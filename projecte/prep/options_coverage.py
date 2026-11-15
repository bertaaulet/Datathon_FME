#!/usr/bin/env python3
"""How many problems reach the model with five readable options? No model needed.

    python3 prep/options_coverage.py                       # data/val.jsonl
    python3 prep/options_coverage.py --input data/train.jsonl

A problem without its five options never reaches the model: predict.py answers
the fallback letter (FALLBACK_ANSWER, D). This prints, by language and level,
how many problems have five options, and how often the fallback letter is right
on those that don't. That bounds what predict.py can gain from the model.

Prints aggregate numbers only (no problem text, no per-problem labels), and
writes them to results/options_coverage.csv for the dashboard.
"""
import argparse
import csv
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from copilot.config import CONFIG  # noqa: E402

LETTERS = "ABCDE"


def has_options(problem):
    options = problem.get("options") or {}
    return all(str(options.get(letter, "")).strip() for letter in LETTERS)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", default="data/val.jsonl")
    p.add_argument("--out", default="results/options_coverage.csv")
    args = p.parse_args()

    fallback = CONFIG.get("FALLBACK_ANSWER", "D")
    with open(args.input, encoding="utf-8") as f:
        problems = [json.loads(line) for line in f if line.strip()]

    groups = defaultdict(lambda: {"n": 0, "with": 0, "without": 0, "fallback_right": 0})
    for x in problems:
        for key in ((x["language"], "all"), ("all", x.get("level")), ("all", "all")):
            g = groups[key]
            g["n"] += 1
            if has_options(x):
                g["with"] += 1
            else:
                g["without"] += 1
                g["fallback_right"] += x.get("label") == fallback

    def order(key):
        language, level = key
        return (language == "all", language, level == "all", -1 if level == "all" else level)

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", newline="", encoding="utf-8") as out:
        writer = csv.writer(out)
        writer.writerow(["input", "language", "level", "n", "with_options", "without_options",
                         "share_with_options", f"fallback_{fallback}_right_without_options"])
        print(f"{args.input}: {len(problems)} problems. Fallback letter: {fallback}")
        print(f"{'language':>8} {'level':>5} {'n':>5} {'5 options':>10} {'share':>6} "
              f"{'no options':>10} {fallback + ' right':>8}")
        for key in sorted(groups, key=order):
            g = groups[key]
            share = g["with"] / g["n"] if g["n"] else 0
            writer.writerow([args.input, key[0], key[1], g["n"], g["with"], g["without"],
                             f"{share:.3f}", g["fallback_right"]])
            print(f"{key[0]:>8} {str(key[1]):>5} {g['n']:>5} {g['with']:>10} {share:>6.1%} "
                  f"{g['without']:>10} {g['fallback_right']:>8}")
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
