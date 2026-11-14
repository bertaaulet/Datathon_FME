#!/usr/bin/env python3
"""Simulated students: does the Elo trainer find a student's level, and the language gap?

    python3 sim/students.py                  # with an invented problem bank
    python3 sim/students.py --db data/tutor.db    # with your real problems' ratings

A simulated student has a true ability, and answers each problem right with
the probability the Elo formula gives. With --penalty, they lose that many
points when the problem is in the classroom language. Nothing here uses the
model, so it runs in a second.

It answers two questions with numbers:

1. Level: starting from the wrong rating, how many problems until the estimate
   is close to the true ability, and how close does it stay?
2. Language gap: is the measured difference between the two ratings close to
   the true penalty, and after how many problems?

It writes results/sim-level.csv and results/sim-gap.csv for the dashboard.
These are simulations of the method, not measurements of real students.
"""
import argparse
import csv
import os
import random
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from copilot import elo  # noqa: E402


def bank(db_path, seed):
    """[(id, rating)]: the real problems' ratings, or an invented spread like M3Kang's levels."""
    if db_path and os.path.exists(db_path):
        from copilot.store import Store
        store = Store(db_path)
        rows = [(r["id"], r["elo"]) for r in store.rows("SELECT id, elo FROM problems WHERE eligible = 1")]
        store.close()
        if rows:
            return rows, "real ratings"
    r = random.Random(seed)
    rows = [(f"sim-{level}-{tram}-{n}", elo.initial_problem(level, tram) + r.gauss(0, 60))
            for level in range(8) for tram in range(3) for n in range(25)]
    return rows, "invented bank"


def run_student(problems, ability, start, steps, r, penalty=0.0):
    """One student. Returns the rating after every answer: [(own, classroom)]."""
    own = classroom = start
    seen_own = seen_classroom = 0
    left = list(problems)
    history = []
    for step in range(steps):
        in_own_language = penalty > 0 and step % 2 == 0   # alternate, to compare the two ratings
        rating = own if in_own_language or penalty == 0 else classroom
        chosen = elo.pick([(pid, value, "") for pid, value in left], rating)
        left = [p for p in left if p[0] != chosen[0]]
        true_ability = ability if in_own_language or penalty == 0 else ability - penalty
        correct = r.random() < elo.expected(true_ability, chosen[1])
        uses_own = in_own_language or penalty == 0
        rating = elo.update(rating, chosen[1], correct,
                            seen_own if uses_own else seen_classroom)
        if uses_own:
            own, seen_own = rating, seen_own + 1
        else:
            classroom, seen_classroom = rating, seen_classroom + 1
        if penalty == 0:
            classroom = own
        history.append((own, classroom))
    return history


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--db", default="")
    p.add_argument("--students", type=int, default=200, help="simulated students per setting")
    p.add_argument("--steps", type=int, default=60)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--out", default="results")
    args = p.parse_args()

    problems, source = bank(args.db, args.seed)
    r = random.Random(args.seed)
    os.makedirs(args.out, exist_ok=True)
    print(f"{len(problems)} problems ({source}), {args.students} simulated students per setting, "
          f"{args.steps} answers each.\n")

    print("1. Finding the level. The student starts 300 points away from their true ability.")
    print("   true ability   error after 10   after 20   after 40   after 60  (median, in Elo points)")
    with open(os.path.join(args.out, "sim-level.csv"), "w", newline="", encoding="utf-8") as out:
        writer = csv.writer(out)
        writer.writerow(["ability", "start", "step", "median_error", "q1_error", "q3_error", "students"])
        for ability in (1000, 1300, 1600, 1900):
            for start in (ability - 300, ability + 300):
                runs = [run_student(problems, ability, start, args.steps, r) for _ in range(args.students)]
                line = []
                for step in range(args.steps):
                    errors = sorted(abs(run[step][0] - ability) for run in runs)
                    q1, median, q3 = statistics.quantiles(errors, n=4)
                    writer.writerow([ability, start, step + 1, f"{median:.1f}", f"{q1:.1f}",
                                     f"{q3:.1f}", args.students])
                    if step + 1 in (10, 20, 40, 60):
                        line.append(f"{median:8.0f}")
                print(f"   {ability} (from {start})   " + "   ".join(line))

    print("\n2. The language gap. The student is weaker by `penalty` in the classroom language.")
    print("   true penalty   measured after 15+15   after 30+30  (median, with the middle half of students)")
    with open(os.path.join(args.out, "sim-gap.csv"), "w", newline="", encoding="utf-8") as out:
        writer = csv.writer(out)
        writer.writerow(["penalty", "answers_per_language", "median_gap", "q1_gap", "q3_gap", "students"])
        for penalty in (0, 100, 200, 300):
            line = []
            runs = [run_student(problems, 1400, 1400, args.steps, r, penalty=penalty or 1e-9)
                    for _ in range(args.students)]
            for per_language in range(5, args.steps // 2 + 1, 5):
                gaps = sorted(run[2 * per_language - 1][0] - run[2 * per_language - 1][1] for run in runs)
                q1, median, q3 = statistics.quantiles(gaps, n=4)
                writer.writerow([penalty, per_language, f"{median:.1f}", f"{q1:.1f}", f"{q3:.1f}",
                                 args.students])
                if per_language in (15, 30):
                    line.append(f"{median:5.0f} ({q1:.0f} to {q3:.0f})")
            print(f"   {penalty:4}           " + "      ".join(line))
    print(f"\nWrote {args.out}/sim-level.csv and {args.out}/sim-gap.csv")


if __name__ == "__main__":
    main()
