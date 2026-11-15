"""The tutor "Ensenya el Cangur": one student, one problem at a time.

The student solves a problem from the M3Kang bank. M3Kang knows the right
answer, so checking is exact. The language model plays the Kangaroo, a weak
classmate: it never explains anything. It only reports how likely it finds
each letter, and the student's job is to move it towards the right one with a
hint that doesn't give the answer away. The whole flow, in Catalan, is in
docs/PISTES.md at the root of the repository.

This file holds the whole flow and no web code: app/server.py only calls
start(), next(), answer(), help(), hint(), reveal() and view(). It is kept
apart from predict.py on purpose, so the official run can't change by accident.
"""
import math
import os
import threading
import time

from . import elo, hintgen, leak, led, topics
from .config import CONFIG, ROOT
from .llm import LETTERS, letter_probs, split_problem
from .pipeline import solve

LANG = CONFIG.get("TUTOR_LANG", "cat")          # the classroom language
MODEL_LANG = CONFIG.get("MODEL_LANG", "eng")    # the language predict.py's model reads
# The Kangaroo reads the problem and the student's hint in one language: Catalan, the
# hint's language (docs/DECISIONS.md, 2026-11-15). predict.py is not affected.
KANGAROO_LANG = CONFIG.get("KANGAROO_LANG", "cat")
NEUTRAL_HINTS = {"cat": "Pensa-ho bé.", "eng": "Think carefully."}
NEUTRAL_HINT = NEUTRAL_HINTS.get(KANGAROO_LANG, NEUTRAL_HINTS["eng"])   # a hint that says nothing
HELP_RUNGS = 5        # method, hint, another hint, a similar problem, the solution
FEIGNED_BAR = 0.35    # where the bar starts when the Kangaroo only pretends to be wrong
MAX_TRIES = int(CONFIG.get("HINT_MAX_TRIES", 3))
HINT_MAX_CHARS = int(CONFIG.get("HINT_MAX_CHARS", 200))
LANG_NAMES = {"cat": "català", "eng": "anglès", "esp": "castellà", "fra": "francès"}
PROMOTE_AFTER = 4     # right answers in a row to move to the next language stage
# Answers per language before the language gap is shown. With simulated students
# (sim/students.py), 15 per language still underestimates a real gap by about a
# third, and even at 30 the middle half of students spans some 130 points.
GAP_MIN_ATTEMPTS = 30
DUPLICATE = 0.97      # similarity above which an outside problem is taken as one of the bank
# Always on screen while a student works on a problem from outside the bank (CLAUDE.md)
EXTERNAL_WARNING = ("No podem assegurar les respostes per a problemes externs. "
                    "Confirma la solució en fonts oficials o amb el teu professor.")


def kangaroo(probs, label):
    """The Kangaroo always starts wrong: its answer is the likeliest WRONG option.

    The model's probabilities are never changed. When the model prefers a wrong option
    (most problems), that option is simply its answer. When it already prefers the right
    one, the Kangaroo pretends ("feigned"): it says the likeliest wrong option, so the
    student always has someone to teach.

    Returns {"answer", "sure", "margin", "feigned"}:
      sure     the model's real probability of that answer
      margin   log P(right) - log P(best wrong). Below zero, it prefers a wrong one.
      feigned  True when margin >= 0: the Kangaroo is only pretending
    """
    wrong = {letter: probs[letter] for letter in LETTERS if letter != label}
    answer = max(wrong, key=lambda letter: (wrong[letter], -LETTERS.index(letter)))
    margin = math.log(max(probs[label], 1e-9)) - math.log(max(wrong[answer], 1e-9))
    return {"answer": answer, "sure": probs[answer], "margin": margin, "feigned": margin >= 0}


def bar_value(margin):
    """The margin as a bar from 0 to 1. Half way, the Kangaroo changes its mind."""
    return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, margin))))


class Tutor:
    def __init__(self, store, ask=letter_probs, index=None, images_dir=None, background=True,
                 solver=solve, hint_writer=hintgen.generate):
        self.store = store
        self.ask = ask                    # letter_probs, or a fake one in the tests
        self.solver = solver              # the harness (pipeline.solve), for outside problems
        self.hint_writer = hint_writer    # writes an outside problem's hint (copilot/hintgen.py)
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

    def _say(self, who, text, kind=""):
        self.messages.append({"who": who, "text": text, "kind": kind})

    def _say_method(self, topic, n, lead="", who="sistema", kind="pista", reveal=True):
        """A topic's method hint in Catalan, plus the student's language as the stage allows.

        Stage 1: both languages. Stage 2: the student's language sits behind the same
        "see it in my language" button as the problem (reveal=False when there is no
        button, as for an outside problem). Stage 3: Catalan only.
        """
        hint = topics.method_hint(topic, n)
        message = {"who": who, "text": f"{lead}{hint}", "kind": kind}
        student = self.student or {}
        if self._has_origin() and student.get("etapa") in (1, 2):
            origin = student["lang_origen"]
            translated = topics.method_hint(topic, n, origin)
            if translated != hint and (student["etapa"] == 1 or reveal):
                message["origen"] = {"lang": origin, "text": translated,
                                     "behind_button": student["etapa"] == 2}
        self.messages.append(message)

    def _show(self, frame):
        self.frame = frame
        self.frame_version += 1

    def _spawn(self, function, *args):
        if self.background:
            threading.Thread(target=function, args=args, daemon=True).start()
        else:
            function(*args)

    def _kangaroo_reads(self, problem, hint):
        """One call to the Kangaroo, in its language."""
        return self.ask(problem, hint=hint, timeout=180, lang=KANGAROO_LANG)

    def _tau(self):
        return float(self.store.meta("tau", CONFIG.get("HINT_TAU", 1.0)))

    def _image(self, problem_id, lang):
        name = f"{problem_id}_{lang}.png"
        return name if os.path.exists(os.path.join(self.images_dir, name)) else None

    def _has_origin(self):
        origin = (self.student or {}).get("lang_origen")
        return bool(origin) and origin != LANG

    # ------------------------------------------------------------------ student

    def start(self, name="", lang_origen="", level=0, reset=False):
        """Create the student, or pick up where they left off."""
        with self.lock:
            if reset or not self.student:
                if reset:
                    self.store.run("DELETE FROM attempts WHERE student = 1")
                rating = elo.initial_student(level)
                lang_origen = (lang_origen or "").strip()
                has_origin = bool(lang_origen) and lang_origen != LANG
                self.student = {"id": 1, "name": name.strip()[:40], "lang_origen": lang_origen,
                                "level": int(level or 0), "elo_cat": rating, "elo_origen": rating,
                                "etapa": 1 if has_origin else 3, "streak": 0}
                self.store.save_student(self.student)
            self.phase = "ready"
            self.messages = []
            self._say("cangur", "Hola! Soc el Cangur. Resolem problemes junts? "
                                "Aviso: jo m'equivoco força, potser m'hauràs d'ajudar!")
            self._show(led.text("?"))
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
                self._say("sistema", "Ho fas molt bé! A partir d'ara veuràs els problemes en "
                                     "català, amb un botó per veure'ls en la teva llengua.")
        elif student["etapa"] == 2 and current["shown"] == "cat":
            clean = correct and not current["revealed"]
            student["streak"] = student["streak"] + 1 if clean else 0
            if student["streak"] >= PROMOTE_AFTER:
                student["etapa"], student["streak"] = 3, 0
                self._say("sistema", "Ja no et cal el botó: ara els problemes són en català.")
            else:
                recent = [a for a in self.store.attempts() if a["shown"] == "cat"][-5:]
                if len(recent) == 5 and sum(a["revealed"] for a in recent) >= 3:
                    student["etapa"], student["streak"] = 1, 0
                    self._say("sistema", "Tornem a posar les dues llengües de costat una estona.")

    # ------------------------------------------------------------------ problems

    def next(self, problem_id=None):
        """Choose the next problem (or load a given one) and start thinking about it."""
        with self.lock:
            if not self.student:
                return self.view()
            shown, counts_for = self._presentation()
            origin = self.student["lang_origen"] if self._has_origin() else None
            if problem_id is None:
                # Only problems that exist in the classroom language: never switch to the
                # model's language without telling the student
                candidates = self.store.candidates(1, origin if shown != "cat" else LANG)
                if not candidates and shown != "cat":
                    shown, counts_for = "cat", "cat"
                    candidates = self.store.candidates(1, LANG)
                rating = self.student["elo_origen" if counts_for == "origen" else "elo_cat"]
                chosen = elo.pick(candidates, rating, topic=self.failed_topic)
                if not chosen:
                    self.phase, self.current = "empty", None
                    self.messages = []
                    if self.store.candidates(1):
                        self._say("sistema", f"No queden problemes en {LANG_NAMES.get(LANG, LANG)}. "
                                             "Cal preparar el banc en aquesta llengua.")
                    else:
                        self._say("sistema", "No queden problemes per fer. Has acabat el banc!")
                    return self.view()
                problem_id = chosen[0]
            row = self.store.problem(problem_id)
            if not row:
                return self.view()
            # What the Kangaroo reads: its language first (KANGAROO_LANG)
            model_text = (self.store.text(problem_id, KANGAROO_LANG) or self.store.text(problem_id, LANG)
                          or self.store.text(problem_id, MODEL_LANG))
            cat = self.store.text(problem_id, LANG) or model_text
            origin_text = self.store.text(problem_id, origin) if origin else None
            if shown != "cat" and not origin_text and not self._image(problem_id, origin):
                shown, counts_for = "cat", "cat"
            options = (cat or {}).get("options") or model_text["options"]
            self.current = {
                "id": problem_id, "row": row, "label": row["label"], "options": options,
                "model": {"id": problem_id, "text": model_text["text"],
                          "options": model_text["options"], "level": row["level"]},
                "cat": cat, "origen": origin_text, "shown": shown, "counts_for": counts_for,
                "started": time.time(), "answered": False, "correct": None, "revealed": False,
                "helps": 0, "solution_shown": False, "wrong": [], "method_n": 1, "side": None,
                "ref": None, "ref_done": False, "teach_wait": False, "tries": 0, "bar": None,
                "taught": False, "solved": False, "external": False,
                "generated": None, "generated_used": False,
            }
            # Measured ahead of time (prep/kangaroo_baseline.py), in the language the Kangaroo
            # reads now: a database measured in another language is asked again, live.
            precomputed = bool(row.get("k_probs")) and \
                self.store.meta("kangaroo_lang", "eng") == KANGAROO_LANG and \
                model_text.get("lang") == KANGAROO_LANG
            if precomputed:
                self.current["ref"] = kangaroo(row["k_probs"], row["label"])
                self.current["ref_done"] = True
            self.phase, self.outside, self.busy = "solving", None, False
            self.messages = []
            self._say("cangur", "Mira aquest problema! Jo també l'estic pensant… 🤔")
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
                answer = self._kangaroo_reads(current["model"], NEUTRAL_HINT)
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
        """Stage 2: show the problem in the student's own language. It's counted."""
        with self.lock:
            current = self.current
            if current and self.phase in ("solving", "help") and current["shown"] == "cat" \
                    and self._has_origin() and self.student["etapa"] == 2 \
                    and (current["origen"] or self._image(current["id"], self.student["lang_origen"])):
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
                                   round(time.time() - current["started"], 1), external=True)
            self.failed_topic = None if correct else current["row"]["topic"]
            return
        own = current["counts_for"] == "origen" or current["revealed"]
        key = "elo_origen" if own else "elo_cat"
        seen = sum(a["lang"] == ("origen" if own else "cat") for a in self.store.attempts())
        student[key] = elo.update(student[key], current["row"]["elo"], correct, seen)
        self.store.add_attempt(1, current["id"], "origen" if own else "cat", current["shown"],
                               letter, correct, current["revealed"], current["helps"],
                               round(time.time() - current["started"], 1))
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
            self._say("alumne", f"Jo dic la {letter}.")
            if not current["answered"]:
                self._record_first(letter, correct)
            if not correct:
                current["wrong"].append(letter)
                self.phase = "help"
                self._show(led.cross())
                self._say("sistema", "No coincideix amb la resposta que hem calculat. Pots demanar "
                                     "una pista i tornar-ho a provar." if current["external"] else
                          "No és aquesta. Pots demanar una pista i tornar-ho a provar.", "malament")
                return self.view()
            current["solved"] = True
            self._show(led.tick())
            self._say("sistema", "Correcte!", "be")
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
            self._say("sistema", "El Cangur no ha pogut pensar-hi (el model no respon).")
        else:
            # Always a wrong answer. When the model already prefers the right one, the
            # Kangaroo pretends, and its bar starts below half like any doubtful Kangaroo.
            self.phase = "teach"
            current["bar"] = FEIGNED_BAR if state["feigned"] else bar_value(state["margin"])
            self._show(led.bar(current["bar"]))
            self._say("cangur", f"Doncs jo he dit la {state['answer']}… "
                                f"(n'estic un {round(100 * state['sure'])} % segur). "
                                "M'ajudes? Dona'm una pista, però no em diguis la resposta!")

    def hint(self, text):
        """The student's hint for the Kangaroo. Rejected at once if it gives the answer away."""
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
                reason = leak.check(text, current["label"], current["options"], statements)
                if not reason and current["model"]["options"] != current["options"]:
                    reason = leak.check(text, current["label"], current["model"]["options"],
                                        statements)
            if reason:
                # Counted (how often students give the answer away), never with its text.
                # Not for outside problems: their hints are never kept.
                if not current["external"]:
                    self.store.add_hint_event(current["id"], "rejected", reason,
                                              feigned=current["ref"]["feigned"])
                self._say("sistema", leak.MESSAGES[reason], "fuita")
                return self.view()
            current["tries"] += 1
            self.busy = True
            self._show(led.text("?"))
        self._spawn(self._teach, current, text)
        return self.view()

    def _teach(self, current, text):
        try:
            with self.model_lock:
                answer = self._kangaroo_reads(current["model"], text)
            state = kangaroo(answer["probs"], current["label"])
        except Exception:
            state = None
        with self.lock:
            if self.current is not current:
                return
            self.busy = False
            if state is None:
                self._say("sistema", "El Cangur no respon ara mateix. Torna-ho a provar.")
                current["tries"] -= 1
                return
            feigned = current["ref"]["feigned"]
            delta = state["margin"] - current["ref"]["margin"]
            tau = self._tau()
            if feigned:
                # The model already preferred the right answer: delta measures nothing. The
                # hint passed the filter; it convinces if it didn't confuse the model.
                convinced = state["margin"] > 0
            else:
                convinced = delta > tau and state["margin"] > 0
            if not current["external"]:
                # Only numbers, except the text of a hint that really convinced the Kangaroo
                self.store.add_hint_event(current["id"], "convinced" if convinced else "not_convinced",
                                          feigned=feigned, delta=None if feigned else delta)
                if convinced and not feigned:
                    self.store.add_hint(current["id"], 1, text, delta, True)
            previous = current.get("bar")
            current["bar"] = bar_value(state["margin"])
            self._show(led.bar(current["bar"], previous))
            if convinced:
                current["taught"] = True
                self.phase = "done"
                self._say("cangur", f"Aaah, ara ho veig! Llavors és la {current['label']}. "
                                    "Gràcies!", "be")
            elif current["tries"] >= MAX_TRIES:
                self.phase = "done"
                self._say("cangur", "Avui estic espès… Deixem-ho aquí. Gràcies per provar-ho!")
            elif not feigned and delta > tau / 2:
                self._say("cangur", "Mmm, m'ho estic repensant, però encara no ho veig clar. "
                                    "M'ho expliques d'una altra manera?")
            else:
                self._say("cangur", "No t'he entès… M'ho pots explicar d'una altra manera?")

    # ------------------------------------------------------------------ help, one rung at a time

    def help(self):
        """One rung of help per click (docs/PISTES.md):

        1. the topic and a method hint
        2. a hint: the agent's first (bank) or the model's (outside problem)
        3. another hint: the agent's second, or a method hint
        4. a similar, easier problem WITHOUT its answer: the student may try it
        5. the solution (counts as not solved)
        Whatever is missing falls back to the topic's next method hint.
        """
        with self.lock:
            current = self.current
            if not current or self.phase not in ("solving", "help"):
                return self.view()
            current["helps"] += 1
            rung = min(current["helps"], HELP_RUNGS)
            topic = current["row"]["topic"]
            if rung == 1:
                self._say_method(topic, 0, f"És un problema de «{topics.name(topic)}». ")
            elif rung in (2, 3):
                hint = self._rung_hint(current, rung)
                if hint:
                    self._say("sistema", f"{'Una pista' if rung == 2 else 'Una altra pista'}: "
                                         f"«{hint}»", "pista")
                else:
                    self._say_method(topic, current["method_n"])
                    current["method_n"] += 1
            elif rung == 4:
                side = self._easier_neighbour(current)
                if side:
                    current["side"] = side
                    self._say("sistema", "Prova aquest problema semblant i més fàcil. "
                                         "Quan el responguis, et diré la resposta.", "pista")
                else:
                    rung = current["helps"] = HELP_RUNGS
            if rung == HELP_RUNGS:
                if not current["answered"]:
                    self._record_first("", False)   # seeing the solution counts as not solved
                current["solution_shown"] = True
                label = current["label"]
                self.phase = "done"
                self._show(led.text(label))
                lead = "Segons els nostres càlculs, la resposta" if current["external"] else "La resposta"
                self._say("sistema", f"{lead} és la {label}) "
                                     f"{current['options'].get(label, '')}.", "solucio")
                if current["external"]:
                    self._say("sistema", EXTERNAL_WARNING, "avis")
            return self.view()

    def _rung_hint(self, current, rung):
        """The hint of rung 2 or 3, or None (then a method hint is shown)."""
        if current["external"]:
            # The model's hint, whichever rung comes after it is ready
            if current["generated"] and not current["generated_used"]:
                current["generated_used"] = True
                return current["generated"]
            return None
        hints = self.store.agent_hints(current["id"])
        return hints[rung - 2]["text"] if len(hints) > rung - 2 else None

    def _easier_neighbour(self, current):
        """A similar problem with a lower rating, to try: {"id", "text", "options", "label"}."""
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
        if not options or best["label"] not in options:
            return None
        return {"id": best["id"], "text": shown["text"], "options": options, "label": best["label"],
                "answer": None, "open": False}

    def side_answer(self, letter):
        """The student's answer to the similar problem of rung 4. Then its answer is shown."""
        with self.lock:
            current = self.current
            side = current and current["side"]
            letter = (letter or "").strip().upper()[:1]
            if not side or side["open"] or letter not in side["options"]:
                return self.view()
            side["answer"], side["open"] = letter, True
            right = side["label"]
            if letter == right:
                self._say("sistema", "Correcte! Ara torna al teu problema: és semblant.", "be")
            else:
                self._say("sistema", f"No: la resposta era la {right}) {side['options'][right]}. "
                                     "Torna al teu problema amb aquesta idea.", "malament")
            return self.view()

    def side_reveal(self):
        """The answer of the similar problem, without trying it."""
        with self.lock:
            current = self.current
            side = current and current["side"]
            if not side or side["open"]:
                return self.view()
            side["open"] = True
            right = side["label"]
            self._say("sistema", f"La resposta del problema semblant és la {right}) "
                                 f"{side['options'][right]}.", "exemple")
            return self.view()

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
                self._say("cangur", "Aquest problema ja el tinc al meu banc! Fem-lo junts.")
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
                    self._say_method(outside["topic"], 0,
                                     "No he pogut llegir les cinc opcions, A) … E), o sigui que no "
                                     "et puc corregir la resposta. Sembla un problema de "
                                     f"«{topics.name(outside['topic'])}». ", who="cangur", kind="",
                                     reveal=False)
                    if outside["similar"]:
                        self._say("sistema", "Aquí tens problemes semblants del banc per practicar.")
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
            "model": {"id": problem_id, "text": problem["text"], "options": problem["options"],
                      "level": outside["level"]},
            "cat": text, "origen": None, "shown": "cat", "counts_for": "cat",
            "started": time.time(), "answered": False, "correct": None, "revealed": False,
            "helps": 0, "solution_shown": False, "wrong": [], "method_n": 1, "side": None,
            "ref": None, "ref_done": False, "teach_wait": False, "tries": 0, "bar": None,
            "taught": False, "solved": False, "external": True, "solve_failed": False,
            "generated": None, "generated_used": False,
        }
        self.phase, self.outside, self.busy = "solving", None, True
        level = "" if outside["level"] is None else f" (nivell aproximat: {outside['level']})"
        self._say("cangur", "Aquest problema no és al meu banc. Sembla de "
                            f"«{topics.name(outside['topic'])}»{level}. Calculo la resposta "
                            "mentre el llegeixes, i després el fem com els altres.")
        self._say("sistema", EXTERNAL_WARNING, "avis")
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
                self._say("sistema", "No he pogut calcular la resposta d'aquest problema (el model "
                                     "no respon). Prova'n un altre o tornem als problemes del banc.")
                return
            current["label"] = label
        self._reference(current)
        self._write_hint(current)

    def _write_hint(self, current):
        """An outside problem's hint, written by the model after the harness and the Kangaroo.

        One similar bank problem is the example: its Catalan statement and its first agent
        hint. No neighbour with a hint, a failed filter or no answer: the rung shows a
        method hint instead (docs/DECISIONS.md, 2026-11-15).
        """
        if not hintgen.enabled():
            return
        example = None
        for other_id in current["row"]["neighbours"]:
            hints = self.store.agent_hints(other_id)
            text = self.store.text(other_id, LANG)
            if hints and text:
                example = (text["text"], hints[0]["text"])
                break
        if not example:
            return
        try:
            with self.model_lock:
                hint, _reason = self.hint_writer(current["model"], *example)
        except Exception:
            hint = None
        with self.lock:
            if self.current is current and hint:
                current["generated"] = hint

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
                message["origen"] = {"lang": origen["lang"], "text": origen["text"]}
            out.append(message)
        return out

    def view(self):
        with self.lock:
            student = self.student
            view = {"phase": self.phase, "busy": self.busy, "messages": self._messages(),
                    "student": None, "problem": None, "outside": None,
                    "languages": self.store.languages(), "classroom_lang": LANG,
                    "hint_max_chars": HINT_MAX_CHARS}
            if student:
                view["student"] = {
                    "name": student["name"], "lang_origen": student["lang_origen"],
                    "etapa": student["etapa"] if self._has_origin() else None,
                    "level": round((student["elo_cat"] - 1000) / 150, 1),
                }
            current = self.current
            if current:
                origin = student["lang_origen"] if self._has_origin() else None
                own = current["shown"] in ("both", "origen") or current["revealed"]
                solved = current["solved"] or current["solution_shown"]
                view["problem"] = {
                    "id": current["id"],
                    "level": "?" if current["row"]["level"] is None else current["row"]["level"],
                    "external": current["external"],
                    "warning": EXTERNAL_WARNING if current["external"] else None,
                    "topic": topics.name(current["row"]["topic"]),
                    "shown": current["shown"], "options": current["options"],
                    "cat": current["cat"]["text"] if current["shown"] != "origen" else None,
                    "origen": (current["origen"] or {}).get("text") if own else None,
                    "origen_image": self._image(current["id"], origin) if own and origin else None,
                    "origen_lang": origin if own else None,
                    "can_reveal": bool(origin) and current["shown"] == "cat"
                                  and student["etapa"] == 2 and not current["revealed"]
                                  and self.phase in ("solving", "help"),
                    "wrong": list(current["wrong"]),
                    "label": current["label"] if solved else None,
                    "helps": current["helps"],
                    "rungs": HELP_RUNGS,
                    "side": None if not current["side"] else {
                        "text": current["side"]["text"], "options": current["side"]["options"],
                        "answer": current["side"]["answer"], "open": current["side"]["open"],
                        "label": current["side"]["label"] if current["side"]["open"] else None},
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
                       # only the hints that convinced the Kangaroo keep their text; the rest
                       # are counts (docs/PISTES.md)
                       "hints": self.store.student_hints(), "hint_counts": self.store.hint_counts()}
            groups = {}
            for attempt in attempts:
                groups.setdefault(attempt["topic"] or topics.DEFAULT, []).append(attempt["correct"])
            for key, results in sorted(groups.items()):
                summary["by_topic"].append({"topic": topics.name(key), "n": len(results),
                                            "correct": sum(results)})
            if student and self._has_origin():
                own = sum(a["lang"] == "origen" for a in attempts)
                classroom = sum(a["lang"] == "cat" for a in attempts)
                summary["gap"] = {
                    "n_origen": own, "n_cat": classroom, "needed": GAP_MIN_ATTEMPTS,
                    "ready": own >= GAP_MIN_ATTEMPTS and classroom >= GAP_MIN_ATTEMPTS,
                    "elo_origen": round(student["elo_origen"]), "elo_cat": round(student["elo_cat"]),
                    "gap": round(student["elo_origen"] - student["elo_cat"]),
                }
            return summary
