#!/usr/bin/env python3
"""Build the tutor's database from the prepared M3Kang files.

    python3 prep/build_tutor_db.py                       # data/train.jsonl + data/val.jsonl
    python3 prep/build_tutor_db.py --show-topics 50      # also print 50 problems with their topic
    python3 prep/build_tutor_db.py --no-neighbours       # skip the embeddings

For every problem it stores: its level, year and question number, a topic, a
first Elo rating, whether the tutor can use it, its text in every language you
prepared, and its most similar problems.

The tutor only uses problems that are text-only and whose five options OCR
could read ("eligible"). The neighbours need the embedding server (step 7 of
the base README); with --no-neighbours, or if the server is down, a problem's
neighbours are the closest-rated problems of the same topic.

Running it again keeps what the tutor has learned: ratings, the Kangaroo's
answers, the student and the hints.

The database holds M3Kang text: never commit it (.gitignore excludes *.db).
"""
import argparse
import json
import operator
import re
from array import array
from collections import Counter, defaultdict

import common
from copilot import elo, topics
from copilot.config import CONFIG
from copilot.llm import format_problem
from copilot.store import Store, default_path

ID = re.compile(r"^lvl-(\d+)_(\d{4})_(\d+)")


def embed_all(problems, batch=16):
    from copilot.embed import embed
    vectors = {}
    for i in range(0, len(problems), batch):
        chunk = problems[i:i + batch]
        for problem, vector in zip(chunk, embed([format_problem(p) for p in chunk])):
            vectors[problem["id"]] = array("f", vector)
        print(f"\r  {min(i + batch, len(problems))}/{len(problems)} problems embedded", end="", flush=True)
    print()
    return vectors


def nearest(vectors, k):
    """For every id, the k most similar other ids. Plain loops: slow but dependency-free."""
    ids = list(vectors)
    result = {}
    for n, a in enumerate(ids, 1):
        va = vectors[a]
        scored = [(sum(map(operator.mul, va, vectors[b])), b) for b in ids if b != a]
        scored.sort(reverse=True)
        result[a] = [b for _score, b in scored[:k]]
        if n % 25 == 0 or n == len(ids):
            print(f"\r  neighbours for {n}/{len(ids)} problems", end="", flush=True)
    print()
    return result


def by_rating(problems, k):
    """Fallback without embeddings: same topic, closest rating."""
    result = {}
    for p in problems:
        same = [q for q in problems if q["topic"] == p["topic"] and q["id"] != p["id"]]
        same.sort(key=lambda q: (abs(q["elo"] - p["elo"]), q["id"]))
        result[p["id"]] = [q["id"] for q in same[:k]]
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--inputs", nargs="*", default=["data/train.jsonl", "data/val.jsonl"])
    p.add_argument("--db", default=default_path())
    p.add_argument("--neighbours", type=int, default=5)
    p.add_argument("--no-neighbours", action="store_true")
    p.add_argument("--show-topics", type=int, default=0, metavar="N")
    args = p.parse_args()

    model_lang = CONFIG.get("MODEL_LANG", "eng")
    rows = common.read_jsonl(*args.inputs)
    if not rows:
        raise SystemExit("No problems found. Prepare M3Kang first (step 9 of the base README).")
    texts = defaultdict(dict)
    for row in rows:
        texts[row["id"]][row["language"]] = row

    last = defaultdict(int)   # the highest question number of each paper
    parsed = {}
    for problem_id in texts:
        match = ID.match(problem_id)
        parsed[problem_id] = tuple(int(g) for g in match.groups()) if match else (None, None, None)
        if match:
            level, year, number = parsed[problem_id]
            last[(level, year)] = max(last[(level, year)], number)

    problems = []
    for problem_id, versions in texts.items():
        base = versions.get(model_lang) or next(iter(versions.values()))
        level, year, number = parsed[problem_id]
        level = base.get("level", level) if base.get("level") is not None else level
        tram = elo.tram(number, last.get((level, year)))
        problems.append({
            "id": problem_id, "level": level or 0, "year": base.get("year", year), "number": number,
            "tram": tram, "topic": topics.classify(base["text"]), "label": base["label"],
            "text_only": int(bool(base.get("text_only", True))),
            "eligible": int(bool(base.get("text_only", True)) and common.has_options(base)
                            and model_lang in versions),
            "elo": elo.initial_problem(level, tram), "base": base,
        })
    eligible = [q for q in problems if q["eligible"]]

    store = Store(args.db)
    store.many("INSERT OR IGNORE INTO problems (id, elo) VALUES (?, ?)",
               [(q["id"], q["elo"]) for q in problems])
    store.many("UPDATE problems SET level = ?, year = ?, number = ?, tram = ?, topic = ?, "
               "label = ?, text_only = ?, eligible = ? WHERE id = ?",
               [(q["level"], q["year"], q["number"], q["tram"], q["topic"], q["label"],
                 q["text_only"], q["eligible"], q["id"]) for q in problems])
    # Official M3Kang rows: they replace a machine translation of the same problem and language
    store.many("INSERT OR REPLACE INTO texts (id, lang, text, options, source) "
               "VALUES (?, ?, ?, ?, 'official')",
               [(row["id"], row["language"], row["text"],
                 json.dumps(row.get("options") or {}, ensure_ascii=False)) for row in rows])

    neighbours = None
    if not args.no_neighbours and eligible:
        try:
            print("Embedding the eligible problems (needs the embedding server)...")
            neighbours = nearest(embed_all([q["base"] for q in eligible]), args.neighbours)
            how = "embeddings"
        except Exception as error:
            print(f"\n  The embedding server didn't answer ({error}).")
    if neighbours is None:
        neighbours = by_rating(eligible, args.neighbours)
        how = "same topic, closest rating"
    store.many("UPDATE problems SET neighbours = ? WHERE id = ?",
               [(json.dumps(ids), problem_id) for problem_id, ids in neighbours.items()])
    store.set_meta("neighbours", how)

    languages = Counter(row["language"] for row in rows)
    print(f"\nWrote {args.db}")
    print(f"  problems: {len(problems)}, the tutor can use {len(eligible)} "
          f"(text-only, five readable options, with a {model_lang} version)")
    print(f"  languages: " + ", ".join(f"{lang} {n}" for lang, n in sorted(languages.items())))
    print(f"  neighbours: {how}")
    print("  topics of the usable problems:")
    for key, n in Counter(q["topic"] for q in eligible).most_common():
        print(f"    {topics.name(key):42} {n:4}")
    if args.show_topics:
        print(f"\nCheck these {args.show_topics} by hand. Is the topic right?")
        for q in common.sample(eligible, args.show_topics):
            print(f"  [{topics.name(q['topic'])}] {q['id']}: {q['base']['text'][:90]}")
    store.close()


if __name__ == "__main__":
    main()
