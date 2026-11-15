#!/usr/bin/env python3
"""Check what an agent wrote for one batch, line by line, before anyone uses it.

    python3 prep/check_agent_output.py data/agent/hint_bank_out.jsonl --kind hint_bank

It checks the schema of every line (prep/agent/<kind>.md), that the problem ids
exist when the data is there (data/train.jsonl, data/val.jsonl, data/tutor.db),
and the rules of the batch: bank hints and good hints must pass copilot.leak,
leak hints must fail it, solutions must reach the labelled answer (training
problems only), and so on.

It prints the errors with their line number and writes the lines that pass to
<input>_ok.jsonl (or --ok), filled in with what the next script needs. Both
files hold M3Kang text or labels: keep them in data/, never commit them.

Exit code: 0 when every line passed, 1 when some didn't, 2 when nothing did.
"""
import argparse
import ast
import json
import operator
import os
import re
import sys
from collections import Counter

import common
import agent_lots as lots
from copilot import leak, topics
from copilot.config import CONFIG

LEAK_REASONS = ("lletra", "posicio", "valor")
LEAK_CATEGORIES = ("lletra", "valor", "posicio", "indirecta", "neta")
COMMON_FIELDS = {"id": str, "kind": str, "source": str}
OPTIONAL_COMMON = {"model": str, "note": str}

# kind -> (required fields, optional fields), each {name: type}.
SCHEMAS = {
    "hint_experiment": ({"good": str, "bad": str, "leak": str},
                        {"label": str, "text": str, "options": dict, "lang": str}),
    "hint_bank": ({"lang": str, "hint": str, "step": int}, {"label": str}),
    "solutions": ({"solution": str, "answer": str}, {"expression": str}),
    "problem_types": ({"type": str}, {"topic": str, "python_solvable": bool}),
    "leak_cases": ({"hint": str, "label": str, "leak": bool},
                   {"options": dict, "text": str, "category": str, "lang": str}),
    "topics_reference": ({"topic": str}, {"alt": (str, type(None))}),
    "invented_problems": ({"language": str, "level": int, "text": str, "options": dict,
                           "label": str}, {"topic": str, "solution": str}),
}


class LineError(Exception):
    pass


def need(condition, message):
    if not condition:
        raise LineError(message)


# --- small checks ------------------------------------------------------------

def check_schema(kind, row):
    required, optional = SCHEMAS[kind]
    allowed = {**COMMON_FIELDS, **OPTIONAL_COMMON, **required, **optional}
    for name, kind_type in {**COMMON_FIELDS, **required}.items():
        need(name in row, f"missing field {name!r}")
        need(isinstance(row[name], kind_type) and not isinstance(row[name], bool) or
             kind_type is bool and isinstance(row[name], bool),
             f"field {name!r} should be {type_name(kind_type)}")
        if kind_type is str:
            need(row[name].strip(), f"field {name!r} is empty")
    for name, value in row.items():
        need(name in allowed, f"unknown field {name!r}")
        if name in optional and value is not None:
            expected = optional[name]
            ok = isinstance(value, bool) if expected is bool else \
                isinstance(value, expected) and not isinstance(value, bool)
            need(ok, f"field {name!r} should be {type_name(expected)}")
    need(row["kind"] == kind, f"kind is {row['kind']!r}, expected {kind!r}")
    need(row["source"] == "agent", f"source is {row['source']!r}, expected 'agent'")


def type_name(t):
    if isinstance(t, tuple):
        return " or ".join(type_name(x) for x in t)
    return {str: "a string", int: "an integer", bool: "true or false", dict: "an object",
            type(None): "null"}[t]


def check_letter(value, name="label"):
    need(value in tuple(lots.LETTERS), f"{name} must be one of A-E, got {value!r}")


def check_options(options):
    need(sorted(options) == list(lots.LETTERS), "options must have exactly the keys A-E")
    values = [str(options[k]).strip() for k in lots.LETTERS]
    need(all(values), "every option needs a value")
    need(len(set(values)) == 5, "two options have the same value")


def one_sentence(text):
    """True when the text has at most one sentence: nothing after a full stop."""
    return re.search(r"[.!?…]\s+\S", text.strip()) is None


def leak_reasons(hint, label, option_sets, statements):
    return [leak.check(hint, label, options, statements) for options in option_sets]


def label_for(row, ref):
    entry = ref.get(row["id"]) if ref else None
    if entry and entry.get("label"):
        if row.get("label"):
            need(row["label"] == entry["label"],
                 f"label {row['label']!r} doesn't match the data")
        return entry["label"]
    need(row.get("label"), "no label to check against: add 'label' or provide the data")
    check_letter(row["label"])
    return row["label"]


def options_for(row, ref):
    sets = ref.option_sets(row["id"]) if ref and row["id"] in ref else [{}]
    if row.get("options"):
        check_options(row["options"])
        sets = [row["options"]] + [s for s in sets if s and s != row["options"]]
    return sets


def statements_for(row, ref):
    found = ref.statements(row["id"]) if ref and row["id"] in ref else []
    return [row["text"]] + found if row.get("text") else found


def shown_text(ref, problem_id, prefer=("cat", "eng")):
    for lang in prefer:
        found = ref.text(problem_id, lang) if ref else None
        if found:
            return found
    entry = ref.get(problem_id) if ref else None
    texts = list((entry or {}).get("texts", {}).values())
    return texts[0] if texts else None


# --- arithmetic for the optional "expression" of a solution -----------------

OPERATORS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
             ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
             ast.Pow: operator.pow, ast.USub: operator.neg, ast.UAdd: operator.pos}


def evaluate_expression(text):
    """The value of a plain arithmetic expression ('(12 + 3) * 4 / 5'), or LineError."""
    def walk(node):
        if isinstance(node, ast.Expression):
            return walk(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) \
                and not isinstance(node.value, bool):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in OPERATORS:
            left, right = walk(node.left), walk(node.right)
            if isinstance(node.op, ast.Pow):
                need(abs(right) <= 64, "exponent too large in expression")
            return OPERATORS[type(node.op)](left, right)
        if isinstance(node, ast.UnaryOp) and type(node.op) in OPERATORS:
            return OPERATORS[type(node.op)](walk(node.operand))
        raise LineError("expression may only use numbers, + - * / // % ** and brackets")
    need(len(text) <= 200, "expression longer than 200 characters")
    try:
        return walk(ast.parse(text, mode="eval"))
    except (SyntaxError, ZeroDivisionError, OverflowError) as error:
        raise LineError(f"expression doesn't evaluate: {error}")


def as_number(value):
    text = str(value).strip().replace(",", ".").replace(" ", "")
    if re.fullmatch(r"-?\d+(?:\.\d+)?", text):
        return float(text)
    match = re.fullmatch(r"(-?\d+)/(\d+)", text)
    if match and int(match.group(2)):
        return int(match.group(1)) / int(match.group(2))
    return None


# --- one function per batch ---------------------------------------------------

def check_hint_experiment(row, ref, state):
    need(row["id"] not in state["ids"], "this problem already has hints in the file")
    label = label_for(row, ref)
    option_sets, statements = options_for(row, ref), statements_for(row, ref)
    for name in ("good", "bad", "leak"):
        need(one_sentence(row[name]), f"{name}: a hint is one sentence")
    for name in ("good", "bad"):
        reasons = [r for r in leak_reasons(row[name], label, option_sets, statements) if r]
        need(not reasons, f"{name} hint rejected by copilot.leak ({reasons[0]})" if reasons else "")
    ratio = len(row["bad"].strip()) / len(row["good"].strip())
    need(0.5 <= ratio <= 1.5, "bad should be about as long as good (between half and 1.5 times)")
    reasons = leak_reasons(row["leak"], label, option_sets, statements)
    need(any(r in LEAK_REASONS for r in reasons),
         "leak hint passes copilot.leak: it must give the answer away plainly")
    state["ids"].add(row["id"])
    shown = shown_text(ref, row["id"]) or {}
    return {"id": row["id"], "kind": row["kind"], "source": row["source"],
            "text": row.get("text") or shown.get("text", ""),
            "options": row.get("options") or shown.get("options") or option_sets[0],
            "label": label, "good": row["good"].strip(), "bad": row["bad"].strip(),
            "leak": row["leak"].strip()}


def check_hint_bank(row, ref, state):
    need(row["lang"] == lots.HINT_LANG, f"lang must be {lots.HINT_LANG!r}")
    hint = row["hint"].strip()
    need(len(hint) <= lots.MAX_HINT_CHARS, f"hint longer than {lots.MAX_HINT_CHARS} characters")
    need(one_sentence(hint), "a hint is one sentence")
    if ref:
        need(ref.eligible(row["id"]), "this problem isn't eligible (needs text only and five options)")
    label = label_for(row, ref)
    reasons = [r for r in leak_reasons(hint, label, options_for(row, ref), statements_for(row, ref)) if r]
    need(not reasons, f"rejected by copilot.leak ({reasons[0]})" if reasons else "")
    key = (row["id"], leak.plain(hint))
    need(key not in state["pairs"], "the same hint appears twice for this problem")
    need(row["step"] in (1, 2), "step must be 1 (where to start) or 2 (the next step)")
    need((row["id"], row["step"]) not in state["steps"], f"already a step {row['step']} hint for this problem")
    need(state["per_id"][row["id"]] < 2, "already two hints for this problem")
    state["pairs"].add(key)
    state["steps"].add((row["id"], row["step"]))
    state["per_id"][row["id"]] += 1
    return {"id": row["id"], "kind": row["kind"], "source": row["source"], "lang": row["lang"],
            "step": row["step"], "hint": hint}


def check_solutions(row, ref, state):
    need(row["id"] not in state["ids"], "this problem is already in the file")
    entry = ref.get(row["id"]) if ref else None
    # Validation problems never get a solution: it would reach the RAG and eval.py
    # would measure the agent, not the model.
    need((entry or {}).get("split") != "val", "solutions are for training problems only")
    solution = row["solution"].strip()
    need(len(solution) <= lots.MAX_SOLUTION_CHARS,
         f"solution longer than {lots.MAX_SOLUTION_CHARS} characters")
    check_letter(row["answer"], "answer")
    if entry and entry.get("label"):
        need(row["answer"] == entry["label"], f"answer {row['answer']} doesn't match the label")
    out = {"id": row["id"], "kind": row["kind"], "source": row["source"],
           "solution": solution, "answer": row["answer"]}
    if row.get("expression"):
        value = evaluate_expression(row["expression"])
        target = None
        for options in (ref.option_sets(row["id"]) if entry else []):
            if options and row["answer"] in options:
                target = as_number(options[row["answer"]])
                break
        if target is not None:
            need(abs(value - target) <= 1e-6 * max(1.0, abs(target)),
                 f"expression gives {value:g}, the correct option is {target:g}")
        out["expression"] = row["expression"]
    state["ids"].add(row["id"])
    return out


def check_problem_types(row, ref, state):
    need(row["id"] not in state["ids"], "this problem is already in the file")
    need(row["type"] in lots.PROBLEM_TYPES, f"type must be one of {', '.join(lots.PROBLEM_TYPES)}")
    if row.get("topic") is not None:
        need(row["topic"] in lots.TOPIC_KEYS, f"topic must be one of {', '.join(lots.TOPIC_KEYS)}")
    state["ids"].add(row["id"])
    state["types"][row["type"]] += 1
    out = {"id": row["id"], "kind": row["kind"], "source": row["source"], "type": row["type"]}
    for name in ("topic", "python_solvable"):
        if row.get(name) is not None:
            out[name] = row[name]
    return out


def check_leak_cases(row, ref, state):
    outside = row["id"].startswith(lots.OUTSIDE_PREFIXES)
    check_letter(row["label"])
    if row.get("category") is not None:
        need(row["category"] in LEAK_CATEGORIES,
             f"category must be one of {', '.join(LEAK_CATEGORIES)}")
        need((row["category"] != "neta") == row["leak"],
             "category 'neta' goes with leak false, the others with leak true")
    key = (row["id"], leak.plain(row["hint"]))
    need(key not in state["pairs"], "the same case appears twice")
    if outside or not ref:
        need(row.get("options") and row.get("text"),
             "a case without data needs 'options' and 'text'")
    if row.get("options"):
        check_options(row["options"])
    label = row["label"] if outside or not ref else label_for(row, ref)
    shown = None if outside else shown_text(ref, row["id"], (row.get("lang") or "cat", "eng"))
    state["pairs"].add(key)
    state["leaks"][bool(row["leak"])] += 1
    return {"id": row["id"], "kind": row["kind"], "source": row["source"],
            "hint": row["hint"].strip(), "label": label,
            "options": row.get("options") or (shown or {}).get("options") or {},
            "text": row.get("text") or (shown or {}).get("text", ""),
            "leak": row["leak"], "category": row.get("category")}


def check_topics_reference(row, ref, state):
    need(row["id"] not in state["ids"], "this problem is already in the file")
    need(row["topic"] in lots.TOPIC_KEYS, f"topic must be one of {', '.join(lots.TOPIC_KEYS)}")
    if row.get("alt") is not None:
        need(row["alt"] in lots.TOPIC_KEYS and row["alt"] != row["topic"],
             "alt must be another valid topic, or null")
    state["ids"].add(row["id"])
    shown = shown_text(ref, row["id"], ("eng", "cat"))
    if shown:
        state["agree"][topics.classify(shown["text"]) in (row["topic"], row.get("alt"))] += 1
    return {"id": row["id"], "kind": row["kind"], "source": row["source"],
            "topic": row["topic"], "alt": row.get("alt")}


def check_invented_problems(row, ref, state):
    need(row["id"].startswith(lots.INVENTED_PREFIX),
         f"invented problem ids start with {lots.INVENTED_PREFIX!r}")
    need(row["id"] not in state["ids"], "this id is already in the file")
    need(row["language"] in ("eng", "cat"), "language must be 'eng' or 'cat'")
    need(0 <= row["level"] <= 7, "level must be between 0 and 7")
    check_options(row["options"])
    check_letter(row["label"])
    if row.get("topic") is not None:
        need(row["topic"] in lots.TOPIC_KEYS, f"topic must be one of {', '.join(lots.TOPIC_KEYS)}")
    if ref:
        for other_id, entry in ref.problems.items():
            for text in entry["texts"].values():
                score = lots.similarity(row["text"], text["text"])
                need(score < 0.6, f"too close to the M3Kang problem {other_id} "
                                  f"({score:.0%} of words shared): write a new problem")
    for other in state["texts"]:
        need(lots.similarity(row["text"], other) < 0.8, "almost the same as another invented problem")
    state["ids"].add(row["id"])
    state["texts"].append(row["text"])
    out = {"id": row["id"], "language": row["language"], "level": row["level"],
           "text": row["text"].strip(), "options": row["options"], "label": row["label"],
           "kind": row["kind"], "source": row["source"]}
    for name in ("topic", "solution"):
        if row.get(name):
            out[name] = row[name]
    return out


CHECKS = {name: globals()[f"check_{name}"] for name in lots.KINDS}


def check_line(kind, row, ref, state):
    """Return the row to keep, or raise LineError with the reason."""
    need(isinstance(row, dict), "a line must be a JSON object")
    check_schema(kind, row)
    outside = kind == "invented_problems" or (
        kind == "leak_cases" and row["id"].startswith(lots.OUTSIDE_PREFIXES))
    if ref and not outside:
        need(row["id"] in ref, f"unknown problem id {row['id']!r}")
    if kind == "invented_problems" and ref:
        need(row["id"] not in ref, "invented problems can't reuse an M3Kang id")
    return CHECKS[kind](row, ref, state)


def new_state():
    return {"ids": set(), "pairs": set(), "steps": set(), "per_id": Counter(), "types": Counter(),
            "leaks": Counter(), "agree": Counter(), "texts": []}


def check_file(path, kind, ref):
    """[(line number, row to keep or None, error or None)] for every non-empty line."""
    state, results = new_state(), []
    with open(path, encoding="utf-8") as f:
        for number, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as error:
                results.append((number, None, f"not valid JSON ({error.msg})", None))
                continue
            problem_id = row.get("id") if isinstance(row, dict) else None
            try:
                results.append((number, check_line(kind, row, ref, state), None, problem_id))
            except LineError as error:
                results.append((number, None, str(error), problem_id))
    return results, state


def default_ok_path(path):
    stem, ext = os.path.splitext(path)
    return f"{stem}_ok{ext or '.jsonl'}"


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("file", help="the agent's JSONL output")
    p.add_argument("--kind", required=True, choices=lots.KINDS)
    p.add_argument("--ok", help="where to write the lines that pass (default: <file>_ok.jsonl)")
    p.add_argument("--data", nargs="*", default=["data/train.jsonl", "data/val.jsonl"])
    p.add_argument("--db", default=CONFIG.get("TUTOR_DB", "data/tutor.db"))
    p.add_argument("--no-data", action="store_true", help="check the schema and rules only")
    p.add_argument("--max-errors", type=int, default=50, help="how many errors to print")
    args = p.parse_args(argv)

    ref = lots.Reference() if args.no_data else lots.Reference(args.data, args.db)
    if not ref:
        print("No data found: checking schema and rules only, not the ids.")
    results, state = check_file(args.file, args.kind, ref)
    good = [row for _n, row, error, _id in results if error is None]
    bad = [(n, error, pid) for n, _row, error, pid in results if error is not None]
    for n, error, pid in bad[:args.max_errors]:
        print(f"  line {n}" + (f" ({pid})" if pid else "") + f": {error}")
    if len(bad) > args.max_errors:
        print(f"  ... and {len(bad) - args.max_errors} more")

    ok_path = args.ok or default_ok_path(args.file)
    if os.path.dirname(ok_path):
        os.makedirs(os.path.dirname(ok_path), exist_ok=True)
    with open(ok_path, "w", encoding="utf-8") as out:
        for row in good:
            out.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"{args.kind}: {len(good)}/{len(results)} lines passed, written to {ok_path}")
    if args.kind == "problem_types" and state["types"]:
        print("  types: " + ", ".join(f"{k} {v}" for k, v in state["types"].most_common()))
    if args.kind == "leak_cases":
        print(f"  with a leak: {state['leaks'][True]}, clean: {state['leaks'][False]}")
    if args.kind == "topics_reference" and state["agree"]:
        total = sum(state["agree"].values())
        print(f"  copilot/topics.py agrees on {state['agree'][True]}/{total}")
    if args.kind == "hint_bank":
        short = sum(1 for n in state["per_id"].values() if n < 2)
        print(f"  problems: {len(state['per_id'])}, with fewer than two hints: {short}")
    print(f"Next: review 20 lines by hand; the final file is {lots.OK_FILES[args.kind]}.")
    if not good and results:
        return 2
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
