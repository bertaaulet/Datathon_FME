#!/usr/bin/env python3
"""Build the Tukey dashboard: one self-contained HTML page from results/ and dashboard/facts.json.

    python3 dashboard/build.py            # writes dashboard/dashboard.html

Standard library only, no internet: it runs on the laptop or on the board. The page
holds aggregates only (counts, rates, quartiles): no problem text, no ids, no
per-problem labels, so it can be shared.

Sources:
    results/ablations.csv          one row per eval.py run (the single source of truth)
    results/eval-*.csv             the per-problem file named in each row (never committed)
    results/tutor-smoke-*.csv      prep/tutor_smoke.py on the board (timings per tutor step)
    dashboard/facts.json           aggregates measured elsewhere (off-board models, leak
                                   filter, Elo simulation), each with where and source

Every number the page shows is computed here, and a set of checks (shown at the foot of
the page) confirms that ablations.csv and the per-problem files agree.
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
LIMIT = 57.0          # the harness budget; the rule is 60 s

# Runs shown on the page, with plain names. Everything else in ablations.csv still feeds the checks.
CONFIG_RUNS = [
    ("dev50", "dev-nodebias", "Una lletra, sense corregir"),
    ("dev50", "dev-debias", "Una lletra + correcció del biaix"),
    ("dev50", "dev-debias-rag1", "+ un problema semblant (RAG)"),
    ("dev50", "dev-debias-rag1-letter", "+ RAG amb la lletra del semblant"),
    ("demo", "demo-nodebias", "Una lletra, sense corregir"),
    ("demo", "demo-debias", "Una lletra + correcció del biaix"),
]
FINAL_RUN = "demo-debias"
SET_NAMES = {
    "dev50": "Validació equilibrada · 50 problemes",
    "demo": "Conjunt de pràctica dels organitzadors · 100 problemes",
    "val": "Validació antiga · 50 problemes",
}


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
    r = lambda v: round(v, 2)
    return {"n": len(values), "min": r(values[0]), "max": r(values[-1]), "q1": r(q1), "median": r(median),
            "q3": r(q3), "low": r(inside[0]), "high": r(inside[-1]),
            "out": [r(v) for v in values if v < low_fence or v > high_fence]}


def mcnemar(only_a, only_b):
    """Exact two-sided McNemar test on the problems where two runs disagree."""
    n = only_a + only_b
    if not n:
        return 1.0
    tail = sum(math.comb(n, k) for k in range(0, min(only_a, only_b) + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def chi_uniform(counts):
    """Chi-square goodness of fit against equal counts, 4 degrees of freedom (closed form)."""
    n = sum(counts)
    expected = n / len(counts)
    x = sum((c - expected) ** 2 / expected for c in counts)
    # survival function of chi-square with 4 df: exp(-x/2) * (1 + x/2)
    return round(x, 1), math.exp(-x / 2) * (1 + x / 2)


def set_of(input_name):
    if "dev50" in input_name:
        return "dev50"
    if "demo" in input_name:
        return "demo"
    return "val"


def load_runs(results, checks):
    runs = {}
    for row in read_csv(os.path.join(results, "ablations.csv")):
        name = row["name"]
        path = os.path.join(results, os.path.basename(row.get("details") or ""))
        rows = read_csv(path)
        if not rows:
            checks.append({"ok": False, "text": f"Falta el fitxer per problema de «{name}» ({os.path.basename(path)})."})
            continue
        n = len(rows)
        hits = sum(int(r["correct"]) for r in rows)
        seconds = [float(r["seconds"]) for r in rows]
        pct = round(100 * hits / n, 1)
        # checks: the summary row and the per-problem file must agree
        same = (str(n) == row["n"] and abs(pct - float(row["accuracy"])) < 0.05
                and abs(max(seconds) - float(row["worst_s"])) < 0.06)
        checks.append({"ok": same, "text": f"«{name}»: n = {n}, encert {pct} %, pitjor {max(seconds):.1f} s "
                       + ("coincideixen amb ablations.csv" if same else "NO coincideixen amb ablations.csv")})
        predicted = Counter(r["answer"] for r in rows)
        truth = Counter(r["label"] for r in rows)
        levels = defaultdict(lambda: [0, 0])
        for r in rows:
            levels[r["level"]][0] += int(r["correct"])
            levels[r["level"]][1] += 1
        if sum(v[0] for v in levels.values()) != hits or sum(predicted.values()) != n:
            checks.append({"ok": False, "text": f"«{name}»: els talls per nivell o per lletra no sumen el total."})
        runs[name] = {
            "name": name, "set": set_of(row["input"]), "machine": row["machine"], "n": n, "hits": hits,
            "pct": pct, "ci": wilson(hits, n), "seconds": box(seconds), "mean_s": round(sum(seconds) / n, 1),
            "over": sum(s > LIMIT for s in seconds),
            "predicted": {l: predicted.get(l, 0) for l in LETTERS},
            "truth": {l: truth.get(l, 0) for l in LETTERS},
            "_right": {f"{r['id']}|{r['language']}": int(r["correct"]) for r in rows},
            "_no_options": sum(r["has_options"] in ("False", "0", "") for r in rows),
        }
    return runs


def paired(a, b):
    keys = [k for k in a["_right"] if k in b["_right"]]
    only_a = sum(a["_right"][k] and not b["_right"][k] for k in keys)
    only_b = sum(b["_right"][k] and not a["_right"][k] for k in keys)
    return {"n": len(keys), "only_a": only_a, "only_b": only_b, "p": round(mcnemar(only_a, only_b), 3)}


def tutor_steps(results):
    paths = sorted(glob.glob(os.path.join(results, "tutor-smoke-*.csv")))
    if not paths:
        return None
    rows = read_csv(paths[-1])
    groups = {"help": [], "hint": [], "external": [], "next": []}
    for r in rows:
        s = float(r["seconds"])
        if r["step"].startswith("help rung"):
            groups["help"].append(s)
        elif r["step"] == "Kangaroo reads the hint":
            groups["hint"].append(s)
        elif r["step"] == "harness + Kangaroo":
            groups["external"].append(s)
        elif r["step"] == "next problem":
            groups["next"].append(s)
    return {"file": os.path.basename(paths[-1]), "steps": len(rows),
            "passed": sum(r["ok"] == "1" for r in rows),
            "groups": {k: {"n": len(v), "median": math.floor(quantile(sorted(v), .5) * 10 + 0.5) / 10 if v else None,
                           "max": round(max(v), 1) if v else None, "values": sorted(round(x, 1) for x in v)}
                       for k, v in groups.items()}}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--results", default=os.path.join(ROOT, "results"))
    p.add_argument("--facts", default=os.path.join(HERE, "facts.json"))
    p.add_argument("--out", default=os.path.join(HERE, "dashboard.html"))
    args = p.parse_args()

    checks = []
    runs = load_runs(args.results, checks)
    with open(args.facts, encoding="utf-8") as f:
        facts = json.load(f)

    board_runs = [r for r in runs.values() if "aarch64" in r["machine"]]
    checks.append({"ok": len(board_runs) == len(runs),
                   "text": f"{len(board_runs)} de {len(runs)} execucions fetes a la placa (aarch64); cap amb el servidor simulat."})

    # configurations panel
    config = []
    for set_key, name, label in CONFIG_RUNS:
        if name in runs:
            r = runs[name]
            config.append({"set": set_key, "set_name": SET_NAMES[set_key], "name": name, "label": label,
                           "final": name == FINAL_RUN or name == "dev-debias", "n": r["n"], "hits": r["hits"],
                           "pct": r["pct"], "ci": r["ci"], "seconds": r["seconds"], "mean_s": r["mean_s"],
                           "over": r["over"]})
    pairs = []
    for a, b in [("demo-debias", "demo-nodebias"), ("dev-debias", "dev-nodebias"),
                 ("dev-debias-rag1", "dev-debias"), ("dev-debias-rag1-letter", "dev-debias"),
                 ("baseline", "baseline-org"), ("expr-override", "baseline")]:
        if a in runs and b in runs:
            pairs.append({"a": a, "b": b, **paired(runs[a], runs[b])})

    # letters panel
    letters = None
    if "demo-nodebias" in runs and "demo-debias" in runs:
        before, after = runs["demo-nodebias"], runs["demo-debias"]
        chi_b = chi_uniform([before["predicted"][l] for l in LETTERS])
        chi_a = chi_uniform([after["predicted"][l] for l in LETTERS])
        letters = {"n": before["n"], "truth": before["truth"], "before": before["predicted"],
                   "after": after["predicted"], "chi_before": [chi_b[0], chi_b[1]], "chi_after": [chi_a[0], chi_a[1]],
                   "dev50": {"truth": runs.get("dev-debias", {}).get("truth"),
                             "before": runs.get("dev-nodebias", {}).get("predicted"),
                             "after": runs.get("dev-debias", {}).get("predicted")}}

    # off-board models
    models = facts["models"]
    for m in models["rows"]:
        if "hits" in m:
            m["pct"] = round(100 * m["hits"] / m["n"], 1)
            m["ci"] = wilson(m["hits"], m["n"])
        else:
            m["ci"] = wilson(round(m["pct"] * m["n"] / 100), m["n"])
    reason = next(m for m in models["rows"] if m["key"] == "qwen3_4b")
    k, n = reason["hits"], reason["n"]
    reason["p_vs_chance"] = sum(math.comb(n, i) * .2 ** i * .8 ** (n - i) for i in range(k, n + 1))
    checks.append({"ok": abs(reason["pct"] - 54.0) < 0.05,
                   "text": f"Qwen3 4B raonant: {k}/{n} = {reason['pct']} %, igual que a l'informe del fine-tuning."})

    # the old no-options decision
    no_opt = None
    if "baseline" in runs and "baseline-org" in runs:
        no_opt = {"model": runs["baseline-org"]["pct"], "prior": runs["baseline"]["pct"],
                  "model_s": runs["baseline-org"]["mean_s"], "prior_s": runs["baseline"]["mean_s"],
                  "n": runs["baseline"]["n"], "without": runs["baseline"]["_no_options"]}

    tutor = tutor_steps(args.results)
    if tutor:
        checks.append({"ok": tutor["passed"] == facts["tutor"]["checks_passed"],
                       "text": f"Tutor a la placa: {tutor['passed']}/{tutor['steps']} passos correctes a {tutor['file']}."})
    leak = facts["leak"]
    direct = [t for t in leak["types"] if t["label"] in ("Diu la lletra", "Diu la posició")]
    leak["direct"] = {"stopped": sum(t["stopped"] for t in direct), "n": sum(t["n"] for t in direct)}

    total_answers = sum(r["n"] for r in board_runs)
    total_over = sum(r["over"] for r in board_runs)
    final = runs.get(FINAL_RUN)
    headline = {
        "d_before": letters["before"]["D"] if letters else None,
        "d_after": letters["after"]["D"] if letters else None,
        "letters_n": letters["n"] if letters else None,
        "answers": total_answers, "over": total_over, "runs": len(board_runs),
        "final_worst": final["seconds"]["max"] if final else None,
        "final_pct": final["pct"] if final else None, "final_ci": final["ci"] if final else None,
        "reason_pct": reason["pct"],
        "one_letter_best": max(m["pct"] for m in models["rows"] if m["key"] != "qwen3_4b"),
        "leak_direct": leak["direct"], "clean": leak["clean"],
    }

    for r in runs.values():
        del r["_right"]
    data = {"built": time.strftime("%Y-%m-%d %H:%M"), "limit": LIMIT, "headline": headline,
            "config": config, "pairs": pairs, "letters": letters, "models": models, "no_options": no_opt,
            "tutor": tutor, "facts": facts, "checks": checks,
            "extra": {
                "rag": {"pct": runs.get("dev-debias-rag1", {}).get("pct"), "base": runs.get("dev-debias", {}).get("pct"),
                        "b": runs.get("dev-debias-rag1", {}).get("predicted", {}).get("B"),
                        "s": runs.get("dev-debias-rag1", {}).get("mean_s"), "base_s": runs.get("dev-debias", {}).get("mean_s")},
                "rag_letter": {"pct": runs.get("dev-debias-rag1-letter", {}).get("pct"),
                               "s": runs.get("dev-debias-rag1-letter", {}).get("mean_s")},
                "expr": {"pct": runs.get("expr-override", {}).get("pct"), "base": runs.get("baseline", {}).get("pct"),
                         "s": runs.get("expr-override", {}).get("mean_s"), "base_s": runs.get("baseline", {}).get("mean_s"),
                         "worst": (runs.get("expr-override", {}).get("seconds") or {}).get("max")},
            }}
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        page = f.read()
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(page.replace("/*DATA*/null", payload))
    bad = [c for c in checks if not c["ok"]]
    print(f"Wrote {args.out}: {len(runs)} runs, {len(checks)} checks, {len(bad)} failed.")
    for c in bad:
        print("  FAILED:", c["text"])


if __name__ == "__main__":
    main()
