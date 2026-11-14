#!/usr/bin/env python3
"""Put the agent's checked hint bank into the tutor's database.

    python3 prep/import_hints.py data/agent_hints.jsonl [--db data/tutor.db]

Takes the file check_agent_output.py wrote for --kind hint_bank (only lines that
passed) and adds each hint with source='agent'. Running it twice adds nothing
new: a hint already there for the same problem is skipped. Hints for problems
that aren't in the database are skipped and counted.
"""
import argparse
import json
import sys

import common  # noqa: F401  (puts the repository on sys.path)
from copilot.store import Store, default_path


def import_hints(store, rows):
    """Return a Counter-like dict: added, already, unknown, invalid."""
    counts = {"added": 0, "already": 0, "unknown": 0, "invalid": 0}
    known = {row["id"] for row in store.rows("SELECT id FROM problems")}
    for row in rows:
        problem_id, hint = row.get("id"), (row.get("hint") or "").strip()
        if row.get("kind", "hint_bank") != "hint_bank" or row.get("source", "agent") != "agent" \
                or not problem_id or not hint:
            counts["invalid"] += 1
        elif problem_id not in known:
            counts["unknown"] += 1
        elif store.has_hint(problem_id, hint):
            counts["already"] += 1
        else:
            store.add_hint(problem_id, None, hint, None, False, source="agent")
            counts["added"] += 1
    return counts


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("file", help="the _ok file of a hint_bank batch")
    p.add_argument("--db", default=default_path())
    args = p.parse_args(argv)

    with open(args.file, encoding="utf-8") as f:
        try:
            rows = [json.loads(line) for line in f if line.strip()]
        except json.JSONDecodeError as error:
            raise SystemExit(f"{args.file} isn't JSONL ({error}). Check it with check_agent_output.py.")
    store = Store(args.db)
    try:
        counts = import_hints(store, rows)
    finally:
        store.close()
    print(f"Added {counts['added']} hints with source='agent' to {args.db}; "
          f"{counts['already']} were already there, {counts['unknown']} are for problems "
          f"not in the database, {counts['invalid']} aren't bank hints.")
    return 0 if not counts["invalid"] else 1


if __name__ == "__main__":
    sys.exit(main())
