#!/usr/bin/env python3
"""Time the path of a problem from outside the bank, on the board: harness, Kangaroo, hint.

    python3 prep/hintgen_timing.py                          # prep/hintgen_problems.jsonl
    python3 prep/hintgen_timing.py --problems my.jsonl

Each line of the problems file is {"id", "text"} with the options A) … E) in the text
(invented problems: never M3Kang text). For each one it runs the tutor's real path,
in order and in the foreground, against the real servers and a copy of tutor.db:

  1. solve()            the harness's answer, like predict.py
  2. the Kangaroo       its reference reading with the neutral hint
  3. hintgen            the model's one-sentence hint, with one similar bank problem

It prints and writes results/hintgen-<time>.csv: seconds of each step, the total
(how long after typing the problem the hint of rung 2 is ready), whether a hint came
out, why not if it didn't, and the hint itself (it is written by the model about an
invented problem, so it can be read and published). Needs data/tutor.db with the
agent's hints and data/index.db (the retrieval index), so the problem has neighbours.
"""
import argparse
import csv
import json
import os
import shutil
import sys
import tempfile
import time

import common  # noqa: F401  (puts the repository on sys.path)
from copilot import hintgen
from copilot.config import ROOT
from copilot.llm import letter_probs
from copilot.pipeline import solve
from copilot.store import Store, default_path
from copilot.tutor import Tutor


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--problems", default=os.path.join(ROOT, "prep", "hintgen_problems.jsonl"))
    p.add_argument("--db", default=default_path())
    p.add_argument("--index", default=os.path.join(ROOT, "data", "index.db"))
    args = p.parse_args()

    if not hintgen.enabled():
        sys.exit("HINTGEN is off in config.env: the tutor never writes a hint, there is nothing to time.")
    if not os.path.exists(args.index):
        sys.exit(f"No {args.index}: build it first (build_index.py), or the problem has no neighbours.")
    with open(args.problems, encoding="utf-8") as f:
        problems = [json.loads(line) for line in f if line.strip()]
    from copilot.rag import Index
    index = Index(args.index)

    # A copy, so the real tutor's database never gets these attempts
    folder = tempfile.mkdtemp()
    copy = os.path.join(folder, "tutor.db")
    shutil.copyfile(args.db, copy)
    store = Store(copy)

    times = {}

    def timed(name, function):
        def run(*a, **kw):
            began = time.perf_counter()
            try:
                return function(*a, **kw)
            finally:
                times[name] = times.get(name, 0.0) + time.perf_counter() - began
        return run

    reasons = {}

    def writer(problem, example_text, example_hint):
        hint, reason = hintgen.generate(problem, example_text, example_hint)
        reasons["last"] = reason
        return hint, reason

    tutor = Tutor(store, ask=timed("kangaroo", letter_probs), index=index, background=False,
                  solver=timed("solve", solve), hint_writer=timed("hint", writer))
    tutor.start("hintgen-timing", "", 3)

    os.makedirs(os.path.join(ROOT, "results"), exist_ok=True)
    out_path = os.path.join(ROOT, "results", f"hintgen-{time.strftime('%Y%m%d-%H%M%S')}.csv")
    rows = []
    for problem in problems:
        times.clear()
        reasons.clear()
        began = time.perf_counter()
        tutor.external(problem["text"])
        total = time.perf_counter() - began
        current = tutor.current
        neighbours = len(current["row"]["neighbours"]) if current else 0
        hint = current.get("generated") if current else None
        if current is None:
            why = "no five options read: only placed"
        elif current.get("solve_failed"):
            why = "harness failed"
        elif hint:
            why = ""
        elif "hint" not in times:
            why = "no neighbour with agent hints" if neighbours else "no neighbours"
        else:
            why = reasons.get("last") or "unknown"
        row = {"id": problem.get("id", ""), "solve_s": round(times.get("solve", 0), 1),
               "kangaroo_s": round(times.get("kangaroo", 0), 1),
               "hint_s": round(times.get("hint", 0), 1), "total_s": round(total, 1),
               "neighbours": neighbours, "hint_ok": int(bool(hint)), "why_not": why,
               "hint": hint or ""}
        rows.append(row)
        print(f"{row['id']}: solve {row['solve_s']} s, Kangaroo {row['kangaroo_s']} s, "
              f"hint {row['hint_s']} s, total {row['total_s']} s  "
              + (f"«{hint}»" if hint else f"NO HINT ({why})"))
    with open(out_path, "w", newline="", encoding="utf-8") as out:
        writer_csv = csv.DictWriter(out, fieldnames=list(rows[0]) if rows else ["id"])
        writer_csv.writeheader()
        writer_csv.writerows(rows)
    store.close()
    shutil.rmtree(folder, ignore_errors=True)
    ok = [r for r in rows if r["hint_ok"]]
    if ok:
        print(f"\nHint ready after {max(r['total_s'] for r in ok)} s at worst "
              f"({len(ok)}/{len(rows)} with a hint). Wrote {out_path}")
    else:
        print(f"\nNo hint for any problem. Wrote {out_path}")


if __name__ == "__main__":
    main()
