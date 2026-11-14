#!/usr/bin/env python3
"""Tests that run anywhere, without the board and without M3Kang.

    python3 -m unittest discover -s tests -v

They use invented problems (tests/demo_data.py) and a stand-in for the model
servers (tests/fake_llama.py). They check that the code does what it says:
they say nothing about how well the real model answers.
"""
import csv
import json
import os
import subprocess
import sys
import tempfile
import unittest
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import demo_data  # noqa: E402
import fake_llama  # noqa: E402
from copilot import calib, elo, led, leak, llm, pipeline, topics  # noqa: E402
from copilot.config import CONFIG  # noqa: E402
from copilot.store import Store  # noqa: E402
from copilot.tutor import Tutor, bar_value, kangaroo  # noqa: E402

TRAIN, VAL = demo_data.make(90)
SAMPLE = {"id": "s1", "level": 0,
          "text": "Anna has 3 bags with 4 apples in each bag. She eats 2 apples. How many are left?",
          "options": {"A": "8", "B": "9", "C": "10", "D": "12", "E": "14"}, "label": "C"}


def english(rows):
    return [r for r in rows if r["language"] == "eng"]


class WithServers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = fake_llama.Model()
        cls.model.learn(TRAIN + VAL + [SAMPLE])
        _model, cls.llm, cls.embed = fake_llama.start(cls.model)
        cls.url = f"http://127.0.0.1:{cls.llm.server_port}/v1/chat/completions"
        cls.saved = dict(CONFIG)

    @classmethod
    def tearDownClass(cls):
        cls.llm.shutdown()
        cls.embed.shutdown()
        CONFIG.clear()
        CONFIG.update(cls.saved)

    def setUp(self):
        CONFIG.clear()
        CONFIG.update(self.saved)
        self.model.shape, self.model.fail_next = "openai", 0

    def ask(self, problem, **kwargs):
        kwargs.pop("timeout", None)
        return llm.letter_probs(problem, url=self.url, timeout=10, **kwargs)


class Prompt(unittest.TestCase):
    def test_baseline_prompt_is_unchanged(self):
        text = llm.build_messages(SAMPLE)[-1]["content"]
        self.assertTrue(text.endswith("E) 14\nAnswer:"))
        self.assertNotIn("Hint", text)

    def test_hint_goes_after_the_problem(self):
        plain = llm.build_messages(SAMPLE)[-1]["content"]
        hinted = llm.build_messages(SAMPLE, hint="Count  them\nall")[-1]["content"]
        shared = plain[:-len("\nAnswer:")]
        self.assertTrue(hinted.startswith(shared))    # so the cache is reused
        self.assertTrue(hinted.endswith("Hint from a classmate: Count them all\nAnswer:"))

    def test_rotation_moves_the_options(self):
        text = llm.format_problem(SAMPLE, order=pipeline.rotation(2))
        self.assertIn("A) 10", text)   # the original C
        self.assertIn("D) 8", text)    # the original A

    def test_options_written_in_the_text(self):
        question, options = llm.split_problem({"text": "What is 2+2? A) 3 B) 4 C) 5 D) 6 E) 7"})
        self.assertEqual(question, "What is 2+2?")
        self.assertEqual(options["B"], "4")
        self.assertEqual(llm.split_problem({"text": "A) and B) only"})[1], {})

    def test_parse_shapes(self):
        top = [{"token": "D", "logprob": -0.5}, {"token": " D", "logprob": -3.0},
               {"token": "The", "logprob": -2.0}, {"token": "A", "logprob": -1.5}]
        for response in ({"choices": [{"logprobs": {"content": [{"top_logprobs": top}]}}]},
                         {"completion_probabilities": [{"top_logprobs": top}]}):
            probs, found = llm.parse_letter_probs(response, "D")
            self.assertEqual(found, 2)
            self.assertAlmostEqual(sum(probs.values()), 1.0)
            self.assertGreater(probs["D"], probs["A"])
            self.assertGreater(probs["A"], probs["B"])   # B wasn't listed: it gets the floor
        probs, found = llm.parse_letter_probs({"choices": [{}]}, "B")
        self.assertEqual((found, max(probs, key=probs.get)), (0, "B"))


class Solver(WithServers):
    def test_probabilities_and_rotation(self):
        answer = self.ask(SAMPLE)
        self.assertEqual(answer["found"], 5)
        self.assertAlmostEqual(sum(answer["probs"].values()), 1.0, places=6)
        rotated = self.ask(SAMPLE, order=pipeline.rotation(2))
        self.assertEqual(set(rotated["probs"]), set("ABCDE"))
        self.assertAlmostEqual(sum(rotated["probs"].values()), 1.0, places=6)

    def test_always_one_letter(self):
        for problem in english(VAL)[:5] + [{"id": "n", "text": "No options here"}]:
            result = pipeline.solve(problem, llm_url=self.url)
            self.assertIn(result["answer"], tuple("ABCDE"))
            self.assertEqual(result["status"], "ok")

    def test_no_options_uses_the_prior_without_the_model(self):
        before = len(self.model.calls)
        result = pipeline.solve({"id": "n", "text": "No options here"}, llm_url=self.url)
        self.assertEqual((result["answer"], result["calls"]), (CONFIG["FALLBACK_ANSWER"], 0))
        self.assertEqual(len(self.model.calls), before)

    def test_rotations_make_more_calls_and_respect_the_clock(self):
        CONFIG["PREDICT_ROTATIONS"] = "3"
        self.assertEqual(pipeline.solve(SAMPLE, llm_url=self.url)["calls"], 4)
        # Just enough time for the first call: answer, don't fail, stay inside the limit
        limit = pipeline.MARGIN + pipeline.estimate_seconds(len(SAMPLE["text"]) + 30) + 0.5
        result = pipeline.solve(SAMPLE, llm_url=self.url, time_limit=limit)
        self.assertEqual(result["status"], "ok")
        self.assertGreaterEqual(result["calls"], 1)
        self.assertLessEqual(result["seconds"], limit)
        # No time for even one call: the prior, with no call at all
        result = pipeline.solve(SAMPLE, llm_url=self.url, time_limit=pipeline.MARGIN)
        self.assertEqual((result["calls"], result["stage"], result["status"]), (0, "prior", "ok"))

    def test_survives_a_dead_or_broken_server(self):
        dead = pipeline.solve(SAMPLE, llm_url="http://127.0.0.1:9/v1/chat/completions")
        self.assertIn(dead["answer"], tuple("ABCDE"))
        self.assertTrue(dead["status"].startswith("error"))
        self.model.fail_next = 1
        broken = pipeline.solve(SAMPLE, llm_url=self.url)
        self.assertTrue(broken["status"].startswith("error"))
        CONFIG["PREDICT_ROTATIONS"] = "2"
        self.model.fail_next = 0
        first = pipeline.solve(SAMPLE, llm_url=self.url)
        self.assertEqual(first["status"], "ok")

    def test_same_answers_every_time(self):
        CONFIG["PREDICT_ROTATIONS"] = "2"
        runs = [[pipeline.solve(p, llm_url=self.url)["answer"] for p in english(VAL)] for _ in range(2)]
        self.assertEqual(runs[0], runs[1])

    def test_without_probabilities_it_still_answers(self):
        self.model.shape = "none"
        answer = self.ask(SAMPLE)
        self.assertEqual(answer["found"], 0)
        self.assertIn(pipeline.solve(SAMPLE, llm_url=self.url)["answer"], tuple("ABCDE"))

    def test_bias_correction_changes_the_weights(self):
        plain = self.ask(SAMPLE)["probs"]
        corrected = self.ask(SAMPLE, bias={"A": 0.2, "B": 0.2, "C": 0.2, "D": 0.8, "E": 0.2})["probs"]
        self.assertLess(corrected["D"], plain["D"])

    def test_cache_only_reads_the_hint(self):
        self.ask(SAMPLE, hint="Think carefully.")
        self.ask(SAMPLE, hint="Count all the apples first.")
        first, second = self.model.calls[-2:]
        self.assertLess(second["prompt_n"], 20)


class Calibration(unittest.TestCase):
    def test_level_from_the_field_or_the_id(self):
        self.assertEqual(calib.problem_level({"id": "x", "level": 3}), 3)
        self.assertEqual(calib.problem_level({"id": "lvl-5_2019_7"}), 5)
        self.assertEqual(calib.problem_level({"id": "lvl-5_2019_7", "level": None}), 5)
        self.assertEqual(calib.problem_level({"id": "lvl-12_2019_7", "level": ""}), 12)
        self.assertIsNone(calib.problem_level({"id": "sample-1"}))
        self.assertIsNone(calib.problem_level({}))

    def test_prior_by_level_when_level_is_missing(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "priors.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"global": "D", "by_level": {"2": "B"}}, f)
            saved, calib.PRIORS_PATH = calib.PRIORS_PATH, path
            try:
                self.assertEqual(calib.prior_letter({"id": "lvl-2_2015_3"}), "B")
                self.assertEqual(calib.prior_letter({"id": "lvl-4_2015_3"}), "D")
                self.assertEqual(calib.prior_letter({"id": "outside"}), "D")
            finally:
                calib.PRIORS_PATH = saved

    def test_batch_bias_and_rescore(self):
        # A model that loves position A: two problems, the second seen rotated
        loves_a = {"A": 0.6, "B": 0.1, "C": 0.1, "D": 0.1, "E": 0.1}
        order = pipeline.rotation(2)
        rotated = {order[i]: loves_a[l] for i, l in enumerate("ABCDE")}
        results = [{"full": True, "passes": [("ABCDE", dict(loves_a))]},
                   {"full": True, "passes": [(order, rotated)]},
                   {"full": False, "passes": [("ABCDE", {"A": 0, "B": 0, "C": 0, "D": 0, "E": 1})]}]
        bias = calib.batch_bias(results)
        self.assertEqual(bias["n"], 2)
        self.assertAlmostEqual(bias["A"], 0.6)
        self.assertIsNone(calib.batch_bias([{"full": False, "passes": []}]))
        # Here the bias is the whole answer, so after the correction every letter ties
        fixed = pipeline.rescore(dict(results[0]), bias)
        self.assertAlmostEqual(fixed["probs"]["A"], 0.2)
        self.assertEqual(fixed["answer"], "A")  # ties go to the earlier letter
        leaning = {"full": True, "passes": [("ABCDE", {"A": 0.5, "B": 0.3, "C": 0.1, "D": 0.05,
                                                      "E": 0.05})]}
        self.assertEqual(pipeline.rescore(leaning, bias)["answer"], "B")


class Guardrails(WithServers):
    def test_clean_problem(self):
        clean = pipeline.clean_problem({"id": 3, "text": None,
                                        "options": {"a": " 1 ", "B)": 2, "C": "", "F": "x", "D": None}})
        self.assertEqual((clean["id"], clean["text"]), ("3", ""))
        self.assertEqual(clean["options"], {"A": "1", "B": "2"})
        self.assertEqual(pipeline.clean_problem("nonsense")["options"], {})

    def test_fit_text_keeps_start_and_end(self):
        short = "How many apples? " * 3
        self.assertEqual(pipeline.fit_text(short, 40, 30), short)
        long = "START " + "word " * 3000 + " QUESTION?"
        fitted = pipeline.fit_text(long, 40, 30)
        self.assertTrue(fitted.startswith("START") and fitted.endswith("QUESTION?"))
        self.assertLessEqual(pipeline.estimate_seconds(len(fitted) + 40), 30)
        self.assertIsNone(pipeline.fit_text(long, 40, 5))

    def test_long_problem_is_shortened_not_timed_out(self):
        problem = dict(SAMPLE, text="Story. " * 2000 + SAMPLE["text"])
        result = pipeline.solve(problem, llm_url=self.url)
        self.assertEqual((result["status"], result["shortened"], result["stage"]), ("ok", True, "model"))

    def test_garbage_still_gets_a_letter(self):
        for problem in (None, "text", {"options": {"A": 1}}, {"id": "x", "text": 5}):
            result = pipeline.solve(problem, llm_url=self.url)
            self.assertIn(result["answer"], tuple("ABCDE"))

    def test_batch_mode_solves_without_the_file_bias(self):
        CONFIG["PREDICT_DEBIAS"] = "batch"
        self.assertIsNone(calib.letter_bias())


class Expressions(WithServers):
    def test_evaluate_is_safe_and_exact(self):
        from copilot import mathexpr
        self.assertEqual(mathexpr.evaluate("2 + 3 * 4"), 14)
        self.assertEqual(mathexpr.evaluate("(1 + 2)^2 - -1"), 10)
        for bad in ("10 / 0", "2^100", "__import__('os')", "2 +", "", None, "9" * 200, "1e400"):
            self.assertIsNone(mathexpr.evaluate(bad), bad)

    def test_option_values(self):
        from copilot import mathexpr
        cases = {"12": 12, "3,5": 3.5, "1/2": 0.5, "25%": 25, "12 cm\u00b2": 12, "\u22123": -3,
                 "1 000": 1000, "10 \u20ac": 10}
        for text, value in cases.items():
            self.assertAlmostEqual(mathexpr.option_value(text), value, msg=text)
        for text in ("3 and 4", "a triangle", "x + 1", "", None):
            self.assertIsNone(mathexpr.option_value(text), text)
        options = {"A": "8", "B": "9", "C": "10", "D": "12", "E": "1/2"}
        self.assertTrue(mathexpr.numeric(options))
        self.assertFalse(mathexpr.numeric({"A": "red", "B": "blue", "C": "1", "D": "2", "E": "3"}))
        self.assertEqual(mathexpr.match(0.5, options), "E")
        self.assertIsNone(mathexpr.match(11, options))
        self.assertIsNone(mathexpr.match(8, {"A": "8", "B": "8.0"}))

    def test_expression_stage(self):
        CONFIG["PREDICT_EXPRESSION"] = "on"
        result = pipeline.solve(SAMPLE, llm_url=self.url)
        self.assertEqual(result["calls"], 2)
        self.assertTrue(result["expr"])
        if result["expr_letter"]:
            self.assertEqual((result["answer"], result["stage"]), (result["expr_letter"], "expr"))
        # Off by default: one call, as before
        CONFIG["PREDICT_EXPRESSION"] = "off"
        self.assertEqual(pipeline.solve(SAMPLE, llm_url=self.url)["calls"], 1)
        # Options that aren't numbers: no expression call
        CONFIG["PREDICT_EXPRESSION"] = "on"
        words = dict(SAMPLE, options={l: w for l, w in zip("ABCDE", ("red", "blue", "green", "pink", "grey"))})
        self.assertEqual(pipeline.solve(words, llm_url=self.url)["calls"], 1)

    def test_vote_and_override(self):
        result = {"probs": {"A": 0.5, "B": 0.2, "C": 0.1, "D": 0.1, "E": 0.1}, "answer": "A",
                  "expr_letter": "B"}
        CONFIG["PREDICT_EXPR_MODE"] = "override"
        self.assertEqual(pipeline.apply_expression(dict(result))["answer"], "B")
        CONFIG["PREDICT_EXPR_MODE"], CONFIG["PREDICT_EXPR_WEIGHT"] = "vote", "2"
        self.assertEqual(pipeline.apply_expression(dict(result))["answer"], "A")   # 0.4 < 0.5
        CONFIG["PREDICT_EXPR_WEIGHT"] = "4"
        self.assertEqual(pipeline.apply_expression(dict(result))["answer"], "B")   # 0.8 > 0.5

    def test_expression_failure_keeps_the_letter(self):
        CONFIG["PREDICT_EXPRESSION"] = "on"
        plain = pipeline.solve(dict(SAMPLE, id="e1"), llm_url=self.url)
        self.model.fail_next = 0
        self.assertIn(plain["answer"], tuple("ABCDE"))
        self.assertEqual(plain["status"], "ok")


class Leaks(unittest.TestCase):
    TEXT = [SAMPLE["text"]]

    def check(self, hint, label="C", options=None, text=None):
        return leak.check(hint, label, options or SAMPLE["options"], text or self.TEXT)

    def test_leaks_are_caught(self):
        for hint, reason in [("És la C, segur", "lletra"), ("La resposta és C)", "lletra"),
                             ("opció c i ja està", "lletra"), ("Jo crec que C", "lletra"),
                             ("En queden 10 al final", "valor"), ("En queden deu al final", "valor"),
                             ("Mira la tercera opció", "posicio"), ("És la del mig", "posicio")]:
            self.assertEqual(self.check(hint), reason, hint)

    def test_clean_hints_pass(self):
        for hint in ["Primer calcula quantes pomes hi ha en total i després resta.",
                     "Multiplica les bosses per les pomes de cada bossa.",
                     "Calcula 3 per 4 i treu-ne les que es menja.",
                     "A la primera bossa hi ha 4 pomes, i a les altres també."]:
            self.assertIsNone(self.check(hint), hint)

    def test_value_already_in_the_statement_is_allowed(self):
        options = {"A": "2", "B": "3", "C": "4", "D": "5", "E": "6"}
        self.assertIsNone(self.check("Fixa't que cada bossa té 4 pomes.", "C", options))

    def test_letter_used_as_a_name_in_the_problem(self):
        text = ["In triangle ABC, the point D is on side BC. How long is AD?"]
        self.assertIsNone(self.check("Mira el triangle que forma D amb els altres punts.", "D",
                                     {"A": "1", "B": "2", "C": "3", "D": "7", "E": "5"}, text))

    def test_length(self):
        self.assertEqual(self.check("Suma"), "curta")
        self.assertEqual(self.check("pensa " * 60), "llarga")

    def test_evaluate(self):
        report = leak.evaluate([
            {"hint": "És la C", "label": "C", "options": SAMPLE["options"], "text": SAMPLE["text"], "leak": True},
            {"hint": "Multiplica i després resta.", "label": "C", "options": SAMPLE["options"],
             "text": SAMPLE["text"], "leak": False},
            {"hint": "És el doble de cinc, oi?", "label": "C", "options": SAMPLE["options"],
             "text": SAMPLE["text"], "leak": True}])   # an indirect leak: the filter misses it
        self.assertEqual((report["leaks_caught"], report["leaks_missed"], report["clean_accepted"]),
                         (1, 1, 1))


class Ratings(unittest.TestCase):
    def test_expected(self):
        self.assertAlmostEqual(elo.expected(1000, 1000), 0.6)
        self.assertGreater(elo.expected(1400, 1000), 0.9)
        self.assertLess(elo.expected(600, 1000), 0.3)
        self.assertGreater(elo.expected(0, 3000), 0.2 - 1e-9)   # never below guessing

    def test_update_and_pick(self):
        student, problem = elo.update(1000, 1000, True)
        self.assertGreater(student, 1000)
        self.assertLess(problem, 1000)
        candidates = [("a", 600, "x"), ("b", 870, "y"), ("c", 1500, "x")]
        self.assertEqual(elo.pick(candidates, 1000)[0], "b")
        self.assertEqual(elo.pick(candidates + [("d", 880, "x")], 1000, topic="x")[0], "d")
        self.assertIsNone(elo.pick([], 1000))

    def test_tram(self):
        self.assertEqual([elo.tram(n, 30) for n in (1, 10, 11, 20, 21, 30)], [0, 0, 1, 1, 2, 2])

    def test_kangaroo_always_starts_wrong(self):
        probs = {"A": 0.30, "B": 0.10, "C": 0.15, "D": 0.40, "E": 0.05}
        state = kangaroo(probs, "C")
        self.assertEqual(state["answer"], "D")
        self.assertAlmostEqual(state["sure"], 0.40 / 0.85)
        self.assertAlmostEqual(state["margin"], -0.9808, places=3)
        sure = kangaroo({"A": 0.05, "B": 0.05, "C": 0.8, "D": 0.05, "E": 0.05}, "C")
        self.assertNotEqual(sure["answer"], "C")      # even when the model prefers the right one
        self.assertGreater(sure["margin"], 0)
        self.assertAlmostEqual(bar_value(0), 0.5)

    def test_topics_and_led(self):
        self.assertEqual(topics.classify("A square has a perimeter of 36 cm."), "geometria")
        self.assertEqual(topics.classify("Is any number even in the evening?"), "nombres")
        self.assertEqual(topics.classify("zzz"), topics.DEFAULT)
        for frame in (led.tick(), led.cross(), led.text("C"), led.text("12"), led.bar(0.5), led.bar(2)):
            self.assertEqual((len(frame), {len(row) for row in frame}), (8, {13}))
            self.assertTrue(all(0 <= v <= 7 for row in frame for v in row))
        self.assertEqual(sum(v == 7 for v in led.bar(1.0)[3]), 13)


def build_db(path, embed_port):
    """Run the real preparation script on the invented problems."""
    folder = os.path.dirname(path)
    for name, rows in (("train.jsonl", TRAIN), ("val.jsonl", VAL)):
        with open(os.path.join(folder, name), "w", encoding="utf-8") as f:
            f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
    env = dict(os.environ, EMBED_PORT=str(embed_port), PYTHONIOENCODING="utf-8")
    return subprocess.run([sys.executable, os.path.join(ROOT, "prep", "build_tutor_db.py"),
                           "--inputs", os.path.join(folder, "train.jsonl"),
                           os.path.join(folder, "val.jsonl"), "--db", path],
                          capture_output=True, text=True, encoding="utf-8", env=env, cwd=ROOT)


class TutorFlow(WithServers):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.folder = tempfile.TemporaryDirectory()
        cls.template = os.path.join(cls.folder.name, "tutor.db")
        cls.build = build_db(cls.template, cls.embed.server_port)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        try:
            cls.folder.cleanup()
        except OSError:
            pass

    def setUp(self):
        super().setUp()
        self.assertEqual(self.build.returncode, 0, self.build.stderr)
        self.path = os.path.join(self.folder.name, f"{self.id().split('.')[-1]}.db")
        with open(self.template, "rb") as source, open(self.path, "wb") as target:
            target.write(source.read())
        self.store = Store(self.path)
        self.addCleanup(self.store.close)
        self.tutor = Tutor(self.store, ask=self.ask, background=False,
                           images_dir=self.folder.name)

    def wrong_letter(self):
        label = self.tutor.current["label"]
        return next(letter for letter in "ABCDE" if letter != label)

    def test_database(self):
        usable = self.store.one("SELECT COUNT(*) AS n FROM problems WHERE eligible = 1")["n"]
        self.assertEqual(usable, 90)
        self.assertEqual(self.store.languages(), ["cat", "eng", "esp"])
        row = self.store.problem(english(TRAIN)[0]["id"])
        self.assertEqual(len(row["neighbours"]), 5)
        self.assertEqual(self.store.meta("neighbours"), "embeddings")

    def test_wrong_then_help_ladder(self):
        self.tutor.start("Test", "", 1)
        view = self.tutor.next()
        self.assertEqual(view["phase"], "solving")
        self.assertIsNone(view["problem"]["label"])            # the answer is never sent early
        before = self.tutor.student["elo_cat"]
        view = self.tutor.answer(self.wrong_letter())
        self.assertEqual(view["phase"], "help")
        self.assertLess(self.tutor.student["elo_cat"], before)
        self.assertIsNone(view["problem"]["label"])
        kinds = []
        for _ in range(4):
            view = self.tutor.help()
            kinds.append(view["messages"][-1]["kind"])
        self.assertEqual(kinds, ["exemple", "pista", "pista", "solucio"])
        self.assertEqual(view["phase"], "done")
        self.assertEqual(view["problem"]["label"], self.tutor.current["label"])
        self.assertEqual(len(self.store.attempts()), 1)         # one attempt, however many clicks

    def teachable(self):
        """Go through problems until the Kangaroo has something to learn."""
        for _ in range(40):
            self.tutor.next()
            view = self.tutor.answer(self.tutor.current["label"])
            if view["phase"] == "teach":
                return view
        self.fail("the fake model never preferred a wrong option")

    def test_teach_the_kangaroo(self):
        self.tutor.start("Test", "", 1)
        view = self.teachable()
        current = self.tutor.current
        self.assertLess(current["ref"]["margin"], 0)
        self.assertNotEqual(current["ref"]["answer"], current["label"])
        self.assertLess(view["problem"]["bar"], 0.5)

        calls = len(self.model.calls)
        view = self.tutor.hint(f"És la {current['label']}")       # a leak: rejected, no model call
        self.assertEqual(view["messages"][-1]["kind"], "fuita")
        self.assertEqual((len(self.model.calls), current["tries"]), (calls, 0))

        self.store.set_meta("tau", "0.5")
        words = sorted(fake_llama.words(current["model"]["text"]))[:3]
        view = self.tutor.hint("Fixa't en: " + " ".join(words))    # the fake likes shared words
        hint = self.store.hints()[-1]
        self.assertGreater(hint["delta"], 0.5)
        self.assertEqual(len(self.model.calls), calls + 1)
        self.assertEqual(self.model.calls[-1]["hint"], "Fixa't en: " + " ".join(words))
        self.assertLess(self.model.calls[-1]["prompt_n"], 40)      # only the hint was read
        self.assertGreater(view["problem"]["bar"], bar_value(current["ref"]["margin"]))
        if hint["convinced"]:
            self.assertEqual(view["phase"], "done")

    def test_nonsense_hint_does_not_convince(self):
        self.tutor.start("Test", "", 1)
        self.teachable()
        self.store.set_meta("tau", "0.5")
        for n in range(3):
            view = self.tutor.hint(f"zzzz qqqq xxxx {n} kkkk")
        self.assertEqual(view["phase"], "done")                    # three tries, then it stops
        self.assertTrue(all(not h["convinced"] for h in self.store.hints()))

    def test_peer_hint_reaches_the_next_student(self):
        self.tutor.start("Test", "", 1)
        self.tutor.next()
        problem_id = self.tutor.current["id"]
        self.store.add_hint(problem_id, 1, "Compta-les per grups.", 2.0, True)
        self.tutor.answer(self.wrong_letter())
        for _ in range(3):
            view = self.tutor.help()
        self.assertIn("Compta-les per grups.", view["messages"][-1]["text"])
        self.tutor.answer(self.tutor.current["label"])
        hint = self.store.hints()[0]
        self.assertEqual((hint["shown"], hint["solved_after"]), (1, 1))

    def test_language_stages_and_two_ratings(self):
        view = self.tutor.start("Test", "esp", 1)
        self.assertEqual(view["student"]["etapa"], 1)
        for _ in range(4):                                         # stage 1: both languages
            view = self.tutor.next()
            self.assertEqual(view["problem"]["shown"], "both")
            self.assertTrue(view["problem"]["cat"] and view["problem"]["origen"])
            self.tutor.answer(self.tutor.current["label"])
        self.assertEqual(self.tutor.student["etapa"], 2)
        self.assertGreater(self.tutor.student["elo_origen"], self.tutor.student["elo_cat"])
        shown = []
        for _ in range(6):                                         # stage 2: one in three in Spanish
            view = self.tutor.next()
            shown.append(view["problem"]["shown"])
            if view["problem"]["shown"] == "cat":
                self.assertTrue(view["problem"]["can_reveal"])
                self.assertIsNone(view["problem"]["origen"])
            self.tutor.answer(self.wrong_letter())
        self.assertEqual(shown.count("origen"), 2)
        view = self.tutor.next()
        if view["problem"]["shown"] != "cat":
            self.tutor.answer(self.wrong_letter())
            view = self.tutor.next()
        view = self.tutor.reveal()                                 # the button counts
        self.assertEqual(view["problem"]["origen_lang"], "esp")
        self.tutor.answer(self.tutor.current["label"])
        last = self.store.attempts()[-1]
        self.assertEqual((last["revealed"], last["lang"], last["shown"]), (1, "origen", "cat"))
        gap = self.tutor.teacher()["gap"]
        self.assertFalse(gap["ready"])                             # too few answers to say

    def test_outside_problem_never_leads_with_an_answer(self):
        self.tutor.start("Test", "", 1)
        view = self.tutor.external("How many legs do 7 spiders have? A) 42 B) 49 C) 56 D) 63 E) 70")
        self.assertEqual(view["phase"], "external")
        self.assertIsNone(view["outside"]["guess"])
        self.assertFalse(any("diria" in m["text"] for m in view["messages"]))
        view = self.tutor.external_guess()
        self.assertIn(view["outside"]["guess"], tuple("ABCDE"))
        self.assertEqual(view["messages"][-1]["kind"], "avis")     # the warning comes with it
        self.assertEqual(self.tutor.next()["phase"], "solving")

    def test_model_down(self):
        def dead(problem, **kwargs):
            raise OSError("down")
        tutor = Tutor(self.store, ask=dead, background=False)
        tutor.start("Test", "", 1)
        tutor.next()
        view = tutor.answer(tutor.current["label"])
        self.assertEqual(view["phase"], "done")                    # the tutor carries on


class Scripts(WithServers):
    """predict.py and eval.py as the jury runs them, against the stand-in servers."""

    def run_script(self, *args, cwd, **settings):
        env = dict(os.environ, LLM_PORT=str(self.llm.server_port),
                   EMBED_PORT=str(self.embed.server_port), PYTHONIOENCODING="utf-8", **settings)
        return subprocess.run([sys.executable, *args], capture_output=True, text=True,
                              encoding="utf-8", env=env, cwd=cwd)

    def test_predict_and_eval(self):
        with tempfile.TemporaryDirectory() as folder:
            data = os.path.join(folder, "val.jsonl")
            with open(data, "w", encoding="utf-8") as f:
                f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in VAL)
            out = os.path.join(folder, "predictions.csv")
            done = self.run_script(os.path.join(ROOT, "predict.py"), "--input", data,
                                   "--output", out, cwd=ROOT)
            self.assertEqual(done.returncode, 0, done.stderr)
            with open(out, encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(list(rows[0]), ["id", "language", "answer", "seconds", "status"])
            self.assertEqual(len(rows), len(VAL))
            self.assertTrue(all(r["answer"] in tuple("ABCDE") and r["status"] == "ok" for r in rows))

            done = self.run_script(os.path.join(ROOT, "eval.py"), "--input", data, "--limit", "12",
                                   "--rotations", "1", "--name", "test", cwd=folder)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertIn("By topic", done.stdout)
            with open(os.path.join(folder, "results", "ablations.csv"), encoding="utf-8") as f:
                log = list(csv.DictReader(f))
            self.assertEqual((log[0]["name"], log[0]["n"]), ("test", "12"))
            self.assertIn("rotations=1", log[0]["settings"])
            self.assertTrue(log[0]["machine"])

            done = self.run_script(os.path.join(ROOT, "eval.py"), "--input", data, "--limit", "12",
                                   "--rotations", "1", "--debias", "batch", "--name", "batch",
                                   "--expression", "on", cwd=folder, PREDICT_BATCH_MIN="5")
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertIn("Letter bias from batch", done.stdout)
            self.assertIn("Expression stage: asked", done.stdout)
            with open(os.path.join(folder, "results", "ablations.csv"), encoding="utf-8") as f:
                log = list(csv.DictReader(f))
            self.assertIn("debias=batch", log[1]["settings"])
            self.assertIn("expression=on/override", log[1]["settings"])
            with open(os.path.join(folder, log[1]["details"]), encoding="utf-8") as f:
                details = list(csv.DictReader(f))
            self.assertEqual(len(details), 12)
            self.assertTrue(all(r["answer"] in tuple("ABCDE") for r in details))

    def test_predict_survives_bad_input(self):
        with tempfile.TemporaryDirectory() as folder:
            data = os.path.join(folder, "test.jsonl")
            good = english(VAL)[:6]
            with open(data, "w", encoding="utf-8") as f:
                f.write(json.dumps(good[0]) + "\n")
                f.write('{"id": "broken-1", "text": "no closing brace"\n')
                f.write("[1, 2, 3]\n\n")
                f.write(json.dumps({"id": 7, "text": None, "options": ["x"]}) + "\n")
                f.writelines(json.dumps(r) + "\n" for r in good[1:])
            out = os.path.join(folder, "predictions.csv")
            done = self.run_script(os.path.join(ROOT, "predict.py"), "--input", data, "--output", out,
                                   "--rag", "1", "--index", os.path.join(folder, "missing.db"),
                                   cwd=ROOT, PREDICT_DEBIAS="batch", PREDICT_BATCH_MIN="3")
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertIn("No retrieval", done.stderr)
            self.assertIn("Letter bias from batch", done.stderr)
            with open(out, encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 9)
            self.assertEqual([r["id"] for r in rows[1:4]], ["broken-1", "line-3", "7"])
            self.assertTrue(all(r["answer"] in tuple("ABCDE") for r in rows))
            self.assertFalse(os.path.exists(out + ".tmp"))

    def test_web_server_endpoints(self):
        from app.server import make_handler
        from http.server import ThreadingHTTPServer
        import threading
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "tutor.db")
            self.assertEqual(build_db(path, self.embed.server_port).returncode, 0)
            store = Store(path)
            tutor = Tutor(store, ask=self.ask, background=False)
            server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(tutor, folder))
            threading.Thread(target=server.serve_forever, daemon=True).start()
            base = f"http://127.0.0.1:{server.server_port}"

            def call(route, body=None):
                data = None if body is None else json.dumps(body).encode()
                request = urllib.request.Request(base + route, data=data,
                                                 headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(request, timeout=10) as response:
                    return json.loads(response.read())

            try:
                self.assertEqual(call("/api/state")["phase"], "welcome")
                self.assertEqual(call("/api/start", {"name": "T", "level": 0, "lang": ""})["phase"], "ready")
                view = call("/api/next", {})
                self.assertEqual(view["phase"], "solving")
                self.assertNotIn(tutor.current["label"], json.dumps(view["problem"]["label"]))
                self.assertEqual(len(call("/api/led")["frame"]), 8)
                self.assertIn(call("/api/answer", {"letter": "A"})["phase"], ("help", "teach", "done"))
                self.assertEqual(call("/api/teacher")["attempts"], 1)
                with urllib.request.urlopen(base + "/", timeout=10) as page:
                    html = page.read().decode("utf-8")
                self.assertIn("Ensenya el Cangur", html)
                self.assertNotIn("http://", html.replace("http://127.0.0.1", ""))   # nothing from the internet
                self.assertNotIn("https://", html)
            finally:
                server.shutdown()
                store.close()


if __name__ == "__main__":
    unittest.main()
