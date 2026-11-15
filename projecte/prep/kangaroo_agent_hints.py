#!/usr/bin/env python3
"""Show every agent hint to the Kangaroo, ahead of time, and store its verdict.

    python3 prep/kangaroo_agent_hints.py              # every agent hint not measured yet
    python3 prep/kangaroo_agent_hints.py --limit 50

Run it after import_hints.py and kangaroo_baseline.py (same KANGAROO_LANG). For each
agent hint, the Kangaroo reads the problem with the hint, exactly as in the tutor,
and the hint gets its delta (how far it moved the margin towards the right answer)
and whether it convinced the Kangaroo, with the same rule as the tutor:

  - the model preferred a wrong option: convinced if delta > tau and it now prefers
    the right one;
  - the model already preferred the right one (the Kangaroo pretends): delta means
    nothing, so it is not stored; convinced if the model still prefers the right one.

It writes results/agent-hints-kangaroo.csv for the dashboard: ids, step and numbers,
no text and no labels. The model that judges is the one the tutor uses, so read the
share of convincing hints with care. About one model call per hint: ~10 s on the
board, ~0.5 s on the laptop. Stop with Ctrl+C whenever you like: it continues where
it stopped.
"""
import argparse
import csv
import os
import time

import common  # noqa: F401  (puts the repository on sys.path)
from copilot.config import CONFIG
from copilot.llm import letter_probs
from copilot.store import Store, default_path
from copilot.tutor import KANGAROO_LANG, kangaroo


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--db", default=default_path())
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--redo", action="store_true", help="measure again the ones already done")
    p.add_argument("--out", default="results/agent-hints-kangaroo.csv")
    args = p.parse_args()

    store = Store(args.db)
    if store.meta("kangaroo_lang", "eng") != KANGAROO_LANG:
        raise SystemExit(f"Run prep/kangaroo_baseline.py first: the Kangaroo's answers in the "
                         f"database weren't measured in {KANGAROO_LANG}.")
    tau = float(store.meta("tau", CONFIG.get("HINT_TAU", 1.0)))
    todo = store.rows("SELECT h.n, h.problem_id, h.text, p.label, p.k_probs FROM hints h "
                      "JOIN problems p ON p.id = h.problem_id WHERE h.source = 'agent' "
                      "AND p.k_probs IS NOT NULL" + ("" if args.redo else " AND h.convinced IS NULL")
                      + " ORDER BY h.n")
    if args.limit:
        todo = todo[:args.limit]
    print(f"{len(todo)} agent hints to show the Kangaroo (tau = {tau:.2f}, {KANGAROO_LANG}).")
    start = time.time()
    try:
        for n, row in enumerate(todo, 1):
            stored = store.problem(row["problem_id"])
            text = store.text(row["problem_id"], KANGAROO_LANG)
            if not text:
                continue
            problem = {"id": row["problem_id"], "text": text["text"], "options": text["options"]}
            ref = kangaroo(stored["k_probs"], row["label"])
            try:
                answer = letter_probs(problem, hint=row["text"], timeout=180, lang=KANGAROO_LANG)
            except Exception as error:
                print(f"\n  hint {row['n']}: {error}")
                continue
            after = kangaroo(answer["probs"], row["label"])
            if ref["feigned"]:
                delta, convinced = None, after["margin"] > 0
            else:
                delta = after["margin"] - ref["margin"]
                convinced = delta > tau and after["margin"] > 0
            store.set_hint_measure(row["n"], delta, convinced)
            rate = (time.time() - start) / n
            print(f"\r{n}/{len(todo)}  {rate:.1f} s per hint, "
                  f"about {rate * (len(todo) - n) / 60:.0f} min left   ", end="", flush=True)
    except KeyboardInterrupt:
        print("\nStopped. Run it again to continue.")
    print()

    rows = store.rows("SELECT h.problem_id, h.step, h.delta, h.convinced, p.k_margin FROM hints h "
                      "JOIN problems p ON p.id = h.problem_id WHERE h.source = 'agent' "
                      "AND h.convinced IS NOT NULL ORDER BY h.n")
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", newline="", encoding="utf-8") as out:
        writer = csv.writer(out)
        writer.writerow(["id", "step", "feigned", "delta", "convinced"])
        for row in rows:
            feigned = int(row["k_margin"] is not None and row["k_margin"] >= 0)
            writer.writerow([row["problem_id"], row["step"] or "", feigned,
                             "" if row["delta"] is None else f"{row['delta']:.4f}",
                             int(bool(row["convinced"]))])
    real = [r for r in rows if not (r["k_margin"] is not None and r["k_margin"] >= 0)]
    print(f"{len(rows)} agent hints measured. Where the Kangaroo was really wrong ({len(real)}), "
          f"{sum(bool(r['convinced']) for r in real)} convinced it. Wrote {args.out}")
    store.close()


if __name__ == "__main__":
    main()
