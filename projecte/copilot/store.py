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
    origin_lang TEXT            -- the student's home language then ('' for none); NULL: older row
);
CREATE TABLE IF NOT EXISTS hints (
    n INTEGER PRIMARY KEY AUTOINCREMENT,
    problem_id TEXT, student INTEGER, text TEXT,
    delta REAL,             -- how far the hint moved the Kangaroo's margin (NULL: not measured)
    convinced INTEGER,
    shown INTEGER DEFAULT 0, solved_after INTEGER DEFAULT 0,
    ts REAL,
    source TEXT DEFAULT 'student',  -- who wrote it: 'student', 'seed' or 'agent'
    relevance REAL,         -- cosine similarity to the problem's references (NULL: not measured)
    dups INTEGER DEFAULT 0, -- how many later hints were near copies of this one
    vec BLOB,               -- the hint's embedding, float32 (NULL: not embedded)
    rejected TEXT,          -- why the leak filter refused it (NULL: it passed); never shown
    lang TEXT               -- the language the hint is written in, guessed (NULL: not recorded)
);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
-- Embeddings of the texts a student's hint is compared with, made on the laptop
-- (prep/embed_refs.py): kind 'method' (ref: topic key) or 'solution' (ref: problem id).
CREATE TABLE IF NOT EXISTS ref_vectors (
    kind TEXT, ref TEXT, n INTEGER, text TEXT, vec BLOB,
    PRIMARY KEY (kind, ref, n)
);
"""

# Columns added after the first version: (table, column, declaration). Older databases
# get them when they are opened, keeping their rows.
MIGRATIONS = [
    ("hints", "source", "TEXT DEFAULT 'student'"),
    ("hints", "relevance", "REAL"),
    ("hints", "dups", "INTEGER DEFAULT 0"),
    ("hints", "vec", "BLOB"),
    ("hints", "rejected", "TEXT"),
    ("attempts", "external", "INTEGER DEFAULT 0"),
    ("texts", "source", "TEXT DEFAULT 'official'"),
    ("attempts", "origin_lang", "TEXT"),
    ("hints", "lang", "TEXT"),
]

# The order of the hints another student may see: what helped people most, then the
# closest to the problem's references, then how far it moved the Kangaroo, then the oldest.
HINT_ORDER = ("ORDER BY (solved_after + 1.0) / (shown + 2.0) DESC, COALESCE(relevance, -1) DESC, "
              "COALESCE(delta, 0) DESC, n")

# Who wrote a hint: a student teaching the Kangaroo, a hint shipped with the
# database, or the agent's hint bank (prep/import_hints.py).
HINT_SOURCES = ("student", "seed", "agent")


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
        self.db.execute("UPDATE hints SET dups = 0 WHERE dups IS NULL")
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
                    helps, seconds, external=False, origin_lang=""):
        self.run("INSERT INTO attempts (student, problem_id, lang, shown, answer, correct, "
                 "revealed, helps, seconds, ts, external, origin_lang) "
                 "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                 (student_id, problem_id, lang, shown, answer, int(correct), int(revealed),
                  helps, seconds, time.time(), int(bool(external)), origin_lang or ""))

    def attempts(self, student_id=1, external=False):
        """The student's attempts, oldest first. Bank problems only, unless external=True
        (then only the outside ones): the two never mix in ratings or counts."""
        return self.rows("SELECT a.*, p.topic, p.level FROM attempts a "
                         "LEFT JOIN problems p ON p.id = a.problem_id "
                         "WHERE a.student = ? AND COALESCE(a.external, 0) = ? ORDER BY a.n",
                         (student_id, int(bool(external))))

    # --- hints -------------------------------------------------------------

    def add_hint(self, problem_id, student_id, text, delta, convinced, source="student",
                 relevance=None, vec=None, rejected=None, lang=None):
        """Store a hint. rejected: the leak filter's reason, for a hint kept only as data."""
        if source not in HINT_SOURCES:
            raise ValueError(f"unknown hint source {source!r}, expected one of {HINT_SOURCES}")
        if rejected:
            delta, convinced, relevance, vec = None, False, None, None
        return self.run("INSERT INTO hints (problem_id, student, text, delta, convinced, ts, "
                        "source, relevance, vec, rejected, lang) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (problem_id, student_id, text, delta, int(bool(convinced)), time.time(),
                         source, relevance, vec, rejected or None, lang)).lastrowid

    def hint_duplicate(self, n, convinced=False):
        """A near copy of hint n arrived: count it, and keep the better verdict of the two."""
        self.run("UPDATE hints SET dups = dups + 1, convinced = MAX(convinced, ?) WHERE n = ?",
                 (int(bool(convinced)), n))

    def hint_vectors(self, problem_id, source=None):
        """[(n, source, vec blob)] for the embedded hints of a problem."""
        sql = ("SELECT n, source, vec FROM hints WHERE problem_id = ? AND vec IS NOT NULL "
               "AND rejected IS NULL")
        args = [problem_id]
        if source:
            sql += " AND source = ?"
            args.append(source)
        with self.lock:
            return [tuple(row) for row in self.db.execute(sql + " ORDER BY n", args)]

    def set_hint_vector(self, n, vec):
        self.run("UPDATE hints SET vec = ? WHERE n = ?", (vec, n))

    def set_ref_vectors(self, kind, ref, items):
        """Replace the reference vectors of one topic or problem: items = [(text, vec blob)]."""
        with self.lock:
            self.db.execute("DELETE FROM ref_vectors WHERE kind = ? AND ref = ?", (kind, ref))
            self.db.executemany("INSERT INTO ref_vectors VALUES (?, ?, ?, ?, ?)",
                                [(kind, ref, i, text, vec) for i, (text, vec) in enumerate(items)])
            self.db.commit()

    def ref_vectors(self, kind, ref):
        with self.lock:
            return [row[0] for row in self.db.execute(
                "SELECT vec FROM ref_vectors WHERE kind = ? AND ref = ? ORDER BY n", (kind, ref))]

    def has_hint(self, problem_id, text, source=None):
        sql, args = "SELECT 1 FROM hints WHERE problem_id = ? AND text = ?", [problem_id, text]
        if source:
            sql += " AND source = ?"
            args.append(source)
        return self.one(sql + " LIMIT 1", args) is not None

    def best_hint(self, problem_id, min_relevance=None):
        """The hint to show another student, or None.

        A student's hint that convinced the Kangaroo comes first (a student's hint is only
        stored after it passed the leak filter), ranked by the human signal: how often
        people solved the problem after seeing it. The agent's bank is only the fallback
        when there is no such hint. min_relevance, when set, leaves out the student hints
        that were measured and are too far from the problem's references.
        """
        relevant, args = "", [problem_id]
        if min_relevance is not None:
            relevant, args = " AND (relevance IS NULL OR relevance >= ?)", [problem_id, min_relevance]
        found = self.one("SELECT * FROM hints WHERE problem_id = ? AND rejected IS NULL AND "
                         "source != 'agent' AND (convinced = 1 OR (source = 'seed' AND delta IS NULL))"
                         f"{relevant} {HINT_ORDER} LIMIT 1", args)
        return found or self.one("SELECT * FROM hints WHERE problem_id = ? AND rejected IS NULL "
                                 f"AND source = 'agent' {HINT_ORDER} LIMIT 1", (problem_id,))

    def best_neighbour_hint(self, neighbour_ids, min_relevance=None):
        """The best hint of a similar problem: a student's first, then the agent's.

        Neighbours are tried in their stored order (most similar first). The result
        carries "from_problem", so the tutor can say where it comes from.
        """
        fallback = None
        for other in neighbour_ids:
            found = self.best_hint(other, min_relevance)
            if found and found["source"] != "agent":
                return dict(found, from_problem=other)
            if found and fallback is None:
                fallback = dict(found, from_problem=other)
        return fallback

    def hint_shown(self, n):
        self.run("UPDATE hints SET shown = shown + 1 WHERE n = ?", (n,))

    def hint_solved(self, n):
        self.run("UPDATE hints SET solved_after = solved_after + 1 WHERE n = ?", (n,))

    def hints(self):
        return self.rows("SELECT * FROM hints ORDER BY n")

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
