#!/usr/bin/env python3
"""Measure the model's letter bias, and the most common answers, on the training set.

    python3 prep/letter_bias.py                 # 60 training problems, about 10 minutes on the board
    python3 prep/letter_bias.py --limit 0       # all of them
    python3 prep/letter_bias.py --priors-only   # no model: only the most common answers

It writes two small files that predict.py uses when they exist:

    data/letter_bias.json   how much probability the model gives each letter on average.
                            If it says D far more often than 1 time in 5, that's bias, and
                            dividing by it removes it (PREDICT_DEBIAS in config.env).
    data/priors.json        the most common right answer overall and for each level, used
                            for problems with no readable options and when the model fails.

Only training problems are used, so the validation score stays honest. Delete
the files to go back to the baseline.
"""
import argparse
import json
import os
from collections import Counter, defaultdict

import common
from copilot.calib import BIAS_PATH, PRIORS_PATH
from copilot.config import CONFIG
from copilot.llm import LETTERS, letter_probs


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", default="data/train.jsonl")
    p.add_argument("--limit", type=int, default=60, help="0 means every problem")
    p.add_argument("--language", default=CONFIG.get("MODEL_LANG", "eng"))
    p.add_argument("--priors-only", action="store_true")
    p.add_argument("--min-level-count", type=int, default=50,
                   help="a level needs this many problems to get its own most common answer")
    args = p.parse_args()

    rows = [r for r in common.read_jsonl(args.input) if r.get("language") == args.language]
    if not rows:
        raise SystemExit(f"No {args.language} problems in {args.input}.")

    labels = Counter(r["label"] for r in rows)
    by_level = defaultdict(Counter)
    for r in rows:
        by_level[r["level"]][r["label"]] += 1
    priors = {"global": labels.most_common(1)[0][0], "n": len(rows),
              "by_level": {str(level): counts.most_common(1)[0][0]
                           for level, counts in sorted(by_level.items())
                           if sum(counts.values()) >= args.min_level_count}}
    os.makedirs(os.path.dirname(PRIORS_PATH), exist_ok=True)
    with open(PRIORS_PATH, "w", encoding="utf-8") as f:
        json.dump(priors, f, indent=1)
    print(f"Most common answer in {len(rows)} training problems: {priors['global']} "
          f"({100 * labels[priors['global']] / len(rows):.1f}%). By level: {priors['by_level']}")
    print(f"Wrote {PRIORS_PATH}")
    if args.priors_only:
        return

    chosen = common.sample([r for r in rows if common.has_options(r)], args.limit)
    totals = {letter: 0.0 for letter in LETTERS}
    full_totals, full_done = {letter: 0.0 for letter in LETTERS}, 0
    picked, done, missing = Counter(), 0, 0
    for n, problem in enumerate(chosen, 1):
        try:
            answer = letter_probs(problem, timeout=120)   # no bias correction: this measures it
        except Exception as error:
            print(f"\n  {problem['id']}: {error}")
            continue
        missing += answer["found"] < 5
        for letter in LETTERS:
            totals[letter] += answer["probs"][letter]
        if answer["found"] >= 5:  # the server listed every letter: a clean measurement
            full_done += 1
            for letter in LETTERS:
                full_totals[letter] += answer["probs"][letter]
        picked[answer["letter"]] += 1
        done += 1
        print(f"\r{n}/{len(chosen)} problems", end="", flush=True)
    print()
    if not done:
        raise SystemExit("The model answered no problem. Is the service running?")
    # Only problems with all five letters when there are enough; a missing letter's
    # tiny floor would drag its average towards zero (calib.robust() also caps it)
    if full_done >= max(20, done // 3):
        bias = {letter: full_totals[letter] / full_done for letter in LETTERS}
    else:
        bias = {letter: totals[letter] / done for letter in LETTERS}
    bias["n_full"] = full_done
    bias["n"] = done
    with open(BIAS_PATH, "w", encoding="utf-8") as f:
        json.dump(bias, f, indent=1)
    truth = Counter(r["label"] for r in chosen)
    print("Letter   mean probability   times chosen   times right")
    for letter in LETTERS:
        print(f"  {letter}      {bias[letter]:.3f}              {picked[letter]:4}           {truth[letter]:4}")
    if missing:
        print(f"Warning: in {missing} problems the server reported fewer than 5 letters. "
              f"Run prep/check_model.py.")
    print(f"Wrote {BIAS_PATH} from {done} problems. Now measure: python3 eval.py --name debias")


if __name__ == "__main__":
    main()
