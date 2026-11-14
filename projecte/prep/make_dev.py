#!/usr/bin/env python3
"""Build decision sets from the validation file that look like the final test.

    python3 prep/make_dev.py                      # data/val.jsonl -> data/dev50.jsonl, data/dev100.jsonl

The final test has every option readable, one language per problem and (in the
practice set) every letter right equally often. So each set here keeps only
validation problems with five options that OCR did not flag as suspect, takes
ONE language per problem (half eng, half cat), and the same number of problems
for each right letter. dev50 is part of dev100. Both are fixed (SEED=42).

Run eval.py on them with --limit 0. They hold M3Kang text: never commit them.
"""
import argparse
import hashlib
import json
import os
from collections import Counter, defaultdict


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", default="data/val.jsonl")
    p.add_argument("--out", default="data")
    p.add_argument("--sizes", default="50,100")
    p.add_argument("--seed", default="42")
    args = p.parse_args()

    by_id = defaultdict(dict)
    with open(args.input, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                row = json.loads(line)
                if len(row.get("options") or {}) == 5 and not row.get("options_suspect"):
                    by_id[row["id"]][row["language"]] = row
    key = lambda text: hashlib.sha256(f"{args.seed}|{text}".encode()).hexdigest()
    by_letter = defaultdict(list)
    for problem_id in sorted(by_id, key=key):
        by_letter[next(iter(by_id[problem_id].values()))["label"]].append(problem_id)

    for size in sorted(int(s) for s in args.sizes.split(",")):
        per_letter = size // 5
        short = {l: len(ids) for l, ids in by_letter.items() if len(ids) < per_letter}
        if short:
            raise SystemExit(f"Not enough problems for {size}: {short}")
        rows = []
        for letter in "ABCDE":
            for n, problem_id in enumerate(by_letter[letter][:per_letter]):
                langs = by_id[problem_id]
                wanted = "eng" if n % 2 == 0 else "cat"
                rows.append(langs.get(wanted) or next(iter(langs.values())))
        path = os.path.join(args.out, f"dev{size}.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
        print(f"{path}: {len(rows)} problems, letters {dict(sorted(Counter(r['label'] for r in rows).items()))}, "
              f"languages {dict(Counter(r['language'] for r in rows))}")


if __name__ == "__main__":
    main()
