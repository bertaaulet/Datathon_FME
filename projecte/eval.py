#!/usr/bin/env python3
"""Measure accuracy and latency on the board, the way the official run does.

    python3 eval.py --limit 50                    # baseline on 50 validation problems
    python3 eval.py --limit 50 --rag 1 --name rag1
    python3 eval.py --languages cat --limit 100

Every run writes per-problem results to results/ and adds one line to
results/ablations.csv, so you can build your ablation table as you go.
"""
import argparse
import csv
import json
import os
import random
import statistics
import subprocess
import time
from collections import Counter, defaultdict

from copilot import topics
from copilot.config import CONFIG
from copilot.pipeline import TIME_LIMIT, solve


def wilson(hits, n, z=1.96):
    """95% confidence interval for a share, as two percentages. Honest for small n."""
    if not n:
        return 0.0, 100.0
    share = hits / n
    centre = (share + z * z / (2 * n)) / (1 + z * z / n)
    half = z * ((share * (1 - share) / n + z * z / (4 * n * n)) ** 0.5) / (1 + z * z / n)
    return 100 * max(0.0, centre - half), 100 * min(1.0, centre + half)


def git_commit():
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"],
                                       stderr=subprocess.DEVNULL, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def table(title, groups):
    print(f"\n{title}")
    for key in sorted(groups, key=str):
        hits = groups[key]
        low, high = wilson(sum(hits), len(hits))
        print(f"  {str(key):38} {sum(hits):4}/{len(hits):<4} {100 * sum(hits) / len(hits):5.1f}%"
              f"   (95% interval {low:.0f}-{high:.0f}%)")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", default="data/val.jsonl")
    p.add_argument("--limit", type=int, default=50, help="0 means every problem")
    p.add_argument("--languages", default="", help="e.g. eng,cat")
    p.add_argument("--rag", type=int, default=0, metavar="K")
    p.add_argument("--index", default="data/index.db")
    p.add_argument("--name", default="", help="a label for this experiment in ablations.csv")
    p.add_argument("--rotations", type=int, default=None, metavar="N",
                   help="extra passes with the options rotated (overrides PREDICT_ROTATIONS)")
    p.add_argument("--debias", choices=["auto", "off"], default=None,
                   help="letter bias correction (overrides PREDICT_DEBIAS)")
    p.add_argument("--no-options", choices=["prior", "model"], default=None,
                   help="what to do without readable options (overrides PREDICT_NO_OPTIONS)")
    args = p.parse_args()

    # The solver reads these when it answers, so one run can try a setting
    # without editing config.env. The official run uses config.env as it is.
    if args.rotations is not None:
        CONFIG["PREDICT_ROTATIONS"] = str(args.rotations)
    if args.debias is not None:
        CONFIG["PREDICT_DEBIAS"] = args.debias
    if args.no_options is not None:
        CONFIG["PREDICT_NO_OPTIONS"] = args.no_options
    settings = (f"rotations={CONFIG.get('PREDICT_ROTATIONS', 0)} "
                f"debias={CONFIG.get('PREDICT_DEBIAS', 'auto')} "
                f"no_options={CONFIG.get('PREDICT_NO_OPTIONS', 'prior')}")

    with open(args.input, encoding="utf-8") as f:
        problems = [json.loads(line) for line in f if line.strip()]
    # The topic comes from the English text of the same problem when the file has it
    english = {x["id"]: x["text"] for x in problems if x.get("language") == "eng"}
    languages = set(filter(None, args.languages.split(",")))
    if languages:
        problems = [x for x in problems if x["language"] in languages]
    random.Random(42).shuffle(problems)  # the same sample every run, so runs compare
    if args.limit:
        problems = problems[:args.limit]

    index = None
    if args.rag:
        from copilot.rag import Index
        index = Index(args.index)

    os.makedirs("results", exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    name = args.name or (f"rag{args.rag}" if args.rag else "baseline")
    detail_path = f"results/eval-{stamp}-{name}.csv"

    rows = []
    with open(detail_path, "w", newline="", encoding="utf-8") as out:
        writer = csv.writer(out)
        writer.writerow(["id", "language", "level", "has_options", "label", "answer",
                         "correct", "seconds", "status", "prompt_tokens", "retrieved",
                         "topic", "calls"])
        for n, problem in enumerate(problems, 1):
            result = solve(problem, index=index, k=args.rag, exclude_id=problem["id"])
            correct = result["answer"] == problem["label"]
            topic = topics.name(topics.classify(english.get(problem["id"], problem["text"])))
            row = {**problem, **result, "correct": correct, "topic": topic,
                   "has_options": bool(problem.get("options"))}
            rows.append(row)
            writer.writerow([problem["id"], problem["language"], problem["level"], row["has_options"],
                             problem["label"], result["answer"], int(correct), result["seconds"],
                             result["status"], result["prompt_tokens"], result["retrieved"],
                             topic, result["calls"]])
            out.flush()
            running = 100 * sum(r["correct"] for r in rows) / len(rows)
            print(f"[{n}/{len(problems)}] {problem['id']} {problem['language']}: "
                  f"{result['answer']} (truth {problem['label']}) {result['seconds']:.1f} s, "
                  f"running accuracy {running:.1f}%", flush=True)

    hits = [r["correct"] for r in rows]
    seconds = [r["seconds"] for r in rows]
    floor = sum(r["label"] == CONFIG["FALLBACK_ANSWER"] for r in rows)
    over = sum(s > TIME_LIMIT for s in seconds)
    accuracy = 100 * sum(hits) / len(hits)

    print("\n" + "=" * 60)
    low, high = wilson(sum(hits), len(hits))
    print(f"Settings: {settings}")
    print(f"Accuracy: {sum(hits)}/{len(hits)} = {accuracy:.1f}%   (95% interval {low:.0f}-{high:.0f}%)")
    print(f"  floor, always {CONFIG['FALLBACK_ANSWER']}: {100 * floor / len(rows):.1f}%   random guess: 20.0%")
    print(f"Latency: mean {statistics.mean(seconds):.1f} s, median {statistics.median(seconds):.1f} s, "
          f"worst {max(seconds):.1f} s, over {TIME_LIMIT:.0f} s: {over}")
    print(f"Status: {dict(Counter(r['status'] for r in rows))}")

    for field, title in (("language", "By language"), ("level", "By level"),
                         ("topic", "By topic (keywords: check it by hand before you trust it)"),
                         ("has_options", "By whether OCR found the options")):
        groups = defaultdict(list)
        for r in rows:
            groups[r[field]].append(r["correct"])
        table(title, groups)

    predicted = Counter(r["answer"] for r in rows)
    truth = Counter(r["label"] for r in rows)
    print("\nLetters   " + "  ".join(f"{l}:{predicted[l]:>3}/{truth[l]:<3}" for l in "ABCDE"))
    print("          (predicted/true; a model that loves one letter shows up here)")

    log = "results/ablations.csv"
    new = not os.path.exists(log)
    with open(log, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if new:
            writer.writerow(["time", "name", "commit", "input", "languages", "n", "rag_k",
                             "accuracy", "mean_s", "worst_s", "over_limit", "settings", "details"])
        writer.writerow([stamp, name, git_commit(), args.input, args.languages or "all", len(rows),
                         args.rag, f"{accuracy:.1f}", f"{statistics.mean(seconds):.1f}",
                         f"{max(seconds):.1f}", over, settings, detail_path])
    print(f"\nDetails: {detail_path}\nAblation log: {log}")


if __name__ == "__main__":
    main()
