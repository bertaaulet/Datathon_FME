#!/usr/bin/env python3
"""Export the input of one agent batch: only the fields the agent needs.

    python3 prep/agent/export_batch.py --kind hint_bank --n 200 --out data/agent/hint_bank_in.jsonl

Reads data/train.jsonl and data/val.jsonl (or data/tutor.db) and writes one
line per problem: {"id", "level", "split", "label"?, "texts": {lang: {"text",
"options"}}}. The label goes out only when the batch needs it (hints, leak
cases, solutions); never for a validation problem. The same --n gives the same problems
every time (seed 42); --skip leaves out problems already done in earlier files.

The output holds M3Kang text: it must stay in data/ (never committed). The
agent's instructions for each batch are in prep/agent/<kind>.md.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import common  # noqa: E402
import agent_lots as lots  # noqa: E402
from copilot import topics  # noqa: E402

NEEDS_LABEL = {"hint_experiment", "hint_bank", "leak_cases", "solutions"}
ELIGIBLE_ONLY = {"hint_experiment", "hint_bank", "leak_cases"}


def done_ids(paths):
    ids = set()
    for row in common.read_jsonl(*paths):
        if row.get("id"):
            ids.add(row["id"])
    return ids


def pick(ref, kind, split, n, skip):
    ids = sorted(ref.problems)
    if split != "all":
        ids = [i for i in ids if ref.get(i).get("split", "train") == split]
    if kind in ELIGIBLE_ONLY:
        ids = [i for i in ids if ref.eligible(i)]
    ids = [i for i in ids if i not in skip]
    return common.sample(ids, n)


def problem_line(ref, problem_id, kind, langs):
    entry = ref.get(problem_id)
    texts = {lang: entry["texts"][lang] for lang in langs if lang in entry["texts"]}
    line = {"id": problem_id, "level": entry.get("level"), "split": entry.get("split", "train"),
            "texts": texts}
    # Validation problems never take their label to the agent: a solution written for
    # one would end up in the RAG and the measured accuracy would mean nothing.
    if kind in NEEDS_LABEL and line["split"] != "val":
        line["label"] = entry.get("label")
    return line


def invented_plan(n, skip):
    """Targets for invented problems: no M3Kang text, only id, language, level, topic."""
    keys = list(topics.NAMES)
    rows, k = [], 0
    while len(rows) < n:
        k += 1
        problem_id = f"{lots.INVENTED_PREFIX}{k:03d}"
        if problem_id in skip:
            continue
        rows.append({"id": problem_id, "language": "cat" if k % 2 else "eng",
                     "level": (k - 1) % 8, "topic": keys[(k - 1) % len(keys)]})
    return rows


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--kind", required=True, choices=lots.KINDS)
    p.add_argument("--n", type=int, default=50, help="how many problems (0: all)")
    p.add_argument("--out", help="default: data/agent/<kind>_in.jsonl")
    p.add_argument("--split", choices=("train", "val", "all"),
                   help="default: all for problem_types and topics_reference, train otherwise")
    p.add_argument("--langs", default="eng,cat", help="languages to include, in this order")
    p.add_argument("--skip", nargs="*", default=[], help="files whose ids are already done")
    p.add_argument("--data", nargs="*", default=["data/train.jsonl", "data/val.jsonl"])
    p.add_argument("--db", default="data/tutor.db")
    args = p.parse_args(argv)

    out = args.out or f"data/agent/{args.kind}_in.jsonl"
    skip = done_ids(args.skip)
    if args.kind == "invented_problems":
        rows = invented_plan(args.n or 100, skip)
    else:
        ref = lots.Reference(args.data, args.db)
        if not ref:
            raise SystemExit("No data: run laptop/prepare_m3kang.py first (or pass --data / --db).")
        split = args.split or ("all" if args.kind in ("problem_types", "topics_reference") else "train")
        if args.kind == "solutions" and split != "train":
            raise SystemExit("Solutions are for training problems only (--split train).")
        langs = [lang for lang in args.langs.split(",") if lang]
        rows = [problem_line(ref, i, args.kind, langs)
                for i in pick(ref, args.kind, split, args.n, skip)]
    if os.path.dirname(out):
        os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"Wrote {len(rows)} lines to {out}. Instructions: prep/agent/{args.kind}.md. "
          f"Keep it in data/: it isn't for Git.")


if __name__ == "__main__":
    main()
