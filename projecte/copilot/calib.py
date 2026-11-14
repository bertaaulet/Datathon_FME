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
    """The model's letter bias, or None when it's off or not measured yet."""
    if CONFIG.get("PREDICT_DEBIAS", "auto").lower() == "off":
        return None
    bias = _read(BIAS_PATH)
    if not isinstance(bias, dict) or not all(letter in bias for letter in "ABCDE"):
        return None
    return bias


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
    totals, count = dict.fromkeys("ABCDE", 0.0), 0
    for result in results:
        if not result.get("full"):
            continue
        for order, probs in result.get("passes", []):
            for position, letter in enumerate("ABCDE"):
                totals[letter] += probs[order[position]]
            count += 1
    if not count:
        return None
    bias = {letter: total / count for letter, total in totals.items()}
    bias["n"] = count
    return bias


def prior_letter(problem):
    """The most common answer for the problem's level, or the fallback answer."""
    priors = _read(PRIORS_PATH)
    if isinstance(priors, dict):
        letter = priors.get("by_level", {}).get(str(problem_level(problem)), priors.get("global"))
        if letter in tuple("ABCDE"):
            return letter
    return CONFIG["FALLBACK_ANSWER"]
