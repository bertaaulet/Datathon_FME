#!/usr/bin/env python3
"""Ask the Kangaroo every usable problem once, ahead of time. Run it overnight.

    python3 prep/kangaroo_baseline.py              # every usable problem not done yet
    python3 prep/kangaroo_baseline.py --limit 50

For each problem it stores the model's five probabilities, the wrong answer the
Kangaroo will give, and its margin (below zero: it prefers a wrong option, so
the student has something to teach). About 9 seconds per problem on the board.
Stop it with Ctrl+C whenever you like: it continues where it stopped.

It also writes results/kangaroo-baseline.csv (ids and numbers only, no problem
text) for the dashboard.
"""
import argparse
import csv
import json
import os
import time

import common
from copilot.config import CONFIG
from copilot.llm import letter_probs
from copilot.store import Store, default_path
from copilot.tutor import NEUTRAL_HINT, kangaroo


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--db", default=default_path())
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--redo", action="store_true", help="measure again the ones already done")
    p.add_argument("--out", default="results/kangaroo-baseline.csv")
    args = p.parse_args()

    store = Store(args.db)
    lang = CONFIG.get("MODEL_LANG", "eng")
    todo = store.rows("SELECT id, label, level FROM problems WHERE eligible = 1"
                      + ("" if args.redo else " AND k_probs IS NULL") + " ORDER BY id")
    if args.limit:
        todo = todo[:args.limit]
    print(f"{len(todo)} problems to ask.")
    start = time.time()
    try:
        for n, row in enumerate(todo, 1):
            text = store.text(row["id"], lang)
            problem = {"id": row["id"], "text": text["text"], "options": text["options"]}
            try:
                answer = letter_probs(problem, hint=NEUTRAL_HINT, timeout=180)
            except Exception as error:
                print(f"\n  {row['id']}: {error}")
                continue
            state = kangaroo(answer["probs"], row["label"])
            store.run("UPDATE problems SET k_answer = ?, k_margin = ?, k_probs = ? WHERE id = ?",
                      (state["answer"], state["margin"], json.dumps(answer["probs"]), row["id"]))
            rate = (time.time() - start) / n
            print(f"\r{n}/{len(todo)}  {rate:.1f} s per problem, "
                  f"about {rate * (len(todo) - n) / 60:.0f} min left   ", end="", flush=True)
    except KeyboardInterrupt:
        print("\nStopped. Run it again to continue.")
    print()

    done = store.rows("SELECT id, level, topic, label, k_answer, k_margin FROM problems "
                      "WHERE k_probs IS NOT NULL ORDER BY id")
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", newline="", encoding="utf-8") as out:
        writer = csv.writer(out)
        writer.writerow(["id", "level", "topic", "label", "kangaroo_answer", "margin", "prefers_right"])
        for row in done:
            writer.writerow([row["id"], row["level"], row["topic"], row["label"], row["k_answer"],
                             f"{row['k_margin']:.4f}", int(row["k_margin"] >= 0)])
    teachable = sum(row["k_margin"] < 0 for row in done)
    print(f"{len(done)} problems measured. The model prefers a wrong option in {teachable} of them: "
          f"those are the ones the student can teach. Wrote {args.out}")
    store.close()


if __name__ == "__main__":
    main()
