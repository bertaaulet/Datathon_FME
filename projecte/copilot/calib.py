"""Small files measured ahead of time: the model's letter bias, and the most common answers.

data/letter_bias.json  {"A": 0.31, ..., "E": 0.08}        from prep/letter_bias.py (uses the model)
data/priors.json       {"global": "D", "by_level": {...}}  from prep/letter_bias.py (labels only)

Both are optional. Without them, predict.py behaves like the baseline.
"""
import json
import os

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


def prior_letter(problem):
    """The most common answer for the problem's level, or the fallback answer."""
    priors = _read(PRIORS_PATH)
    if isinstance(priors, dict):
        letter = priors.get("by_level", {}).get(str(problem.get("level")), priors.get("global"))
        if letter in tuple("ABCDE"):
            return letter
    return CONFIG["FALLBACK_ANSWER"]
