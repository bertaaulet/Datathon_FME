#!/usr/bin/env python3
"""Store the embeddings a student's hint is compared with (copilot/hintsim.py).

    python3 prep/embed_refs.py [--db data/tutor.db] [--solutions data/agent_solutions.jsonl]

Needs the embedding server (port 8082). Run it on the laptop after
build_tutor_db.py and import_hints.py, then copy tutor.db to the board. It embeds:

  - the agent's bank hints (hints with source='agent') that have no vector yet;
  - the Catalan method hints of every topic (copilot/topics.py);
  - the short solutions, when the file is there (one per training problem).

Vectors are stored as float32 blobs. Running it again only adds what's missing
(the method hints and solutions are replaced, so edited texts are picked up).
"""
import argparse
import os
import sys

import common
from copilot import embed, hintsim, topics
from copilot.store import Store, default_path


def batches(items, size):
    for start in range(0, len(items), size):
        yield items[start:start + size]


def embed_texts(texts, embedder, size):
    vectors = []
    for chunk in batches(texts, size):
        vectors += embedder(chunk)
    return [hintsim.to_blob(v) for v in vectors]


def run(store, embedder=embed.embed, solutions_path=None, size=16):
    counts = {"agent_hints": 0, "method": 0, "solutions": 0}
    rows = store.rows("SELECT n, text FROM hints WHERE source = 'agent' AND vec IS NULL ORDER BY n")
    for row, vec in zip(rows, embed_texts([r["text"] for r in rows], embedder, size)):
        store.set_hint_vector(row["n"], vec)
        counts["agent_hints"] += 1
    for key in topics.NAMES:
        texts = topics.HINTS[key][topics.HINT_LANG]
        store.set_ref_vectors("method", key, list(zip(texts, embed_texts(texts, embedder, size))))
        counts["method"] += len(texts)
    if solutions_path and os.path.exists(solutions_path):
        known = {row["id"] for row in store.rows("SELECT id FROM problems")}
        found = [r for r in common.read_jsonl(solutions_path)
                 if r.get("id") in known and (r.get("solution") or "").strip()]
        vectors = embed_texts([r["solution"] for r in found], embedder, size)
        for row, vec in zip(found, vectors):
            store.set_ref_vectors("solution", row["id"], [(row["solution"], vec)])
        counts["solutions"] = len(found)
    return counts


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--db", default=default_path())
    p.add_argument("--solutions", default="data/agent_solutions.jsonl")
    p.add_argument("--batch", type=int, default=16)
    args = p.parse_args(argv)

    store = Store(args.db)
    try:
        counts = run(store, solutions_path=args.solutions, size=args.batch)
    except Exception as error:
        store.close()
        raise SystemExit(f"The embedding server didn't answer ({error}). Start it on port "
                         f"{embed.CONFIG['EMBED_PORT']} and run this again.")
    store.close()
    print(f"Embedded into {args.db}: {counts['agent_hints']} agent hints, "
          f"{counts['method']} method hints, {counts['solutions']} solutions.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
