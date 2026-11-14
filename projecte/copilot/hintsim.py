"""How a student's hint relates to what we already have, by embedding similarity.

On the laptop, prep/embed_refs.py stores the vectors of the references: the agent's
hints of each problem, the short solutions, and the Catalan method hints of each
topic. On the board only the student's new hint is embedded (one call to the bge
server), and three signals come out of the cosine similarity:

  relevance   the highest similarity to the problem's references and its topic's
              method hints. Stored with the hint and used to break ties.
  duplicate   a hint of the same problem at least HINT_DUP_SIM similar: the new
              one is not stored again, the old one counts a duplicate.
  (reuse)     the tutor shows a similar problem's hint when a problem has none;
              that uses the stored neighbours, not a new embedding.

A caveat to keep in mind: bge-small is an English model and the hints are in
Catalan, so these similarities are rough. Relevance never rejects a hint unless
HINT_MIN_REL is set in config.env (empty by default), and both thresholds must be
calibrated on real hints before anyone trusts them. If the embedding server does
not answer, the hint is stored without the signals: the student is never blocked.

Standard library only.
"""
import array
import math

from .config import CONFIG


def to_blob(vector):
    """A vector as float32 bytes, to store in SQLite."""
    return array.array("f", vector).tobytes()


def from_blob(blob):
    values = array.array("f")
    values.frombytes(blob)
    return list(values)


def cosine(a, b):
    if not a or not b or len(a) != len(b):
        return None
    dot = sum(x * y for x, y in zip(a, b))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else None


def setting(name, default=None):
    """A float from config.env; empty or missing gives the default (None: switched off)."""
    value = str(CONFIG.get(name, "") or "").strip()
    try:
        return float(value) if value else default
    except ValueError:
        return default


def dup_threshold():
    return setting("HINT_DUP_SIM", 0.92)


def min_relevance():
    return setting("HINT_MIN_REL", None)


def references(store, problem_id, topic):
    """The stored vectors a hint for this problem is compared with."""
    blobs = [vec for _n, _source, vec in store.hint_vectors(problem_id, source="agent")]
    blobs += store.ref_vectors("solution", problem_id)
    blobs += store.ref_vectors("method", topic)
    return [from_blob(blob) for blob in blobs if blob]


def assess(store, problem_id, topic, text, embedder, timeout=10):
    """Embed one hint and compare it: {"vec", "relevance", "duplicate_of", "similarity"}.

    Returns None when there is no embedder or the embedding server fails, so the
    caller stores the hint as before.
    """
    if embedder is None:
        return None
    try:
        vector = list(embedder([text], timeout=timeout)[0])
    except Exception:
        return None
    scores = [cosine(vector, ref) for ref in references(store, problem_id, topic)]
    scores = [s for s in scores if s is not None]
    duplicate_of, closest = None, None
    threshold = dup_threshold()
    for n, _source, blob in store.hint_vectors(problem_id):
        score = cosine(vector, from_blob(blob))
        if score is not None and (closest is None or score > closest):
            closest = score
            if threshold is not None and score >= threshold:
                duplicate_of = n
    return {"vec": to_blob(vector), "relevance": max(scores) if scores else None,
            "duplicate_of": duplicate_of, "similarity": closest}
