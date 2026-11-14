"""Small files measured ahead of time: the model's letter bias, and the most common answers.

data/letter_bias.json  {"A": 0.31, ..., "E": 0.08}        from prep/letter_bias.py (uses the model)
data/priors.json       {"global": "D", "by_level": {...}}  from prep/letter_bias.py (labels only)

Both are optional. Without them, predict.py behaves like the baseline.
They only hold aggregate numbers, so they are committed: the hidden test uses them.
"""
import json
import os
import re

from .config import CONFIG, ROOT

BIAS_PATH = os.path.join(ROOT, "data", "letter_bias.json")
PRIORS_PATH = os.path.join(ROOT, "data", "priors.json")
_cache = {}


def _read(path):
    stamp = os.path.getmtime(path) if os.path.exists(path) else None
    if path not in _cache or _cache[path][0] != stamp:
        value = None
        if stamp is not None:
            try:
                with open(path, encoding="utf-8") as f:
                    value = json.load(f)
            except (OSError, ValueError):
                value = None
        _cache[path] = (stamp, value)
    return _cache[path][1]


def letter_bias():
    """The bias to apply while solving, or None: off, batch (applied at the end) or not measured."""
    if CONFIG.get("PREDICT_DEBIAS", "auto").lower() in ("off", "batch"):
        return None
    return file_bias()


def file_bias():
    """data/letter_bias.json, made robust (robust()), or None."""
    bias = _read(BIAS_PATH)
    if not isinstance(bias, dict) or not all(letter in bias for letter in "ABCDE"):
        return None
    return robust(bias)


def robust(bias):
    """No letter below BIAS_FLOOR, then shares that add up to 1.

    When the server doesn't list a letter among its top tokens, that letter gets a
    tiny probability. Averaged, its bias can end near zero (C = 0.005 on the board),
    and dividing by it made C win almost every problem. The floor caps how much one
    letter can be boosted (at most 1/BIAS_FLOOR times).
    """
    floor = float(CONFIG.get("BIAS_FLOOR", 0.05) or 0)
    if all(float(bias[letter]) >= floor for letter in "ABCDE"):
        return dict(bias)   # nothing to fix: keep the measured numbers as they are
    raw = {letter: max(float(bias[letter]), floor) for letter in "ABCDE"}
    total = sum(raw.values())
    fixed = {letter: value / total for letter, value in raw.items()}
    for key in ("n", "n_full"):
        if key in bias:
            fixed[key] = bias[key]
    return fixed


_LEVEL_IN_ID = re.compile(r"^lvl-(\d+)_")


def problem_level(problem):
    """The problem's level: the "level" field, else read from an M3Kang id (lvl-3_2015_13).

    None when neither says it, so the caller falls back to the global answer.
    """
    level = problem.get("level")
    if level is not None and str(level).strip() != "":
        try:
            return int(level)
        except (TypeError, ValueError):
            pass
    match = _LEVEL_IN_ID.match(str(problem.get("id", "")))
    return int(match.group(1)) if match else None


def batch_bias(results):
    """The letter bias measured on the batch itself, without labels: {"A": p, ...} or None.

    results are solve() outputs run with no bias correction. Each pass is
    turned back into positions (what the model saw as A, B, ...), and the
    probabilities are averaged over every pass of every problem with five options.
    """
    usable = [r for r in results if r.get("full") and r.get("passes")]
    # Problems where the server listed all five letters measure the bias best: use only
    # those when there are enough of them
    complete = [r for r in usable if r.get("letters_found", 5) >= 5]
    if len(complete) >= int(CONFIG.get("PREDICT_BATCH_MIN", 20) or 0):
        usable = complete
    totals, count = dict.fromkeys("ABCDE", 0.0), 0
    for result in usable:
        for order, probs in result.get("passes", []):
            for position, letter in enumerate("ABCDE"):
                totals[letter] += probs[order[position]]
            count += 1
    if not count:
        return None
    bias = {letter: total / count for letter, total in totals.items()}
    bias["n"] = count
    return robust(bias)


def end_of_run_bias(results):
    """For PREDICT_DEBIAS=batch: the batch's own bias, or the file's when the batch is too small.

    Returns (bias or None, where it came from).
    """
    bias = batch_bias(results)
    if bias and bias["n"] >= int(CONFIG.get("PREDICT_BATCH_MIN", 20) or 0):
        return bias, "batch"
    bias = file_bias()
    return (bias, "file") if bias else (None, "none")


def prior_letter(problem):
    """The most common answer for the problem's level, or the fallback answer."""
    priors = _read(PRIORS_PATH)
    if isinstance(priors, dict):
        letter = priors.get("by_level", {}).get(str(problem_level(problem)), priors.get("global"))
        if letter in tuple("ABCDE"):
            return letter
    return CONFIG["FALLBACK_ANSWER"]
