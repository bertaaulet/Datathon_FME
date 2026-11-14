#!/usr/bin/env python3
"""Split the prepared M3Kang problems into train, validation and test, by id and by level.

    python3 prep/split_data.py data/train.jsonl data/val.jsonl          # 70/15/15, SEED=42
    python3 prep/split_data.py data/*.jsonl --val 0.15 --test 0.15 --out data

Every translation of a problem has the same id and stays in the same set, and
each level is split separately, so the three sets have the same mix of levels.
The order inside each level comes from a hash of the id and the seed, so the
split is the same every time and on every machine.

    train.jsonl  the retrieval index, priors.json and the letter bias
    val.jsonl    exploring and deciding (eval.py)
    test.jsonl   one final run with the chosen settings: the number we publish

The input files are read before anything is written. Files that would be
replaced are first moved to <out>/before-split/. Never commit any of them.
"""
import argparse
import hashlib
import json
import os
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from copilot.calib import problem_level  # noqa: E402


def split_ids(levels, val, test, seed):
    """{id: "train" | "val" | "test"} from {id: level}."""
    by_level = defaultdict(list)
    for problem_id, level in levels.items():
        by_level[level].append(problem_id)
    split = {}
    for level, ids in by_level.items():
        ids.sort(key=lambda i: hashlib.sha256(f"{seed}|{i}".encode()).hexdigest())
        n_test, n_val = round(len(ids) * test), round(len(ids) * val)
        for n, problem_id in enumerate(ids):
            split[problem_id] = "test" if n < n_test else "val" if n < n_test + n_val else "train"
    return split


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("inputs", nargs="+", help="prepared JSONL files (any split)")
    p.add_argument("--val", type=float, default=0.15)
    p.add_argument("--test", type=float, default=0.15)
    p.add_argument("--seed", default="42")
    p.add_argument("--out", default="data")
    args = p.parse_args()

    rows, seen = [], set()
    for path in args.inputs:
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    row = json.loads(line)
                    key = (row["id"], row.get("language"))
                    if key not in seen:   # the same problem twice across the inputs
                        seen.add(key)
                        rows.append(row)
    levels = {}
    for row in rows:
        levels.setdefault(row["id"], problem_level(row))
    split = split_ids(levels, args.val, args.test, args.seed)

    os.makedirs(args.out, exist_ok=True)
    backup = os.path.join(args.out, "before-split")
    for name in ("train", "val", "test"):
        path = os.path.join(args.out, f"{name}.jsonl")
        if os.path.exists(path):
            os.makedirs(backup, exist_ok=True)
            os.replace(path, os.path.join(backup, f"{name}.jsonl"))
    outputs = {name: open(os.path.join(args.out, f"{name}.jsonl"), "w", encoding="utf-8")
               for name in ("train", "val", "test")}
    counts = Counter()
    for row in rows:
        name = split[row["id"]]
        row["split"] = name
        outputs[name].write(json.dumps(row, ensure_ascii=False) + "\n")
        counts[(name, row.get("language"))] += 1
    for f in outputs.values():
        f.close()

    ids = Counter(split.values())
    print(f"{len(levels)} problems, {len(rows)} rows. Seed {args.seed}.")
    for name in ("train", "val", "test"):
        langs = ", ".join(f"{lang} {n}" for (s, lang), n in sorted(counts.items()) if s == name)
        print(f"  {name:5} {ids[name]:5} problems ({100 * ids[name] / len(levels):.0f}%): {langs}")
    print("Now: python3 prep/letter_bias.py --priors-only, and rebuild index.db and tutor.db.")


if __name__ == "__main__":
    main()
