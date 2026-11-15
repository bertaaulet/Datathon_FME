"""The tutor's SQLite file: problems, their texts, the student, attempts and hints.

Everything about the student stays in this file, on the board. It also holds
M3Kang text, so it must never be committed: .gitignore excludes *.db.
"""
import json
import os
import sqlite3
import threading
import time

from .config import CONFIG, ROOT

SCHEMA = """
CREATE TABLE IF NOT EXISTS problems (
    id TEXT PRIMARY KEY,
    level INTEGER, year INTEGER, number INTEGER, tram INTEGER,
    topic TEXT, label TEXT, text_only INTEGER,
    eligible INTEGER,       -- 1: text-only, with five readable options
    elo REAL,
    k_answer TEXT,          -- the Kangaroo's wrong answer, measured ahead of time
    k_margin REAL,          -- log P(correct) - log P(best wrong option), before any hint
    k_probs TEXT,           -- the five probabilities, as JSON
    neighbours TEXT         -- ids of the most similar problems, as JSON
);
CREATE TABLE IF NOT EXISTS texts (
    id TEXT, lang TEXT, text TEXT, options TEXT,
    source TEXT DEFAULT 'official',  -- 'official' (M3Kang) or the translator: 'opus-mt', 'haiku'...
    PRIMARY KEY (id, lang)
);
CREATE TABLE IF NOT EXISTS student (
    id INTEGER PRIMARY KEY,
    name TEXT, lang_origen TEXT, level INTEGER,
    elo_cat REAL, elo_origen REAL,
    etapa INTEGER,          -- 1: both languages, 2: classroom language + button, 3: classroom only
    streak INTEGER
);
-- The language bridge, once per home language: the student keeps a rating, a stage and a
-- streak for each one, and finds them again after switching. student.elo_origen, etapa and
-- streak are a copy of the row of the language in use.
CREATE TABLE IF NOT EXISTS student_lang (
    student INTEGER, lang TEXT, elo REAL, etapa INTEGER, streak INTEGER,
    PRIMARY KEY (student, lang)
);
CREATE TABLE IF NOT EXISTS attempts (
    n INTEGER PRIMARY KEY AUTOINCREMENT,
    student INTEGER, problem_id TEXT,
    lang TEXT,              -- the language the answer counts for: 'cat' or 'origen'
    shown TEXT,             -- what was on screen: 'cat', 'both' or 'origen'
    answer TEXT, correct INTEGER, revealed INTEGER, helps INTEGER,
    seconds REAL, ts REAL,
    external INTEGER DEFAULT 0, -- 1: a problem from outside the bank, checked against the
                                -- harness's answer; never moves a rating or a bank count
    origin_lang TEXT,           -- the student's home language then ('' for none); NULL: older row
    retry INTEGER DEFAULT 0     -- 1: a problem tried again from the failed list; moves no rating
);
CREATE TABLE IF NOT EXISTS hints (
    n INTEGER PRIMARY KEY AUTOINCREMENT,
    problem_id TEXT, student INTEGER, text TEXT,
    delta REAL,             -- how far the hint moved the Kangaroo's margin (NULL: not measured)
    convinced INTEGER,
    ts REAL,
    source TEXT DEFAULT 'student',  -- who wrote it: 'student' or 'agent'
    step INTEGER,           -- an agent hint's place: 1 (where to start) or 2 (the next step)
    lang TEXT               -- guessed language of a stored student's hint
);
-- What happened to each hint a student sent the Kangaroo, with no text (docs/PISTES.md):
-- outcome 'rejected' (reason: the leak filter's), 'not_convinced' or 'convinced'.
-- feigned = 1 when the model already preferred the right answer and the Kangaroo
-- only pretended (no delta then: it measures nothing). Bank problems only.
CREATE TABLE IF NOT EXISTS hint_events (
    n INTEGER PRIMARY KEY AUTOINCREMENT,
    problem_id TEXT, outcome TEXT, reason TEXT, feigned INTEGER, delta REAL, ts REAL
);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
"""

# Columns added after the first version: (table, column, declaration). Older databases
# get them when they are opened, keeping their rows.
MIGRATIONS = [
    ("hints", "source", "TEXT DEFAULT 'student'"),
    ("hints", "step", "INTEGER"),
    ("attempts", "external", "INTEGER DEFAULT 0"),
    ("texts", "source", "TEXT DEFAULT 'official'"),
    ("attempts", "origin_lang", "TEXT"),
    ("hints", "lang", "TEXT"),
    ("attempts", "retry", "INTEGER DEFAULT 0"),
]
# Older databases may still have the columns of the shared-hint version (relevance, dups,
# vec, rejected, shown, solved_after) and a ref_vectors table: they are left as they are
# and never read. Since 2026-11-15 nobody else sees a student's hint (one board each).

HINT_SOURCES = ("student", "agent")
OUTCOMES = ("rejected", "not_convinced", "convinced")


def default_path():
    path = CONFIG.get("TUTOR_DB", "data/tutor.db")
    return path if os.path.isabs(path) else os.path.join(ROOT, path)


class Store:
    """One connection shared by the web server's threads, behind a lock."""

    def __init__(self, path=None):
        self.path = path or default_path()
        self.db = sqlite3.connect(self.path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        with self.lock:
            self.db.executescript(SCHEMA)
            self._migrate()
            self.db.commit()

    def _migrate(self):
        """Bring a database made by an older version up to date, keeping its rows."""
        for table, column, declaration in MIGRATIONS:
            columns = {row[1] for row in self.db.execute(f"PRAGMA table_info({table})")}
            if column not in columns:
                self.db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {declaration}")
        self.db.execute("UPDATE hints SET source = 'student' WHERE source IS NULL")
        self.db.execute("UPDATE attempts SET external = 0 WHERE external IS NULL")
        self.db.execute("UPDATE texts SET source = 'official' WHERE source IS NULL")
        # Before student_lang there was one home language per student: its attempts and its
        # bridge state belong to that language.
        classroom = CONFIG.get("TUTOR_LANG", "cat")
        self.db.execute(
            "UPDATE attempts SET origin_lang = COALESCE((SELECT CASE WHEN s.lang_origen = ? "
            "THEN '' ELSE s.lang_origen END FROM student s WHERE s.id = attempts.student), '') "
            "WHERE origin_lang IS NULL", (classroom,))
        self.db.execute(
            "INSERT OR IGNORE INTO student_lang SELECT id, lang_origen, elo_origen, etapa, streak "
            "FROM student WHERE COALESCE(lang_origen, '') NOT IN ('', ?)", (classroom,))

    def run(self, sql, args=()):
        with self.lock:
            cursor = self.db.execute(sql, args)
            self.db.commit()
            return cursor

    def rows(self, sql, args=()):
        with self.lock:
            return [dict(row) for row in self.db.execute(sql, args).fetchall()]

    def one(self, sql, args=()):
        found = self.rows(sql, args)
        return found[0] if found else None

    def many(self, sql, rows):
        with self.lock:
            self.db.executemany(sql, rows)
            self.db.commit()

    def close(self):
        with self.lock:
            self.db.close()

    # --- settings measured ahead of time -----------------------------------

    def meta(self, key, default=None):
        row = self.one("SELECT value FROM meta WHERE key = ?", (key,))
        return row["value"] if row else default

    def set_meta(self, key, value):
        self.run("INSERT OR REPLACE INTO meta VALUES (?, ?)", (key, str(value)))

    # --- problems ----------------------------------------------------------

    def problem(self, problem_id):
        row = self.one("SELECT * FROM problems WHERE id = ?", (problem_id,))
        if row:
            row["neighbours"] = json.loads(row["neighbours"] or "[]")
            row["k_probs"] = json.loads(row["k_probs"]) if row["k_probs"] else None
        return row

    def text(self, problem_id, lang):
        """The problem in one language: {"text", "options"}, or None."""
        row = self.one("SELECT text, options, source FROM texts WHERE id = ? AND lang = ?",
                       (problem_id, lang))
        if not row:
            return None
        return {"text": row["text"], "options": json.loads(row["options"] or "{}"), "lang": lang,
                "source": row["source"] or "official"}

    def languages(self):
        return [row["lang"] for row in self.rows("SELECT DISTINCT lang FROM texts ORDER BY lang")]

    def candidates(self, student_id, lang=None):
        """Eligible problems the student hasn't seen: [(id, elo, topic), ...]."""
        sql = ("SELECT p.id, p.elo, p.topic FROM problems p WHERE p.eligible = 1 "
               "AND p.id NOT IN (SELECT problem_id FROM attempts WHERE student = ?)")
        args = [student_id]
        if lang:
            sql += " AND p.id IN (SELECT id FROM texts WHERE lang = ?)"
            args.append(lang)
        return [(row["id"], row["elo"], row["topic"]) for row in self.rows(sql, args)]

    # --- the student -------------------------------------------------------

    def student(self, student_id=1):
        return self.one("SELECT * FROM student WHERE id = ?", (student_id,))

    def save_student(self, student):
        """Save the student, and the bridge state of the home language in use."""
        self.run("INSERT OR REPLACE INTO student (id, name, lang_origen, level, elo_cat, "
                 "elo_origen, etapa, streak) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                 (student["id"], student["name"], student["lang_origen"], student["level"],
                  student["elo_cat"], student["elo_origen"], student["etapa"], student["streak"]))
        lang = student["lang_origen"] or ""
        if lang and lang != CONFIG.get("TUTOR_LANG", "cat"):
            self.run("INSERT OR REPLACE INTO student_lang (student, lang, elo, etapa, streak) "
                     "VALUES (?, ?, ?, ?, ?)", (student["id"], lang, student["elo_origen"],
                                                student["etapa"], student["streak"]))

    def student_lang(self, student_id, lang):
        """The bridge state the student left in one home language, or None."""
        return self.one("SELECT * FROM student_lang WHERE student = ? AND lang = ?",
                        (student_id, lang))

    def student_langs(self, student_id=1):
        return self.rows("SELECT * FROM student_lang WHERE student = ? ORDER BY lang", (student_id,))

    def add_attempt(self, student_id, problem_id, lang, shown, answer, correct, revealed,
                    helps, seconds, external=False, origin_lang="", retry=False):
        self.run("INSERT INTO attempts (student, problem_id, lang, shown, answer, correct, "
                 "revealed, helps, seconds, ts, external, origin_lang, retry) "
                 "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                 (student_id, problem_id, lang, shown, answer, int(correct), int(revealed),
                  helps, seconds, time.time(), int(bool(external)), origin_lang or "",
                  int(bool(retry))))

    def attempts(self, student_id=1, external=False):
        """The student's attempts, oldest first. Bank problems only, unless external=True
        (then only the outside ones): the two never mix in ratings or counts. A problem
        tried again from the failed list (retry = 1) is never counted here."""
        return self.rows("SELECT a.*, p.topic, p.level FROM attempts a "
                         "LEFT JOIN problems p ON p.id = a.problem_id "
                         "WHERE a.student = ? AND COALESCE(a.external, 0) = ? "
                         "AND COALESCE(a.retry, 0) = 0 ORDER BY a.n",
                         (student_id, int(bool(external))))

    def seen(self, student_id, problem_id):
        """Whether the student has already answered this bank problem."""
        return bool(self.one("SELECT 1 AS x FROM attempts WHERE student = ? AND problem_id = ? "
                             "AND COALESCE(external, 0) = 0", (student_id, problem_id)))

    def failed(self, student_id=1):
        """Bank problems whose first answer was wrong, newest first, each one once:
        [{id, topic, level, fixed}], fixed = 1 once a later retry got it right."""
        rows = self.rows(
            "SELECT a.problem_id AS id, p.topic, p.level, COALESCE((SELECT MAX(r.correct) "
            "FROM attempts r WHERE r.student = a.student AND r.problem_id = a.problem_id "
            "AND COALESCE(r.retry, 0) = 1), 0) AS fixed "
            "FROM attempts a JOIN problems p ON p.id = a.problem_id "
            "WHERE a.student = ? AND COALESCE(a.external, 0) = 0 AND COALESCE(a.retry, 0) = 0 "
            "AND a.correct = 0 ORDER BY a.n DESC", (student_id,))
        once = {}
        for row in rows:
            once.setdefault(row["id"], row)
        return list(once.values())

    # --- hints -------------------------------------------------------------

    def add_hint(self, problem_id, student_id, text, delta, convinced, source="student",
                 step=None, lang=None):
        """Store a hint with its text: an agent's (prep/import_hints.py) or a student's.

        The tutor only stores a student's hint when it convinced a Kangaroo that wasn't
        pretending, on a bank problem (docs/PISTES.md). Everything else is a hint event.
        convinced None: not measured yet (an agent hint before kangaroo_agent_hints.py).
        """
        if source not in HINT_SOURCES:
            raise ValueError(f"unknown hint source {source!r}, expected one of {HINT_SOURCES}")
        return self.run("INSERT INTO hints (problem_id, student, text, delta, convinced, ts, "
                        "source, step, lang) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (problem_id, student_id, text, delta,
                         None if convinced is None else int(bool(convinced)), time.time(),
                         source, step, lang)).lastrowid

    def has_hint(self, problem_id, text, source=None):
        sql, args = "SELECT 1 FROM hints WHERE problem_id = ? AND text = ?", [problem_id, text]
        if source:
            sql += " AND source = ?"
            args.append(source)
        return self.one(sql + " LIMIT 1", args) is not None

    def agent_hints(self, problem_id):
        """The agent's hints of a problem, in order: step 1, then step 2 (then any without)."""
        return self.rows("SELECT * FROM hints WHERE problem_id = ? AND source = 'agent' "
                         "ORDER BY COALESCE(step, 99), n", (problem_id,))

    def set_hint_measure(self, n, delta, convinced):
        """The Kangaroo's verdict on a stored hint (prep/kangaroo_agent_hints.py)."""
        self.run("UPDATE hints SET delta = ?, convinced = ? WHERE n = ?",
                 (delta, int(bool(convinced)), n))

    def hints(self, source=None):
        sql, args = "SELECT * FROM hints", []
        if source:
            sql, args = sql + " WHERE source = ?", [source]
        return self.rows(sql + " ORDER BY n", args)

    def student_hints(self):
        """The student's hints that are kept: the ones that convinced the Kangaroo."""
        return self.rows("SELECT n, problem_id, text, delta, ts FROM hints "
                         "WHERE source = 'student' AND convinced = 1 ORDER BY n")

    def add_hint_event(self, problem_id, outcome, reason=None, feigned=False, delta=None):
        if outcome not in OUTCOMES:
            raise ValueError(f"unknown outcome {outcome!r}, expected one of {OUTCOMES}")
        self.run("INSERT INTO hint_events (problem_id, outcome, reason, feigned, delta, ts) "
                 "VALUES (?, ?, ?, ?, ?, ?)",
                 (problem_id, outcome, reason, int(bool(feigned)), delta, time.time()))

    def hint_events(self):
        return self.rows("SELECT * FROM hint_events ORDER BY n")

    def hint_counts(self):
        """{"rejected": {reason: n}, "not_convinced": n, "convinced": n, "feigned": n}."""
        counts = {"rejected": {}, "not_convinced": 0, "convinced": 0, "feigned": 0}
        for row in self.hint_events():
            if row["outcome"] == "rejected":
                counts["rejected"][row["reason"]] = counts["rejected"].get(row["reason"], 0) + 1
            else:
                counts[row["outcome"]] += 1
                counts["feigned"] += int(bool(row["feigned"]))
        return counts

    # --- leaving the Kangaroo ----------------------------------------------
    # Its own table, created on first use, so older databases need no migration.

    TEACH_EXITS = ("CREATE TABLE IF NOT EXISTS teach_exits (n INTEGER PRIMARY KEY AUTOINCREMENT, "
                   "problem_id TEXT, student INTEGER, "
                   "tries INTEGER, "  # hints the student sent before leaving the Kangaroo
                   "ts REAL)")

    def add_teach_exit(self, problem_id, student_id, tries):
        """The student left the Kangaroo before it was convinced or the tries ran out."""
        self.run(self.TEACH_EXITS)
        self.run("INSERT INTO teach_exits (problem_id, student, tries, ts) VALUES (?, ?, ?, ?)",
                 (problem_id, student_id, tries, time.time()))

    def teach_exits(self, student_id=1):
        self.run(self.TEACH_EXITS)
        return self.rows("SELECT * FROM teach_exits WHERE student = ? ORDER BY n", (student_id,))
