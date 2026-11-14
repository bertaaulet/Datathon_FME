#!/usr/bin/env python3
"""Official entry point: answer every problem with one letter, A to E.

    python3 predict.py --input problems.jsonl --output predictions.csv
    python3 predict.py --input problems.jsonl --output predictions.csv --rag 1

Input: one JSON object per line with at least "id" and "text", plus
"options" ({"A": ..., "E": ...}) and "language" when available.
Output: a CSV with id, language, answer, seconds, status.

Rules: runs offline, at most 60 seconds per problem, deterministic.
It never stops on a bad line, a missing file or a model error: every
problem gets a letter. With PREDICT_DEBIAS=batch (config.env) the letter
bias is measured on the input itself at the end, and the CSV is rewritten
with the corrected letters (no extra model calls).
"""
import argparse
import csv
import json
import os
import re
import sys

from copilot.calib import end_of_run_bias
from copilot.config import CONFIG, ROOT
from copilot.pipeline import FALLBACK, rescore, solve

FIELDS = ["id", "language", "answer", "seconds", "status"]


def read_problems(path):
    """Every non-empty line, as a dict. A broken line becomes a problem with no text,
    keeping its id when it can be read, so it still gets an answer."""
    problems = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for n, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                problem = json.loads(line)
                if not isinstance(problem, dict):
                    raise ValueError("not an object")
            except ValueError:
                found = re.search(r'"id"\s*:\s*"([^"]*)"', line)
                problem = {"id": found.group(1) if found else f"line-{n}", "_broken": True}
                print(f"line {n}: not valid JSON, answering {FALLBACK}", file=sys.stderr)
            problems.append(problem)
    return problems


def write_rows(path, rows):
    """Write the whole CSV to a temporary file, then swap it in: never half a file."""
    temporary = path + ".tmp"
    with open(temporary, "w", newline="", encoding="utf-8") as out:
        writer = csv.writer(out)
        writer.writerow(FIELDS)
        writer.writerows(rows)
    os.replace(temporary, path)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--rag", type=int, default=None, metavar="K",
                   help="add K similar solved problems (default: PREDICT_RAG_K in config.env)")
    p.add_argument("--index", default=None, help="default: PREDICT_RAG_INDEX in config.env")
    args = p.parse_args()

    rag_k = args.rag if args.rag is not None else int(CONFIG.get("PREDICT_RAG_K", 0) or 0)
    args.index = args.index or os.path.join(ROOT, CONFIG.get("PREDICT_RAG_INDEX", "data/index.db"))
    index = None
    if rag_k:
        try:
            if not os.path.exists(args.index):
                raise FileNotFoundError(args.index)
            from copilot.rag import Index
            index = Index(args.index)
        except Exception as error:  # answer without examples rather than not at all
            print(f"No retrieval ({type(error).__name__}: {error}). "
                  f"Build the index with: python3 build_index.py", file=sys.stderr)
            index = None

    problems = read_problems(args.input)
    batch = CONFIG.get("PREDICT_DEBIAS", "auto").lower() == "batch"

    rows, results = [], []
    with open(args.output, "w", newline="", encoding="utf-8") as out:
        writer = csv.writer(out)
        writer.writerow(FIELDS)
        for n, problem in enumerate(problems, 1):
            if problem.get("_broken"):
                result = {"answer": FALLBACK, "seconds": 0.0, "status": "error: bad input line"}
            else:
                result = solve(problem, index=index, k=rag_k if index else 0)
            row = [str(problem.get("id", "")), str(problem.get("language", "") or ""),
                   result["answer"], result["seconds"], result["status"]]
            rows.append(row)
            results.append(result)
            writer.writerow(row)
            out.flush()
            print(f"[{n}/{len(problems)}] {row[0]} -> {result['answer']} "
                  f"in {result['seconds']:.1f} s ({result['status']})", file=sys.stderr)

    if batch:
        try:
            bias, source = end_of_run_bias(results)
            if bias:
                changed = 0
                for row, result in zip(rows, results):
                    before = result["answer"]
                    rescore(result, bias)
                    row[2] = result["answer"]
                    changed += before != result["answer"]
                write_rows(args.output, rows)
                print(f"Letter bias from {source}: {changed} answers changed", file=sys.stderr)
            else:
                print("No letter bias to apply: the answers stay as written", file=sys.stderr)
        except Exception as error:  # the CSV already written stays valid
            print(f"Batch correction skipped ({type(error).__name__}: {error})", file=sys.stderr)


if __name__ == "__main__":
    main()
