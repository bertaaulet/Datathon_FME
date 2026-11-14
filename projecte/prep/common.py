"""Shared by the preparation scripts: find the repository, read problem files."""
import json
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

LETTERS = "ABCDE"


def read_jsonl(*paths):
    rows = []
    for path in paths:
        if not os.path.exists(path):
            print(f"  (skipping {path}: not found)")
            continue
        with open(path, encoding="utf-8") as f:
            rows += [json.loads(line) for line in f if line.strip()]
    return rows


def has_options(problem):
    options = problem.get("options") or {}
    return all(str(options.get(letter, "")).strip() for letter in LETTERS)


def sample(rows, limit, seed=42):
    """The same sample every run, so results compare."""
    rows = list(rows)
    random.Random(seed).shuffle(rows)
    return rows[:limit] if limit else rows


def percentile(values, q):
    """The q-th percentile (0 to 100) by linear interpolation. Empty list: None."""
    values = sorted(values)
    if not values:
        return None
    position = (len(values) - 1) * q / 100.0
    low = int(position)
    high = min(low + 1, len(values) - 1)
    return values[low] + (values[high] - values[low]) * (position - low)
