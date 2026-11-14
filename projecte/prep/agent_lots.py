"""What each agent batch ("lot") looks like, and the reference data to check it against.

Shared by prep/agent/export_batch.py, prep/check_agent_output.py and
prep/import_hints.py. The instructions the agent reads are in prep/agent/*.md;
keep both in step when a schema changes.

Standard library only. Everything these scripts read or write lives in data/,
which is never committed: it holds M3Kang text and labels.
"""
import json
import os
import re
import sqlite3

import common
from copilot import leak, topics

LETTERS = common.LETTERS

KINDS = ("hint_experiment", "hint_bank", "solutions", "problem_types", "leak_cases",
         "topics_reference", "invented_problems")

# Where the validated lines of each batch go by default (docs/PLA.md, "El banc de l'agent").
OK_FILES = {
    "hint_experiment": "data/hints_experiment.jsonl",   # read by prep/hint_experiment.py
    "hint_bank": "data/agent_hints.jsonl",               # read by prep/import_hints.py
    "solutions": "data/agent_solutions.jsonl",           # harness stage 4 (RAG) and fine-tuning
    "problem_types": "data/problem_types.jsonl",         # harness stage 2 and the error analysis
    "leak_cases": "data/leak_cases.jsonl",               # python -m copilot.leak
    "topics_reference": "data/topics_gold.jsonl",        # accuracy of copilot/topics.py
    "invented_problems": "data/invented.jsonl",          # outside problems with a known answer
}

# Problem types for the problem_types batch. They decide which Python solvers to write
# (harness stage 2) and slice the error analysis, so keep the list short and stable.
PROBLEM_TYPES = (
    "arithmetic",          # a calculation written out in the statement
    "percent_ratio",       # percentages, fractions of a quantity, proportions, scales
    "units_measure",       # unit conversion, speed, money, weights
    "multiples_divisors",  # divisibility, primes, remainders, gcd / lcm
    "digits",              # properties of the digits of a number
    "clock_calendar",      # times, durations, days of the week, dates
    "ages",                # ages now and in the past or future
    "equations",           # unknowns, systems, balances
    "sequences_patterns",  # sequences, repeating patterns, growth
    "counting",            # arrangements, combinations, paths, cases
    "probability",
    "logic",               # truth-tellers, deduction, ordering people or objects
    "geometry_plane",      # lengths, angles, areas, perimeters in 2D
    "geometry_space",      # cubes, nets, solids, views
    "visual",              # needs the figure and cannot be solved from the text alone
    "other",
)

# Invented problems are not from M3Kang: their ids must say so.
INVENTED_PREFIX = "inv-"
# Leak test cases may use invented problems too (the team's sample problems included).
OUTSIDE_PREFIXES = (INVENTED_PREFIX, "sample-")

MAX_SOLUTION_CHARS = 600
MAX_HINT_CHARS = 200
HINT_LANG = "cat"


class Reference:
    """The problems an agent batch talks about: label, split and text per language.

    Reads data/train.jsonl and data/val.jsonl, and data/tutor.db when it's there.
    Empty when there's no data yet: the checker then checks the schema only.
    """

    def __init__(self, jsonl=None, db=None):
        self.problems = {}   # id -> {"label", "level", "split", "text_only", "texts": {lang: {...}}}
        jsonl = [p for p in (jsonl or []) if os.path.exists(p)]
        for path in jsonl:
            split = "val" if os.path.basename(path).startswith("val") else "train"
            with open(path, encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        self._add(json.loads(line), split)
        if db and os.path.exists(db):
            self._read_db(db)
        self.sources = jsonl + ([db] if db and os.path.exists(db) else [])

    def _add(self, row, split=None, eligible=None):
        entry = self.problems.setdefault(row["id"], {"texts": {}})
        for key in ("label", "level", "text_only"):
            if row.get(key) is not None:
                entry.setdefault(key, row[key])
        if split:
            entry.setdefault("split", split)
        if eligible is not None:
            entry["eligible"] = bool(eligible)
        lang = row.get("language") or row.get("lang")
        if lang and row.get("text") is not None:
            entry["texts"][lang] = {"text": row["text"], "options": row.get("options") or {}}

    def _read_db(self, path):
        db = sqlite3.connect(path)
        db.row_factory = sqlite3.Row
        try:
            for row in db.execute("SELECT id, label, level, text_only, eligible FROM problems"):
                self._add(dict(row), eligible=row["eligible"])
            for row in db.execute("SELECT id, lang, text, options FROM texts"):
                self._add({"id": row["id"], "language": row["lang"], "text": row["text"],
                           "options": json.loads(row["options"] or "{}")})
        except sqlite3.Error as error:
            print(f"  (could not read {path}: {error})")
        finally:
            db.close()

    def __bool__(self):
        return bool(self.problems)

    def __contains__(self, problem_id):
        return problem_id in self.problems

    def get(self, problem_id):
        return self.problems.get(problem_id)

    def eligible(self, problem_id):
        """Text-only with five readable options: the problems the tutor can use."""
        entry = self.problems[problem_id]
        if "eligible" in entry:
            return entry["eligible"]
        return bool(entry.get("text_only", True)) and any(
            common.has_options(t) for t in entry["texts"].values())

    def statements(self, problem_id):
        entry = self.problems.get(problem_id) or {"texts": {}}
        return [t["text"] for t in entry["texts"].values() if t.get("text")]

    def option_sets(self, problem_id):
        """Every language's options that has all five: OCR can differ between images."""
        entry = self.problems.get(problem_id) or {"texts": {}}
        found = [t["options"] for t in entry["texts"].values() if common.has_options(t)]
        return found or [{}]

    def text(self, problem_id, lang):
        entry = self.problems.get(problem_id) or {"texts": {}}
        return entry["texts"].get(lang)


def default_reference():
    return Reference(["data/train.jsonl", "data/val.jsonl"], "data/tutor.db")


def plain_words(text):
    """The words of a text longer than two letters, lower case and without accents."""
    return {w for w in re.findall(r"[a-z0-9]+", leak.plain(text)) if len(w) > 2}


def similarity(a, b):
    """Jaccard overlap of the words of two texts, 0 to 1."""
    wa, wb = plain_words(a), plain_words(b)
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


TOPIC_KEYS = tuple(topics.NAMES)
