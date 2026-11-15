"""The tutor "Ensenya el Cangur": one student, one problem at a time.

The student solves a problem from the M3Kang bank. M3Kang knows the right
answer, so checking is exact. The language model plays the Kangaroo, a weak
classmate: it never explains anything. It only reports how likely it finds
each letter, and the student's job is to move it towards the right one with a
hint that doesn't give the answer away.

The language bridge: a student who is still learning Catalan chooses a home
language, and sees the problems, the options and everything the Kangaroo says in both
languages. As the answers come out right, the home language steps back: first behind
a button, then gone. Only what was prepared ahead of time is shown (M3Kang's own
text or a machine translation, and the templates of copilot/phrases.py): nothing is
translated while the tutor runs.

This file holds the whole flow and no web code: app/server.py only calls
start(), next(), answer(), help(), hint(), reveal(), set_language() and view(). It is
kept apart from predict.py on purpose, so the official run can't change by accident.
"""
import math
import os
import threading
import time

from . import elo, embed, hintsim, langs, leak, led, phrases, topics
from .config import CONFIG, ROOT
from .llm import LETTERS, letter_probs, split_problem
from .pipeline import solve

LANG = CONFIG.get("TUTOR_LANG", "cat")          # the classroom language
MODEL_LANG = CONFIG.get("MODEL_LANG", "eng")    # the language the model reads
NEUTRAL_HINT = "Think carefully."               # the reference: a hint that says nothing
MAX_TRIES = int(CONFIG.get("HINT_MAX_TRIES", 3))
HINT_MAX_CHARS = int(CONFIG.get("HINT_MAX_CHARS", 200))
LANG_NAMES = langs.CATALAN                      # each language's name, in Catalan
PROMOTE_AFTER = 4     # right answers in a row to move to the next language stage
# Answers per language before the language gap is shown. With simulated students
# (sim/students.py), 15 per language still underestimates a real gap by about a
# third, and even at 30 the middle half of students spans some 130 points.
GAP_MIN_ATTEMPTS = 30
DUPLICATE = 0.97      # similarity above which an outside problem is taken as one of the bank
# Always on screen while a student works on a problem from outside the bank (CLAUDE.md)
EXTERNAL_WARNING = phrases.EXTERNAL_WARNING


def kangaroo(probs, label):
    """The Kangaroo always starts wrong: its answer is the likeliest WRONG option.

    Returns {"answer", "sure", "margin"}:
      sure    how sure it is of that answer once the right option is left out
      margin  log P(right) - log P(best wrong). Below zero, it prefers a wrong one.
    """
    wrong = {letter: probs[letter] for letter in LETTERS if letter != label}
    answer = max(wrong, key=lambda letter: (wrong[letter], -LETTERS.index(letter)))
    margin = math.log(max(probs[label], 1e-9)) - math.log(max(wrong[answer], 1e-9))
    return {"answer": answer, "sure": wrong[answer] / max(sum(wrong.values()), 1e-9),
            "margin": margin}


def bar_value(margin):
    """The margin as a bar from 0 to 1. Half way, the Kangaroo changes its mind."""
    return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, margin))))


class Tutor:
    def __init__(self, store, ask=letter_probs, index=None, images_dir=None, background=True,
                 embedder=embed.embed, solver=solve):
        self.store = store
        self.ask = ask                    # letter_probs, or a fake one in the tests
        self.solver = solver              # the harness (pipeline.solve), for outside problems
        self.embedder = embedder          # embeds a student's hint; None switches it off
        self.index = index                # copilot.rag.Index, to place outside problems
        self.images_dir = images_dir or os.path.join(ROOT, "data", "images")
        self.background = background      # False runs model calls inline (tests)
        self.lock = threading.RLock()
        self.model_lock = threading.Lock()   # the server has one slot: one call at a time
        self.student = store.student()
        self.phase = "welcome" if not self.student else "ready"
        self.current = None
        self.outside = None
        self.messages = []
        self.busy = False
        self.failed_topic = None
        self.frame = led.text("?")
        self.frame_version = 0

    # ------------------------------------------------------------------ helpers

    def _say(self, who, text, kind="", own=None, source=None):
        """Say a text as it is (a student's hint, a problem). own: the same text in the
        student's language, shown by the same stage rules as a template; source: who
        translated it (None for an official text)."""
        message = {"who": who, "text": text, "kind": kind}
        origin = self._origin()
        if own and own != text and origin and self.student["etapa"] in (1, 2):
            message["origen"] = {"lang": origin, "text": own, "source": source,
                                 "behind_button": self._behind_button()}
        self.messages.append(message)

    def _render(self, lang, parts):
        """The parts of one message in one language, joined with a space.

        A part is a phrase key, (key, {values}) or ("method", {"topic", "n"}) for a topic's
        method hint. A value may be a function of the language (a topic's name, an option).
        """
        out = []
        for part in parts:
            key, data = (part, {}) if isinstance(part, str) else part
            if key == "method":
                out.append(topics.method_hint(data["topic"], data["n"], lang))
            else:
                data = {k: (v(lang) if callable(v) else v) for k, v in data.items()}
                out.append(phrases.phrase(key, lang, **data))
        return " ".join(out)

    def _tell(self, who, *parts, kind="", bridge=False):
        """Say a template in Catalan, plus the student's language as the stage allows.

        Stage 1: both languages. Stage 2: the student's language sits behind the same
        "see it in my language" button as the problem, or next to the Catalan when this
        problem has no such button. Stage 3: Catalan only. bridge=True is for the messages
        about the bridge itself: always both languages, because they explain the change.

        A phrase that names an answer letter is dropped unless the student has solved the
        problem or asked for the solution: no template can give the answer away early.
        """
        keys = {part if isinstance(part, str) else part[0] for part in parts}
        current = self.current
        if keys & phrases.AFTER_SOLVING and not (
                current and (current["solved"] or current["solution_shown"])):
            return
        message = {"who": who, "text": self._render(LANG, parts), "kind": kind}
        origin = self._origin()
        if origin and (bridge or self.student["etapa"] in (1, 2)):
            translated = self._render(origin, parts)
            if translated != message["text"]:
                message["origen"] = {"lang": origin, "text": translated,
                                     "source": self._provenance(origin, parts),
                                     "behind_button": not bridge and self._behind_button()}
        self.messages.append(message)

    @staticmethod
    def _provenance(lang, parts):
        """Who translated the parts of a message into lang: never a native speaker, so the
        page marks it as machine translation. None when it is all the team's Catalan."""
        found = set()
        for part in parts:
            key = part if isinstance(part, str) else part[0]
            if key == "method":
                found.add(topics.TRANSLATION_SOURCE if lang in topics.TRANSLATIONS_LANGS else None)
            else:
                found.add(phrases.provenance(key, lang))
        found.discard(None)
        return ", ".join(sorted(found)) or None

    def _show(self, frame):
        self.frame = frame
        self.frame_version += 1

    def _spawn(self, function, *args):
        if self.background:
            threading.Thread(target=function, args=args, daemon=True).start()
        else:
            function(*args)

    def _tau(self):
        return float(self.store.meta("tau", CONFIG.get("HINT_TAU", 1.0)))

    def _image(self, problem_id, lang):
        name = f"{problem_id}_{lang}.png"
        return name if os.path.exists(os.path.join(self.images_dir, name)) else None

    def _has_origin(self):
        origin = (self.student or {}).get("lang_origen")
        return bool(origin) and origin != LANG

    def _origin(self):
        """The student's home language, or None when the bridge is off."""
        return self.student["lang_origen"] if self._has_origin() else None

    def _own_text(self, current):
        """Does this problem exist in the student's language (as text or as an image)?"""
        origin = self._origin()
        return bool(origin) and not current["external"] and bool(
            current["origen"] or self._image(current["id"], origin))

    def _behind_button(self):
        """Stage 2: is the student's language behind the button for this problem?"""
        current = self.current
        return bool(current) and self.student["etapa"] == 2 and current["shown"] == "cat" \
            and self._own_text(current)

    def _offered(self):
        """The home languages a student may choose: the ones the Kangaroo speaks, and any
        other language the bank has problems in."""
        return sorted((set(langs.BRIDGE) | set(self.store.languages())) - {LANG})

    def _load_origin(self, current):
        """Attach the problem's text and options in the student's language, if they exist."""
        origin = self._origin()
        text = self.store.text(current["id"], origin) if origin and not current["external"] else None
        current["origen"] = text
        own = (text or {}).get("options") or {}
        current["options_origen"] = own if own and set(own) == set(current["options"]) else None

    # ------------------------------------------------------------------ student

    def start(self, name="", lang_origen="", level=0, reset=False):
        """Create the student, or pick up where they left off."""
        with self.lock:
            if reset or not self.student:
                if reset:
                    self.store.run("DELETE FROM attempts WHERE student = 1")
                    self.store.run("DELETE FROM student_lang WHERE student = 1")
                rating = elo.initial_student(level)
                lang_origen = (lang_origen or "").strip()
                if lang_origen == LANG or lang_origen not in self._offered():
                    lang_origen = ""        # "I already speak Catalan": no bridge, stage 3 at once
                has_origin = bool(lang_origen)
                self.student = {"id": 1, "name": name.strip()[:40], "lang_origen": lang_origen,
                                "level": int(level or 0), "elo_cat": rating, "elo_origen": rating,
                                "etapa": 1 if has_origin else 3, "streak": 0}
                self.store.save_student(self.student)
            self.phase = "ready"
            self.messages = []
            self.current = None
            self._tell("cangur", "hola")
            self._show(led.text("?"))
            return self.view()

    def set_language(self, lang):
        """Switch the home language during the session, or switch the bridge off (lang
        empty or Catalan). Each home language keeps its own rating, stage and streak, so
        coming back to one picks up where the student left it; elo_cat is one for all.

        A problem not answered yet is shown again in the new language. Refused while the
        Kangaroo is thinking.
        """
        with self.lock:
            student = self.student
            lang = (lang or "").strip()
            if lang == LANG:
                lang = ""
            if not student or self.busy or lang == (student["lang_origen"] or "") \
                    or (lang and lang not in self._offered()):
                return self.view()
            self.store.save_student(student)       # keeps the state of the language we leave
            saved = self.store.student_lang(1, lang) if lang else None
            student["lang_origen"] = lang
            if not lang:
                student["etapa"], student["streak"] = 3, 0
            elif saved:
                student["elo_origen"], student["etapa"], student["streak"] = \
                    saved["elo"], saved["etapa"], saved["streak"]
            else:
                student["elo_origen"] = elo.initial_student(student["level"])
                student["etapa"], student["streak"] = 1, 0
            self.store.save_student(student)
            current = self.current
            if current and not current["external"]:
                if self.phase in ("solving", "help") and not current["answered"]:
                    return self.next(current["id"])
                self._load_origin(current)
            return self.view()

    def _presentation(self):
        """What goes on screen, and which rating the answer counts for."""
        if not self._has_origin():
            return "cat", "cat"
        if self.student["etapa"] == 1:
            return "both", "origen"
        answered = len(self.store.attempts())
        return ("origen", "origen") if answered % 3 == 2 else ("cat", "cat")

    def _language_progress(self, correct):
        """Move between the three language stages after an answer."""
        student, current = self.student, self.current
        if not self._has_origin():
            return
        if student["etapa"] == 1:
            student["streak"] = student["streak"] + 1 if correct else 0
            if student["streak"] >= PROMOTE_AFTER:
                student["etapa"], student["streak"] = 2, 0
                self._tell("sistema", "etapa2", bridge=True)
        elif student["etapa"] == 2 and current["shown"] == "cat":
            clean = correct and not current["revealed"]
            student["streak"] = student["streak"] + 1 if clean else 0
            if student["streak"] >= PROMOTE_AFTER:
                student["etapa"], student["streak"] = 3, 0
                self._tell("sistema", "etapa3", bridge=True)
            else:
                # only the answers given with this home language: each one has its own bridge
                recent = [a for a in self.store.attempts() if a["shown"] == "cat"
                          and a["origin_lang"] == student["lang_origen"]][-5:]
                if len(recent) == 5 and sum(a["revealed"] for a in recent) >= 3:
                    student["etapa"], student["streak"] = 1, 0
                    self._tell("sistema", "etapa1_torna", bridge=True)

    # ------------------------------------------------------------------ problems

    def next(self, problem_id=None):
        """Choose the next problem (or load a given one) and start thinking about it."""
        with self.lock:
            if not self.student:
                return self.view()
            shown, counts_for = self._presentation()
            origin = self._origin()
            notice = None       # why the student's language is missing: never switch in silence
            if problem_id is None:
                # Only problems that exist in the classroom language: never switch to the
                # model's language without telling the student
                candidates = self.store.candidates(1, LANG)
                if origin:
                    # in stage 2 a Catalan problem should have the button, where possible
                    own = {found[0] for found in self.store.candidates(1, origin)}
                    translated = [found for found in candidates if found[0] in own]
                    if shown != "cat" and not translated:
                        shown, counts_for, notice = "cat", "cat", "no_queden_origen"
                    elif shown != "cat" or (translated and self.student["etapa"] == 2):
                        candidates = translated
                rating = self.student["elo_origen" if counts_for == "origen" else "elo_cat"]
                chosen = elo.pick(candidates, rating, topic=self.failed_topic)
                if not chosen:
                    self.phase, self.current = "empty", None
                    self.messages = []
                    if self.store.candidates(1):
                        self._tell("sistema", ("no_queden_llengua", {"llengua": lambda lang: (
                            langs.catalan(LANG) if lang == LANG else langs.name(LANG))}))
                    else:
                        self._tell("sistema", "banc_acabat")
                    return self.view()
                problem_id = chosen[0]
            row = self.store.problem(problem_id)
            if not row:
                return self.view()
            model_text = self.store.text(problem_id, MODEL_LANG) or self.store.text(problem_id, LANG)
            cat = self.store.text(problem_id, LANG) or model_text
            origin_text = self.store.text(problem_id, origin) if origin else None
            missing = bool(origin) and not origin_text and not self._image(problem_id, origin)
            if missing and shown != "cat":
                shown, counts_for = "cat", "cat"
            if missing and self.student["etapa"] in (1, 2):
                notice = notice or "no_traduit"
            options = (cat or {}).get("options") or model_text["options"]
            own_options = (origin_text or {}).get("options") or {}
            self.current = {
                "id": problem_id, "row": row, "label": row["label"], "options": options,
                "options_origen": own_options if own_options and set(own_options) == set(options)
                else None,
                "model": {"id": problem_id, "text": model_text["text"],
                          "options": model_text["options"], "level": row["level"]},
                "cat": cat, "origen": origin_text, "shown": shown, "counts_for": counts_for,
                "started": time.time(), "answered": False, "correct": None, "revealed": False,
                "helps": 0, "solution_shown": False, "hint_n": None, "wrong": [],
                "ref": None, "ref_done": False, "teach_wait": False, "tries": 0, "bar": None,
                "taught": False, "solved": False, "external": False,
            }
            precomputed = bool(row.get("k_probs"))
            if precomputed:  # measured ahead of time (prep/kangaroo_baseline.py): answer at once
                self.current["ref"] = kangaroo(row["k_probs"], row["label"])
                self.current["ref_done"] = True
            self.phase, self.outside, self.busy = "solving", None, False
            self.messages = []
            self._tell("cangur", "mira_problema")
            if notice:      # the answer then counts for the Catalan rating
                self._tell("sistema", (notice, {"llengua": langs.name(origin)}), kind="avis")
            self._show(led.text("?"))
            current = self.current
        # Only ask the model when nothing was measured ahead of time. Reading the problem
        # again "to fill the server's cache" saves nothing: with this hybrid model the cache
        # is only reused for an identical prompt (D1), and the call would hold model_lock
        # for ~10 s, so the student's first hint would wait behind it.
        if not precomputed:
            self._spawn(self._reference, current)
        return self.view()

    def _reference(self, current):
        """Read the problem with a hint that says nothing. Also fills the server's cache."""
        try:
            with self.model_lock:
                answer = self.ask(current["model"], hint=NEUTRAL_HINT, timeout=180)
            state = kangaroo(answer["probs"], current["label"])
        except Exception:
            state = None
        with self.lock:
            if state:
                current["ref"] = state
            current["ref_done"] = True
            if self.current is current and current["teach_wait"]:
                current["teach_wait"] = False
                self.busy = False
                self._open_teach()

    def reveal(self):
        """Stage 2: show the problem, its options and what was said in the student's own
        language. It's counted when the problem isn't answered yet; after that, it only
        shows what the Kangaroo says."""
        with self.lock:
            current = self.current
            if current and current["shown"] == "cat" and self._has_origin() \
                    and self.student["etapa"] == 2 and self._own_text(current):
                current["revealed"] = True
            return self.view()

    def _record_first(self, letter, correct):
        """The first answer is the one that counts for the ratings.

        An outside problem is stored apart (external=1) and moves nothing: its answer comes
        from the harness, which can be wrong, and it has no rating to measure against.
        """
        current, student = self.current, self.student
        current["answered"], current["correct"] = True, correct
        if current["external"]:
            self.store.add_attempt(1, current["id"], "cat", current["shown"], letter, correct,
                                   False, current["helps"],
                                   round(time.time() - current["started"], 1), external=True,
                                   origin_lang=self._origin())
            self.failed_topic = None if correct else current["row"]["topic"]
            return
        own = current["counts_for"] == "origen" or current["revealed"]
        key = "elo_origen" if own else "elo_cat"
        origin = self._origin() or ""
        # each home language has its own rating: only its own answers make it settle
        seen = sum(a["lang"] == "origen" and a["origin_lang"] == origin if own else a["lang"] == "cat"
                   for a in self.store.attempts())
        student[key] = elo.update(student[key], current["row"]["elo"], correct, seen)
        self.store.add_attempt(1, current["id"], "origen" if own else "cat", current["shown"],
                               letter, correct, current["revealed"], current["helps"],
                               round(time.time() - current["started"], 1), origin_lang=origin)
        self._language_progress(correct)
        self.store.save_student(student)
        self.failed_topic = None if correct else current["row"]["topic"]

    def answer(self, letter):
        with self.lock:
            current = self.current
            letter = (letter or "").strip().upper()[:1]
            if not current or self.phase not in ("solving", "help") or letter not in tuple(LETTERS) \
                    or current["label"] is None:   # an outside problem still being solved
                return self.view()
            correct = letter == current["label"]
            self._tell("alumne", ("jo_dic", {"letter": letter}))
            if not current["answered"]:
                self._record_first(letter, correct)
            if not correct:
                current["wrong"].append(letter)
                self.phase = "help"
                self._show(led.cross())
                self._tell("sistema", "no_coincideix" if current["external"] else "no_es_aquesta",
                           kind="malament")
                return self.view()
            current["solved"] = True
            self._show(led.tick())
            self._tell("sistema", "correcte", kind="be")
            if current["hint_n"]:
                self.store.hint_solved(current["hint_n"])
            if current["ref"] is None and not current["ref_done"]:
                current["teach_wait"], self.busy = True, True   # the Kangaroo is still reading
                self.phase = "teach"
            else:
                self._open_teach()
            return self.view()

    # ------------------------------------------------------------------ teaching the Kangaroo

    def _open_teach(self):
        current = self.current
        state = current["ref"]
        if state is None:
            self.phase = "done"
            self._tell("sistema", "cangur_no_pensa")
        elif state["margin"] >= 0:
            # The model really prefers the right answer here: nothing to teach
            self.phase = "done"
            self._tell("cangur", ("tambe_be", {"label": current["label"]}))
        else:
            self.phase = "teach"
            current["bar"] = bar_value(state["margin"])
            self._show(led.bar(current["bar"]))
            self._tell("cangur", ("jo_he_dit", {"answer": state["answer"],
                                                "sure": round(100 * state["sure"])}))

    def hint(self, text):
        """The student's hint for the Kangaroo, in any of the bridge's six languages.
        Rejected at once if it gives the answer away.

        The model reads the hint as it was written: nothing is translated while the tutor
        runs, and the prompt says nothing about the hint's language (docs/DECISIONS.md).
        How well a hint in another language moves the Kangaroo has not been measured.
        """
        with self.lock:
            current = self.current
            text = " ".join((text or "").split())
            if not current or self.phase != "teach" or self.busy or not text:
                return self.view()
            self._say("alumne", text)
            statements = [current["model"]["text"], (current["cat"] or {}).get("text"),
                          (current["origen"] or {}).get("text")]
            if current["external"]:
                # The harness's answer may be wrong: the hint may point at no option at all
                reason = leak.check_strict(text, current["options"], statements)
            else:
                # the options in every language on screen: the value may be given in any of them
                reason = None
                for options in (current["options"], current["model"]["options"],
                                current.get("options_origen")):
                    reason = reason or (options and leak.check(text, current["label"], options,
                                                               statements)) or None
            if reason:
                # Kept as data (how often students give the answer away), never shown to anyone.
                # Not for outside problems: hints are stored per bank problem only.
                if not current["external"]:
                    self.store.add_hint(current["id"], 1, text, None, False, rejected=reason,
                                        lang=langs.guess(text))
                self._tell("sistema", "fuita_" + reason, kind="fuita")
                return self.view()
            current["tries"] += 1
            self.busy = True
            self._show(led.text("?"))
        self._spawn(self._teach, current, text)
        return self.view()

    def _teach(self, current, text):
        try:
            with self.model_lock:
                answer = self.ask(current["model"], hint=text, timeout=180)
            state = kangaroo(answer["probs"], current["label"])
        except Exception:
            state = None
        # Only the new hint is embedded; None (no server) stores it without the signals.
        # An outside problem's hints aren't stored: no one else will see that problem.
        signals = None if state is None or current["external"] else hintsim.assess(
            self.store, current["id"], current["row"]["topic"], text, self.embedder)
        with self.lock:
            if self.current is not current:
                return
            self.busy = False
            if state is None:
                self._tell("sistema", "cangur_no_respon")
                current["tries"] -= 1
                return
            delta = state["margin"] - current["ref"]["margin"]
            tau = self._tau()
            convinced = delta > tau and state["margin"] > 0
            if current["external"]:
                pass
            elif signals and signals["duplicate_of"]:
                self.store.hint_duplicate(signals["duplicate_of"], convinced)
            else:
                self.store.add_hint(current["id"], 1, text, delta, convinced,
                                    relevance=(signals or {}).get("relevance"),
                                    vec=(signals or {}).get("vec"), lang=langs.guess(text))
            previous = current.get("bar")
            current["bar"] = bar_value(state["margin"])
            self._show(led.bar(current["bar"], previous))
            if convinced:
                current["taught"] = True
                self.phase = "done"
                self._tell("cangur", ("ara_ho_veig", {"label": current["label"]}),
                           "gracies" if current["external"] else "gracies_companys", kind="be")
            elif current["tries"] >= MAX_TRIES:
                self.phase = "done"
                self._tell("cangur", "espes")
            elif delta > tau / 2:
                self._tell("cangur", "repensant")
            else:
                self._tell("cangur", "no_entes")

    # ------------------------------------------------------------------ help, one rung at a time

    def help(self):
        with self.lock:
            current = self.current
            if not current or self.phase not in ("solving", "help"):
                return self.view()
            current["helps"] += 1
            rung = min(current["helps"], 4)
            topic = current["row"]["topic"]
            if rung == 1:
                example = self._easier_neighbour(current)
                if example:
                    self._tell("sistema", "semblant_facil", kind="pista")
                    self._say("sistema", example[0], "exemple", own=example[1], source=example[2])
                else:
                    rung = 2
            if rung == 2:
                self._tell("sistema", ("es_un_problema_de", {"topic": self._topic(topic)}),
                           ("method", {"topic": topic, "n": 0}), kind="pista")
            elif rung == 3:
                peer = self.store.best_hint(current["id"], hintsim.min_relevance())
                similar = None if peer else self._neighbour_hint(current)
                if peer:
                    current["hint_n"] = peer["n"]
                    self.store.hint_shown(peer["n"])
                    # Only a student's hint is "from a classmate"; the agent's bank is not.
                    # The hint itself stays as it was written: nothing is translated here.
                    lead = "pista_company" if peer.get("source", "student") == "student" else "pista"
                    self._tell("sistema", (lead, {"text": peer["text"]}), kind="pista")
                elif similar:
                    # Not counted as shown or solved: those counts belong to its own problem.
                    self._tell("sistema", ("pista_semblant", {"text": similar["text"]}), kind="pista")
                else:
                    self._tell("sistema", ("method", {"topic": topic, "n": 1}), kind="pista")
            elif rung == 4:
                if not current["answered"]:
                    self._record_first("", False)   # seeing the solution counts as not solved
                current["solution_shown"] = True
                label = current["label"]
                self.phase = "done"
                self._show(led.text(label))
                origin = self._origin()

                def value(lang):    # the option as the student reads it in each language
                    own = current.get("options_origen") if lang == origin else None
                    return (own or current["options"]).get(label, "")
                self._tell("sistema", ("solucio_extern" if current["external"] else "solucio",
                                       {"label": label, "value": value}), kind="solucio")
                if current["external"]:
                    self._tell("sistema", "avis_extern", kind="avis")
            return self.view()

    @staticmethod
    def _topic(key):
        """A topic's name, in whichever language a phrase is being written."""
        return lambda lang: phrases.topic_name(key, lang)

    def _neighbour_hint(self, current):
        """The best hint of a similar problem, if it says nothing about this answer."""
        found = self.store.best_neighbour_hint(current["row"]["neighbours"],
                                               hintsim.min_relevance())
        if not found:
            return None
        statements = [current["model"]["text"], (current["cat"] or {}).get("text"),
                      (current["origen"] or {}).get("text")]
        for options in (current["options"], current["model"]["options"],
                        current.get("options_origen") or current["options"]):
            if current["external"]:
                if leak.check_strict(found["text"], options, statements):
                    return None
            elif leak.check(found["text"], current["label"], options, statements):
                return None
        return found

    def _easier_neighbour(self, current):
        """A similar problem with a lower rating, with its answer: (in Catalan, in the
        student's language or None). Only texts that are already in the database."""
        best = None
        for other_id in current["row"]["neighbours"]:
            other = self.store.problem(other_id)
            if other and other["id"] != current["id"]:
                # An outside problem has no rating: its closest neighbour will do
                if current["row"]["elo"] is not None and other["elo"] < current["row"]["elo"]:
                    best = other
                    break
                best = best or other
        if not best:
            return None
        shown = self.store.text(best["id"], LANG) or self.store.text(best["id"], MODEL_LANG)
        if not shown:
            return None
        options = shown["options"] or (self.store.text(best["id"], MODEL_LANG) or {}).get("options", {})

        def example(text, options, lang):
            answer = phrases.phrase("exemple_resposta", lang, label=best["label"],
                                    value=options.get(best["label"], ""))
            return f"{text['text']}\n{answer}".strip()
        origin = self._origin()
        own = self.store.text(best["id"], origin) if origin else None
        source = (own or {}).get("source")
        return (example(shown, options, LANG),
                example(own, own["options"] or options, origin) if own else None,
                None if source in (None, "official") else source)

    # ------------------------------------------------------------------ problems from outside

    def external(self, text, options=None):
        """A problem that isn't in the bank: the same path as a bank problem.

        Nobody knows its answer for sure, so the harness (pipeline.solve, the same code as
        predict.py) works it out in the background, and that answer plays the label: the
        student's answer is checked against it, the help ladder and the Kangaroo use it.
        The warning stays on screen the whole time. The attempt is stored apart
        (external=1) and moves no rating (docs/DECISIONS.md).

        Without five readable options there's nothing to check: the tutor only places the
        problem (topic, level, similar problems to practise). A near copy of a bank problem
        is that problem.
        """
        with self.lock:
            if not self.student:
                return self.view()
            problem = {"id": "extern", "text": (text or "").strip(), "options": options or {}}
            if not problem["text"]:
                return self.view()
            question, found = split_problem(problem)
            problem = {"id": "extern", "text": question, "options": found}
            self.current, self.phase, self.busy = None, "external", True
            self.outside = {"problem": problem, "topic": topics.classify(question),
                            "level": None, "similar": []}
            self.messages = []
            self._say("alumne", text.strip())
            outside = self.outside
        hits = []
        if self.index is not None:
            try:
                hits = self.index.search(problem, k=5)
            except Exception:
                hits = []
        with self.lock:
            if self.outside is not outside:
                return self.view()
            self.busy = False
            for score, other in hits:
                row = self.store.problem(other["id"])
                if row and row["eligible"] and all(s["id"] != row["id"] for s in outside["similar"]):
                    outside["similar"].append({"id": row["id"], "score": round(score, 3),
                                               "level": row["level"]})
            if hits and hits[0][0] >= DUPLICATE and outside["similar"] \
                    and outside["similar"][0]["id"] == hits[0][1]["id"]:
                self._tell("cangur", "ja_al_banc")
                duplicate = outside["similar"][0]["id"]
            else:
                duplicate = None
                weights = [(max(score, 0.0), other.get("level")) for score, other in hits
                           if other.get("level") is not None]
                if weights and sum(w for w, _ in weights) > 0:
                    outside["level"] = round(sum(w * level for w, level in weights)
                                             / sum(w for w, _ in weights), 1)
                if all(letter in found for letter in LETTERS):
                    current = self._open_external(outside)
                else:
                    current = None
                    self._tell("cangur", ("extern_sense_opcions",
                                          {"topic": self._topic(outside["topic"])}),
                               ("method", {"topic": outside["topic"], "n": 0}))
                    if outside["similar"]:
                        self._tell("sistema", "semblants_practicar")
                    self._show(led.text("?"))
        if duplicate:
            return self.next(duplicate)
        if current:
            self._spawn(self._solve_external, current)
        return self.view()

    def _open_external(self, outside):
        """Make an outside problem the current one, with no label until the harness answers."""
        problem = outside["problem"]
        problem_id = f"extern-{int(time.time() * 1000)}"
        row = {"id": problem_id, "level": outside["level"], "topic": outside["topic"],
               "elo": None, "label": None, "eligible": 1, "k_probs": None,
               "neighbours": [s["id"] for s in outside["similar"]]}
        text = {"text": problem["text"], "options": problem["options"], "lang": LANG}
        self.current = {
            "id": problem_id, "row": row, "label": None, "options": problem["options"],
            "options_origen": None,
            "model": {"id": problem_id, "text": problem["text"], "options": problem["options"],
                      "level": outside["level"]},
            "cat": text, "origen": None, "shown": "cat", "counts_for": "cat",
            "started": time.time(), "answered": False, "correct": None, "revealed": False,
            "helps": 0, "solution_shown": False, "hint_n": None, "wrong": [],
            "ref": None, "ref_done": False, "teach_wait": False, "tries": 0, "bar": None,
            "taught": False, "solved": False, "external": True, "solve_failed": False,
        }
        self.phase, self.outside, self.busy = "solving", None, True
        self._tell("cangur", ("extern_obert" if outside["level"] is None else "extern_obert_nivell",
                              {"topic": self._topic(outside["topic"]), "level": outside["level"]}))
        self._tell("sistema", "avis_extern", kind="avis")
        self._show(led.text("?"))
        return self.current

    def _solve_external(self, current):
        """The harness's answer becomes the label. Then the Kangaroo reads it, as for any problem."""
        label = None
        try:
            with self.model_lock:
                result = self.solver(current["model"])
            # A fallback letter (model down, timeout) is no answer: don't grade against it
            if result["status"] == "ok" and result.get("calls"):
                label = result["answer"]
        except Exception:
            label = None
        with self.lock:
            if self.current is not current:
                return
            self.busy = False
            if label is None:
                current["solve_failed"] = True
                self.phase = "done"
                self._tell("sistema", "extern_no_calcul")
                return
            current["label"] = label
        self._reference(current)

    def leave_teaching(self):
        """The student solved the problem and doesn't want to teach the Kangaroo (any more).

        Solving is the goal, so the student may leave this stage at any time. Not while the
        Kangaroo is thinking: _teach would find another problem and never clear `busy`.
        The exit is stored, so we can see how many students give up on the Kangaroo, and when.
        """
        with self.lock:
            current = self.current
            if self.phase != "teach" or self.busy or not current:
                return self.view()
            if not current["external"]:
                self.store.add_teach_exit(current["id"], 1, current["tries"])
            return self.next()

    # ------------------------------------------------------------------ what the page shows

    def _messages(self):
        """The chat, with each translated hint shown only when the stage allows it."""
        current = self.current
        revealed = bool(current) and (current["shown"] in ("both", "origen") or current["revealed"])
        out = []
        for message in self.messages:
            origen = message.get("origen")
            message = {k: v for k, v in message.items() if k != "origen"}
            if origen and (not origen["behind_button"] or revealed):
                message["origen"] = {"lang": origen["lang"], "text": origen["text"],
                                     "source": origen.get("source")}
            out.append(message)
        return out

    def view(self):
        with self.lock:
            student = self.student
            view = {"phase": self.phase, "busy": self.busy, "messages": self._messages(),
                    "student": None, "problem": None, "outside": None,
                    # languages: what a student may choose; bank_languages: the ones with
                    # problems in the database (the others only have the Kangaroo's phrases)
                    "languages": [LANG] + self._offered(), "bank_languages": self.store.languages(),
                    "classroom_lang": LANG, "lang_names": langs.table(),
                    "hint_max_chars": HINT_MAX_CHARS}
            if student:
                view["student"] = {
                    "name": student["name"], "lang_origen": student["lang_origen"],
                    "etapa": student["etapa"] if self._has_origin() else None,
                    "level": round((student["elo_cat"] - 1000) / 150, 1),
                }
            current = self.current
            if current:
                origin = self._origin()
                own = current["shown"] in ("both", "origen") or current["revealed"]
                solved = current["solved"] or current["solution_shown"]
                own_options = current.get("options_origen")
                bridge_on = bool(origin) and student["etapa"] in (1, 2)
                view["problem"] = {
                    "id": current["id"],
                    "level": "?" if current["row"]["level"] is None else current["row"]["level"],
                    "external": current["external"],
                    "warning": EXTERNAL_WARNING if current["external"] else None,
                    "warning_origen": {"lang": origin, "text": phrases.phrase("avis_extern", origin),
                                       "source": phrases.provenance("avis_extern", origin)}
                    if current["external"] and bridge_on else None,
                    "topic": topics.name(current["row"]["topic"]),
                    "shown": current["shown"],
                    # the letters never change; a problem shown only in the student's
                    # language has its options in that language too
                    "options": own_options if current["shown"] == "origen" and own_options
                    else current["options"],
                    "options_origen": own_options if own and current["shown"] != "origen" else None,
                    # 'official' is M3Kang's own text; anything else is a machine translation
                    "origen_source": (current["origen"] or {}).get("source") if own else None,
                    "cat": current["cat"]["text"] if current["shown"] != "origen" else None,
                    "origen": (current["origen"] or {}).get("text") if own else None,
                    "origen_image": self._image(current["id"], origin) if own and origin else None,
                    "origen_lang": origin if own else None,
                    "can_reveal": bool(origin) and current["shown"] == "cat"
                                  and student["etapa"] == 2 and not current["revealed"]
                                  and self._own_text(current),
                    "wrong": list(current["wrong"]),
                    "label": current["label"] if solved else None,
                    "helps": current["helps"],
                    "tries_left": MAX_TRIES - current["tries"],
                    "bar": current["bar"],
                }
            if self.outside:
                view["outside"] = {"topic": topics.name(self.outside["topic"]),
                                   "level": self.outside["level"],
                                   "similar": self.outside["similar"],
                                   "text": self.outside["problem"]["text"],
                                   "options": self.outside["problem"]["options"]}
            return view

    def led_view(self):
        with self.lock:
            return {"version": self.frame_version, "frame": self.frame}

    def teacher(self):
        """The teacher's summary. It stays on the board, and nobody is labelled."""
        with self.lock:
            student = self.student
            attempts = self.store.attempts()
            # Outside problems are counted apart: they're checked against the harness's answer
            summary = {"student": student, "attempts": len(attempts),
                       "external_attempts": len(self.store.attempts(external=True)), "by_topic": [],
                       "gap": None, "tau": self._tau(),
                       "languages": self.store.student_langs(),   # the bridge, per home language
                       # the embedding (bytes) is not JSON and the teacher does not need it
                       "hints": [{k: v for k, v in h.items() if k != "vec"} for h in self.store.hints()]}
            groups = {}
            for attempt in attempts:
                groups.setdefault(attempt["topic"] or topics.DEFAULT, []).append(attempt["correct"])
            for key, results in sorted(groups.items()):
                summary["by_topic"].append({"topic": topics.name(key), "n": len(results),
                                            "correct": sum(results)})
            if student and self._has_origin():
                own = sum(a["lang"] == "origen" and a["origin_lang"] == student["lang_origen"]
                          for a in attempts)
                classroom = sum(a["lang"] == "cat" for a in attempts)
                summary["gap"] = {
                    "n_origen": own, "n_cat": classroom, "needed": GAP_MIN_ATTEMPTS,
                    "ready": own >= GAP_MIN_ATTEMPTS and classroom >= GAP_MIN_ATTEMPTS,
                    "elo_origen": round(student["elo_origen"]), "elo_cat": round(student["elo_cat"]),
                    "gap": round(student["elo_origen"] - student["elo_cat"]),
                }
            return summary
