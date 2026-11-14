"""The copilot's solver: one problem in, one letter out.

predict.py and eval.py both call solve(), so what's here is exactly what the
official run measures. The steps, each switched in config.env:

1. No readable options: answer the most common letter (PREDICT_NO_OPTIONS).
2. Ask the model for a probability per letter, in one call.
3. Remove the model's letter bias, if it was measured (PREDICT_DEBIAS).
4. Ask again with the options rotated, while there's time, and average
   (PREDICT_ROTATIONS). The question is cached, so a pass only re-reads the options.

Whatever goes wrong, solve() returns a letter: the official run never stops.
Guardrails: the input is cleaned first (clean_problem), every call is planned
with the board's speed before it's made (estimate_seconds), a problem too long
to read in time is shortened instead of timing out, and the answer is always
the best one found so far (result["stage"] says which step gave it).
"""
import math
import socket
import time
import urllib.error

from . import mathexpr
from .calib import letter_bias, prior_letter
from .config import CONFIG
from .llm import EXPR_MAX_TOKENS, LETTERS, URL, expression, letter_probs, split_problem

TIME_LIMIT = float(CONFIG["TIME_LIMIT_SECONDS"])
FALLBACK = CONFIG["FALLBACK_ANSWER"]
MARGIN = 3.0  # seconds kept free for Python and for writing the answer
READ_TPS = float(CONFIG.get("READ_TOKENS_PER_S", 10.8))
WRITE_TPS = float(CONFIG.get("WRITE_TOKENS_PER_S", 5.8))
CHARS_PER_TOKEN = float(CONFIG.get("CHARS_PER_TOKEN", 3.0))
PROMPT_OVERHEAD = 60  # tokens: system prompt and chat template
# Rotation s shows the option s places further on in position A. Far apart first.
SHIFTS = (2, 4, 1, 3)


def rotation(shift):
    return "".join(LETTERS[(i + shift) % 5] for i in range(5))


def combine(passes):
    """Average several {"A": p, ...} answers (geometric mean) into one."""
    scores = {letter: sum(math.log(max(p[letter], 1e-9)) for p in passes) / len(passes)
              for letter in LETTERS}
    top = max(scores.values())
    weights = {letter: math.exp(s - top) for letter, s in scores.items()}
    total = sum(weights.values())
    return {letter: w / total for letter, w in weights.items()}


def clean_problem(problem):
    """A safe copy of one input line: strings where strings are expected, options A-E only."""
    if not isinstance(problem, dict):
        problem = {}
    clean = dict(problem)
    clean["id"] = str(problem.get("id", "") or "")
    clean["language"] = str(problem.get("language", "") or "")
    text = problem.get("text", "")
    clean["text"] = text if isinstance(text, str) else ("" if text is None else str(text))
    options = problem.get("options")
    kept = {}
    if isinstance(options, dict):
        for key, value in options.items():
            letter = str(key).strip().upper().strip("()).:")
            if letter in tuple(LETTERS) and value is not None and str(value).strip():
                kept[letter] = " ".join(str(value).split())
    clean["options"] = kept
    return clean


def estimate_seconds(chars, generated=1):
    """How long one call should take on the board, from the prompt length."""
    return (PROMPT_OVERHEAD + chars / CHARS_PER_TOKEN) / READ_TPS + generated / WRITE_TPS + 0.5


def fit_text(question, options_chars, seconds):
    """Shorten the question so one call fits in seconds: keep the start and the end
    (the question itself is usually last). Returns the question unchanged when it fits."""
    if estimate_seconds(len(question) + options_chars) <= seconds:
        return question
    budget_tokens = (seconds - 0.5 - 1 / WRITE_TPS) * READ_TPS - PROMPT_OVERHEAD
    keep = int(budget_tokens * CHARS_PER_TOKEN) - options_chars - 5
    if keep < 200:  # too little left to be worth reading
        return None
    head = keep // 3
    return question[:head].rstrip() + " ... " + question[len(question) - (keep - head):].lstrip()


def best_letter(probs):
    """The most likely letter. Ties go to the earlier letter, so runs repeat."""
    return max(LETTERS, key=lambda letter: (probs[letter], -LETTERS.index(letter)))


def rescore(result, bias):
    """Apply a letter bias after the fact, to a result solved without one (eval.py --debias batch).

    Changes result["probs"] and result["answer"] in place. No model call.
    """
    if not bias or not result.get("full") or not result.get("passes"):
        return result
    fixed = []
    for order, probs in result["passes"]:
        # probabilities by position (what the model saw), divided by the bias, then back
        by_position = {LETTERS[i]: probs[order[i]] / max(float(bias.get(LETTERS[i], 0.2)), 1e-6)
                       for i in range(5)}
        total = sum(by_position.values())
        fixed.append({order[i]: by_position[LETTERS[i]] / total for i in range(5)})
    result["probs"] = combine(fixed)
    result["answer"] = best_letter(result["probs"])
    return apply_expression(result)


def apply_expression(result):
    """Use the letter Python computed from the model's expression, if there is one.

    PREDICT_EXPR_MODE=override: that letter wins. vote: its probability is
    multiplied by PREDICT_EXPR_WEIGHT, and the letter call can still overrule it.
    """
    letter = result.get("expr_letter")
    if not letter:
        return result
    if CONFIG.get("PREDICT_EXPR_MODE", "override").lower() == "vote" and result.get("probs"):
        weight = float(CONFIG.get("PREDICT_EXPR_WEIGHT", 4))
        boosted = {l: p * (weight if l == letter else 1.0) for l, p in result["probs"].items()}
        total = sum(boosted.values())
        result["probs"] = {l: p / total for l, p in boosted.items()}
        result["answer"] = best_letter(result["probs"])
        result["stage"] = "expr-vote"
    else:
        result["answer"], result["stage"] = letter, "expr"
    return result


def expression_on():
    return CONFIG.get("PREDICT_EXPRESSION", "off").lower() == "on"


def solve(problem, index=None, k=0, exclude_id=None, image_b64=None, llm_url=URL,
          time_limit=TIME_LIMIT):
    """Return {"answer", "seconds", "status", "probs", "calls", ...} for one problem.

    index and k turn on retrieval: the k most similar solved problems are
    added to the prompt as examples. Each example costs reading time.
    image_b64 and llm_url send the problem image to a vision server.
    """
    start = time.perf_counter()
    result = {"answer": FALLBACK, "status": "ok", "prompt_tokens": 0, "retrieved": "",
              "examples": [], "probs": {}, "calls": 0, "letters_found": 0,
              "passes": [], "full": False, "stage": "fallback", "shortened": False,
              "expr": "", "expr_value": None, "expr_letter": ""}
    try:
        problem = clean_problem(problem)
        result["answer"], result["stage"] = prior_letter(problem), "prior"
        _solve(problem, result, start, index, k, exclude_id, image_b64, llm_url, time_limit)
    except (socket.timeout, TimeoutError):
        result["status"] = "timeout"
    except urllib.error.URLError as error:
        if isinstance(error.reason, (socket.timeout, TimeoutError)):
            result["status"] = "timeout"
        else:
            result["status"] = f"error: {error.reason}"
    except Exception as error:  # a reset connection, odd JSON, a bug: still answer a letter
        result["status"] = f"error: {type(error).__name__}"
    if result["answer"] not in tuple(LETTERS):
        result["answer"] = FALLBACK
    result["seconds"] = round(time.perf_counter() - start, 2)
    return result


def _solve(problem, result, start, index, k, exclude_id, image_b64, llm_url, time_limit):
    def left():
        return time_limit - (time.perf_counter() - start) - MARGIN

    question, options = split_problem(problem)
    full = all(letter in options for letter in LETTERS)
    result["full"] = full
    blind = not options and not image_b64
    if blind and CONFIG.get("PREDICT_NO_OPTIONS", "prior").lower() == "prior":
        return  # the letters mean nothing to the model: keep the most common one

    examples = []
    if index is not None and k > 0:
        hits = index.search(problem, k=k, exclude_id=exclude_id)
        examples = [p for _score, p in hits]
        result["examples"] = hits
        result["retrieved"] = ";".join(f"{p['id']}:{s:.2f}" for s, p in hits)

    # Plan the first call: if the problem can't be read in time, read a shorter version
    options_chars = sum(len(v) + 4 for v in options.values())
    example_chars = sum(len(e.get("text", "")) + 40 for e in examples)
    room = left() - estimate_seconds(example_chars) + estimate_seconds(0)
    short = fit_text(question, options_chars, room)
    if short is None:
        return  # not even a short version fits: keep the prior
    if short != question:
        problem = {**problem, "text": short, "options": options}
        result["shortened"] = True

    bias = letter_bias() if full else None
    began = time.perf_counter()
    first = letter_probs(problem, examples, timeout=max(left(), 1.0), image_b64=image_b64,
                         url=llm_url, bias=bias)
    slowest = time.perf_counter() - began
    # A rotation reads the whole prompt again (the board's cache can't reuse it):
    # plan it as the slower of the measured first call and the estimate
    # (with the token count the server reports, when it reports one)
    read = first["timings"].get("prompt_n") or 0
    planned = (read / READ_TPS + 1 / WRITE_TPS + 0.5 if read > 0 else
               estimate_seconds(len(problem.get("text", "")) + options_chars + example_chars))
    passes = [first["probs"]]
    result["passes"].append((LETTERS, first["probs"]))
    result.update(calls=1, letters_found=first["found"],
                  prompt_tokens=first["timings"].get("prompt_n", 0),
                  probs=first["probs"], answer=best_letter(first["probs"]), stage="model")
    result["model_answer"] = result["answer"]  # the letter call alone, before the expression

    # The model writes an expression, Python computes it (only for numeric options)
    if expression_on() and not image_b64 and mathexpr.numeric(options):
        cost = estimate_seconds(len(problem.get("text", "")) + options_chars, generated=EXPR_MAX_TOKENS)
        if left() >= cost:
            try:
                text, _timings = expression(problem, timeout=max(left(), 1.0), url=llm_url)
                result["calls"] += 1
                value = mathexpr.evaluate(text)
                result.update(expr=text, expr_value=value,
                              expr_letter=mathexpr.match(value, options) or "")
            except Exception:  # no expression: keep the letter call's answer
                pass
            if result["expr_letter"] and CONFIG.get("PREDICT_EXPR_MODE", "override").lower() != "vote":
                apply_expression(result)
                return  # Python is sure: don't spend time on rotations

    wanted = int(CONFIG.get("PREDICT_ROTATIONS", 0) or 0) if full else 0
    for shift in SHIFTS[:max(wanted, 0)]:
        if left() < max(slowest, planned) * 1.1:
            break
        began = time.perf_counter()
        try:
            extra = letter_probs(problem, examples, timeout=max(left(), 1.0), image_b64=image_b64,
                                 url=llm_url, order=rotation(shift), bias=bias)
        except Exception:  # keep the answer we already have
            break
        took = time.perf_counter() - began
        slowest = took if result["calls"] == 1 else max(slowest, took)
        passes.append(extra["probs"])
        result["passes"].append((rotation(shift), extra["probs"]))
        result["calls"] += 1
        result["probs"] = combine(passes)
        result["answer"] = best_letter(result["probs"])
        result["stage"] = "rotations"
        result["model_answer"] = result["answer"]
    apply_expression(result)  # once, on the final probabilities (vote mode)
