#!/usr/bin/env python3
"""Build the Tukey dashboard: one self-contained HTML page from the files in results/.

    python3 dashboard/build.py                     # writes dashboard/dashboard.html
    python3 dashboard/build.py --baseline baseline # the experiment the others are compared with

Run it on the board or on your laptop (copy results/ over first). Standard
library only. The page needs no internet and holds no problem text: only ids,
letters, times and counts.

Every panel answers one design question with one chart, says what the data
show, and proposes a decision. The proposals are careful on purpose: a
difference inside the noise is called noise. Add your own conclusions in
dashboard/notes.json: {"config": "We chose ...", "errors": "...", ...}.

What feeds each panel:
    config, errors, bias   results/ablations.csv and results/eval-*.csv   (eval.py)
    hints                  results/hints-*.csv                            (prep/hint_experiment.py)
    leaks                  results/leak.json        (python3 -m copilot.leak cases.jsonl results/leak.json)
    kangaroo               results/kangaroo-baseline.csv                  (prep/kangaroo_baseline.py)
    simulation             results/sim-level.csv, results/sim-gap.csv     (sim/students.py)
"""
import argparse
import csv
import glob
import json
import math
import os
import time
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LETTERS = "ABCDE"


def read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def wilson(hits, n, z=1.96):
    if not n:
        return [0.0, 100.0]
    share = hits / n
    centre = (share + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(share * (1 - share) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [round(100 * max(0.0, centre - half), 1), round(100 * min(1.0, centre + half), 1)]


def quantile(values, q):
    position = (len(values) - 1) * q
    low = int(position)
    high = min(low + 1, len(values) - 1)
    return values[low] + (values[high] - values[low]) * (position - low)


def box(values):
    """Tukey's box plot numbers: quartiles, whiskers at 1.5 IQR, and the points beyond."""
    values = sorted(values)
    if not values:
        return None
    q1, median, q3 = (quantile(values, q) for q in (0.25, 0.5, 0.75))
    low_fence, high_fence = q1 - 1.5 * (q3 - q1), q3 + 1.5 * (q3 - q1)
    inside = [v for v in values if low_fence <= v <= high_fence] or values
    return {"n": len(values), "min": values[0], "max": values[-1], "q1": q1, "median": median,
            "q3": q3, "low": inside[0], "high": inside[-1],
            "out": [v for v in values if v < low_fence or v > high_fence][:60]}


def mcnemar(gained, lost):
    """Exact two-sided test on the problems where two runs disagree."""
    n = gained + lost
    if not n:
        return 1.0
    tail = sum(math.comb(n, k) for k in range(0, min(gained, lost) + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def groups(rows, field):
    found = defaultdict(list)
    for row in rows:
        found[row.get(field, "") or "?"].append(int(row["correct"]))
    result = []
    for key, hits in found.items():
        result.append({"key": key, "n": len(hits), "hits": sum(hits),
                       "pct": round(100 * sum(hits) / len(hits), 1), "ci": wilson(sum(hits), len(hits))})
    return sorted(result, key=lambda g: (str(g["key"]).zfill(4)))


def experiments(results, baseline_name):
    runs = []
    for row in read_csv(os.path.join(results, "ablations.csv")):
        details = row.get("details") or f"results/eval-{row['time']}-{row['name']}.csv"
        path = os.path.join(results, os.path.basename(details))
        rows = read_csv(path)
        if not rows:
            continue
        hits = sum(int(r["correct"]) for r in rows)
        n = len(rows)
        seconds = [float(r["seconds"]) for r in rows]
        truth = Counter(r["label"] for r in rows)
        floor_letter = truth.most_common(1)[0][0]
        runs.append({
            "name": row["name"], "time": row["time"], "commit": row.get("commit", ""),
            "settings": row.get("settings", ""), "rag": row.get("rag_k", "0"),
            "languages": row.get("languages", ""), "n": n, "hits": hits,
            "pct": round(100 * hits / n, 1), "ci": wilson(hits, n),
            "seconds": box(seconds), "mean_s": round(sum(seconds) / n, 1),
            "over": sum(s > 60 for s in seconds),
            "status": dict(Counter(r["status"].split(":")[0] for r in rows)),
            "floor": {"letter": floor_letter, "pct": round(100 * truth[floor_letter] / n, 1)},
            "by_level": groups(rows, "level"), "by_topic": groups(rows, "topic"),
            "by_language": groups(rows, "language"), "by_options": groups(rows, "has_options"),
            "letters": [{"letter": l, "predicted": sum(r["answer"] == l for r in rows),
                         "true": truth[l]} for l in LETTERS],
            "_right": {f"{r['id']}|{r['language']}": int(r["correct"]) for r in rows},
        })
    base = next((r for r in runs if r["name"] == baseline_name), runs[0] if runs else None)
    for run in runs:
        run["is_baseline"] = run is base
        shared = [k for k in run["_right"] if k in base["_right"]] if base else []
        gained = sum(run["_right"][k] and not base["_right"][k] for k in shared)
        lost = sum(base["_right"][k] and not run["_right"][k] for k in shared)
        run["vs_baseline"] = None if run is base else {
            "shared": len(shared), "gained": gained, "lost": lost,
            "p": round(mcnemar(gained, lost), 3)}
    for run in runs:
        del run["_right"]
    return runs, (base["name"] if base else None)


def hints(results):
    paths = sorted(glob.glob(os.path.join(results, "hints-*.csv")))
    if not paths:
        return None
    rows = read_csv(paths[-1])
    by_kind, by_problem = defaultdict(list), defaultdict(dict)
    for row in rows:
        by_kind[row["kind"]].append(float(row["delta"]))
        by_problem[row["id"]][row["kind"]] = float(row["delta"])
    pairs = [(p["good"], p["bad"]) for p in by_problem.values() if "good" in p and "bad" in p]
    wins = sum(g > b for g, b in pairs)
    losses = sum(g < b for g, b in pairs)
    seconds = [float(r["seconds"]) for r in rows]
    tau = None
    tau_path = os.path.join(ROOT, "data", "tau.json")
    if os.path.exists(tau_path):
        with open(tau_path, encoding="utf-8") as f:
            tau = json.load(f).get("tau")
    return {"file": os.path.basename(paths[-1]), "tau": tau,
            "kinds": {kind: box(values) for kind, values in by_kind.items()},
            "up": {kind: sum(v > 0 for v in values) for kind, values in by_kind.items()},
            "above_tau": None if tau is None else sum(v > tau for v in by_kind.get("good", [])),
            "pairs": len(pairs), "wins": wins, "losses": losses,
            "p": round(mcnemar(wins, losses), 3), "seconds": box(seconds)}


def kangaroo(results):
    rows = read_csv(os.path.join(results, "kangaroo-baseline.csv"))
    if not rows:
        return None
    by_level = defaultdict(list)
    for row in rows:
        by_level[row["level"]].append(1 - int(row["prefers_right"]))
    return {"n": len(rows), "teachable": sum(1 - int(r["prefers_right"]) for r in rows),
            "margin": box([float(r["margin"]) for r in rows]),
            "by_level": [{"key": level, "n": len(v), "hits": sum(v),
                          "pct": round(100 * sum(v) / len(v), 1), "ci": wilson(sum(v), len(v))}
                         for level, v in sorted(by_level.items())]}


def simulation(results):
    level = read_csv(os.path.join(results, "sim-level.csv"))
    gap = read_csv(os.path.join(results, "sim-gap.csv"))
    if not level and not gap:
        return None
    steps = defaultdict(list)
    for row in level:
        steps[int(row["step"])].append((float(row["median_error"]), float(row["q1_error"]),
                                        float(row["q3_error"])))
    curve = [{"step": step, "median": round(sum(v[0] for v in values) / len(values), 1),
              "q1": round(sum(v[1] for v in values) / len(values), 1),
              "q3": round(sum(v[2] for v in values) / len(values), 1)}
             for step, values in sorted(steps.items())]
    return {"curve": curve, "students": int(level[0]["students"]) if level else None,
            "gap": [{"penalty": int(float(r["penalty"])), "per": int(r["answers_per_language"]),
                     "median": float(r["median_gap"]), "q1": float(r["q1_gap"]),
                     "q3": float(r["q3_gap"])} for r in gap]}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--results", default=os.path.join(ROOT, "results"))
    p.add_argument("--out", default=os.path.join(HERE, "dashboard.html"))
    p.add_argument("--baseline", default="baseline", help="name of the experiment to compare with")
    p.add_argument("--label", default="", help="a warning shown at the top, e.g. 'TEST DATA'")
    args = p.parse_args()

    runs, base = experiments(args.results, args.baseline)
    leak = None
    leak_path = os.path.join(args.results, "leak.json")
    if os.path.exists(leak_path):
        with open(leak_path, encoding="utf-8") as f:
            leak = json.load(f)
    notes = {}
    notes_path = os.path.join(HERE, "notes.json")
    if os.path.exists(notes_path):
        with open(notes_path, encoding="utf-8") as f:
            notes = json.load(f)
    data = {"built": time.strftime("%Y-%m-%d %H:%M"), "label": args.label, "baseline": base,
            "runs": runs, "hints": hints(args.results), "leak": leak,
            "kangaroo": kangaroo(args.results), "sim": simulation(args.results), "notes": notes}
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        page = f.read()
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(page.replace("/*DATA*/null", payload))
    found = [name for name in ("hints", "leak", "kangaroo", "sim") if data[name]]
    print(f"Wrote {args.out}: {len(runs)} experiments" + (f", plus {', '.join(found)}" if found else "")
          + ". Open it in a browser.")


if __name__ == "__main__":
    main()
