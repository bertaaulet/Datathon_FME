#!/usr/bin/env python3
"""Tests that run anywhere, without the board and without M3Kang.

    python3 -m unittest discover -s tests -v

They use invented problems (tests/demo_data.py) and a stand-in for the model
servers (tests/fake_llama.py). They check that the code does what it says:
they say nothing about how well the real model answers.
"""
import contextlib
import csv
import io
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
from copilot import calib, elo, hintsim, langs, led, leak, llm, phrases, pipeline, topics  # noqa: E402
from copilot.config import CONFIG  # noqa: E402
from copilot.store import Store  # noqa: E402
from copilot.tutor import NEUTRAL_HINT, Tutor, bar_value, kangaroo  # noqa: E402

# The tests don't depend on the machine translations of the phrases (phrases_mt.json):
# every phrase and topic gets a stand-in "translation", the Catalan text with a language tag.
REAL_PHRASES, REAL_TOPICS = phrases.load()
for _key, _by_lang in phrases.PHRASES.items():
    for _lang in phrases.LANGS:
        if _lang != "cat":
            _by_lang[_lang] = f"‹{_lang}› {_by_lang['cat']}"
phrases.TOPIC_NAMES.clear()
phrases.TOPIC_NAMES.update({_key: {_lang: f"‹{_lang}› {_name}" for _lang in phrases.LANGS if _lang != "cat"}
                            for _key, _name in topics.NAMES.items()})

TRAIN, VAL = demo_data.make(90)
SAMPLE = {"id": "s1", "level": 0,
          "text": "Anna has 3 bags with 4 apples in each bag. She eats 2 apples. How many are left?",
          "options": {"A": "8", "B": "9", "C": "10", "D": "12", "E": "14"}, "label": "C"}


def english(rows):
    return [r for r in rows if r["language"] == "eng"]


def fake_embedder(texts, timeout=None):
    """A deterministic bag of words, 64 numbers per text: enough to test the plumbing.

    It says nothing about how bge-small would score the same texts.
    """
    out = []
    for text in texts:
        vector = [0.0] * 64
        for word in leak.plain(text).split():
            word = "".join(ch for ch in word if ch.isalnum())
            if word:
                vector[sum(map(ord, word)) % 64] += 1.0
        out.append(vector)
    return out


def dead_embedder(texts, timeout=None):
    raise OSError("no embedding server")


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


class Retrieval(WithServers):
    class FakeIndex:
        def __init__(self, hits, fail=False):
            self.hits, self.fail = hits, fail

        def search(self, problem, k=1, exclude_id=None):
            if self.fail:
                raise OSError("embedding server down")
            return [h for h in self.hits if h[1]["id"] != exclude_id][:k]

    def solved(self, pid, value="10", options=True):
        opts = {"A": "8", "B": "9", "C": value, "D": "12", "E": "14"} if options else {}
        return {"id": pid, "language": "eng", "text": f"Problem {pid}: how many?",
                "options": opts, "label": "C"}

    def test_answer_format_shows_question_and_value_only(self):
        CONFIG["PREDICT_RAG_FORMAT"] = "answer"
        messages = llm.build_messages(SAMPLE, [self.solved("x1", "77")])
        self.assertEqual(len(messages), 2)   # system + one user message, no fake replies
        text = messages[1]["content"]
        self.assertIn("Problem x1: how many?\nCorrect answer: 77", text)
        self.assertNotIn("D) 12\nAnswer: C", text)
        self.assertTrue(text.endswith("Answer:"))
        self.assertIn("A) 8", text)        # the new problem keeps its options
        CONFIG["PREDICT_RAG_FORMAT"] = "letter"
        self.assertEqual(len(llm.build_messages(SAMPLE, [self.solved("x1")])), 4)

    def test_retrieve_skips_same_problem_copies_and_unknown_values(self):
        CONFIG["PREDICT_RAG_FORMAT"] = "answer"
        hits = [(0.99, self.solved("copy")), (0.95, self.solved("s1")),
                (0.90, self.solved("noopt", options=False)), (0.85, self.solved("s2")),
                (0.80, dict(self.solved("s1"), language="cat"))]
        index = self.FakeIndex(hits)
        got = pipeline.retrieve(index, {"id": "s1", "text": "q"}, 2)
        self.assertEqual([p["id"] for _s, p in got], ["s2"])  # not itself, not a copy, not without options
        got = pipeline.retrieve(index, {"id": "new", "text": "q"}, 2)
        self.assertEqual([p["id"] for _s, p in got], ["s1", "s2"])
        self.assertEqual(pipeline.retrieve(self.FakeIndex(hits, fail=True), SAMPLE, 1), [])
        self.assertEqual(pipeline.retrieve(None, SAMPLE, 1), [])

    def test_solve_with_examples_and_a_broken_index(self):
        index = self.FakeIndex([(0.9, self.solved("s9"))])
        result = pipeline.solve(SAMPLE, index=index, k=1, llm_url=self.url)
        self.assertEqual((result["status"], result["retrieved"]), ("ok", "s9:0.90"))
        broken = pipeline.solve(SAMPLE, index=self.FakeIndex([], fail=True), k=1, llm_url=self.url)
        self.assertEqual((broken["status"], broken["calls"]), ("ok", 1))

    def test_robust_bias_has_a_floor(self):
        bias = calib.robust({"A": 0.26, "B": 0.095, "C": 0.005, "D": 0.55, "E": 0.088, "n": 60})
        self.assertAlmostEqual(sum(bias[l] for l in "ABCDE"), 1.0)
        self.assertGreater(bias["C"], 0.04)
        self.assertEqual(bias["n"], 60)

    def test_split_is_by_id_level_and_repeatable(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("split_data", os.path.join(ROOT, "prep", "split_data.py"))
        split_data = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(split_data)
        levels = {f"lvl-{l}_20{y:02d}_{n}": l for l in range(4) for y in range(10) for n in range(5)}
        first = split_data.split_ids(levels, 0.15, 0.15, "42")
        self.assertEqual(first, split_data.split_ids(levels, 0.15, 0.15, "42"))
        for level in range(4):
            names = [first[i] for i, l in levels.items() if l == level]
            self.assertEqual((names.count("val"), names.count("test")), (8, 8))  # 15% of 50, rounded


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

    def test_strict_filter_names_no_option(self):
        # Outside problems: the harness's answer may be wrong, so no option at all may be named
        strict = lambda hint: leak.check_strict(hint, SAMPLE["options"], self.TEXT)  # noqa: E731
        for letter in "BCDE":
            self.assertEqual(strict(f"Jo crec que és la {letter}, segur"), "lletra", letter)
        for letter, value in SAMPLE["options"].items():
            self.assertIsNotNone(strict(f"Al final en queden {value}, compta-ho"), letter)
        self.assertEqual(strict("Mira la segona opció"), "posicio")
        self.assertIsNone(strict("Primer calcula quantes pomes hi ha en total i després resta."))
        self.assertEqual(strict("Resta"), "curta")

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
        self.assertIsNone(self.check("先乘后减。"))                    # short in characters, not in words
        self.assertEqual(self.check("乘"), "curta")

    def test_numbers_written_in_words(self):
        for words, value in [
                ("vint-i-tres", "23"), ("noranta-set", "97"), ("dos-cents cinc", "205"),
                ("treinta y dos", "32"), ("veintitrés", "23"), ("twenty-three", "23"),
                ("three hundred and twelve", "312"),
                ("dix-sept", "17"), ("soixante et onze", "71"), ("quatre-vingts", "80"),
                ("quatre-vingt-dix", "90"), ("quatre-vingt-dix-sept", "97"), ("trois cent vingt", "320"),
                ("ثلاثة وعشرون", "23"), ("أحد عشر", "11"), ("سبعة وتسعون", "97"), ("مئة وخمسة", "105"),
                ("٩٧", "97"), ("۲۳", "23"), ("９７", "97"),
                ("二十三", "23"), ("九十七", "97"), ("一百零五", "105"), ("两千", "2000"), ("十二", "12")]:
            self.assertIn(value, leak.numbers(words), words)
        # numbers next to each other aren't added up, and an article or an ordinal is no number
        self.assertEqual(leak.numbers("suma tres i quatre, i mira les dues bosses"), {"2", "3", "4"})
        self.assertEqual(leak.numbers("Il y a une solution et un seul cas"), set())
        self.assertEqual(leak.numbers("第三步先算一下，再数一数"), set())
        self.assertEqual(leak.numbers("36 cm²"), {"36"})             # the ² is no number

    # For each of the six languages: hints that give the answer away (the letter C, the
    # value 97, the third option) and method hints that don't. Written by the team.
    OPTIONS_97 = {"A": "8", "B": "9", "C": "97", "D": "12", "E": "23"}
    LEAKS = {
        "cat": [("La resposta és la C", "lletra"), ("En queden noranta-set", "valor"),
                ("Mira la tercera opció", "posicio")],
        "esp": [("La respuesta es la C", "lletra"), ("Quedan noventa y siete manzanas", "valor"),
                ("Mira la tercera opción", "posicio")],
        "eng": [("The answer is C for sure", "lletra"), ("There are ninety-seven left", "valor"),
                ("Look at the third option", "posicio")],
        "fra": [("Je pense que c'est la C", "lletra"), ("la réponse est c bien sûr", "lletra"),
                ("Il en reste quatre-vingt-dix-sept", "valor"), ("Regarde la troisième option", "posicio"),
                ("C'est celle du milieu", "posicio")],
        "arb": [("الجواب C بالتأكيد", "lletra"), ("الجواب هو ج طبعاً", "lletra"),
                ("يبقى سبعة وتسعون تفاحة", "valor"), ("النتيجة هي ٩٧ تفاحة", "valor"),
                ("انظر إلى الخيار الثالث", "posicio")],
        "zho": [("答案是C", "lletra"), ("我觉得选Ｃ", "lletra"), ("还剩九十七个", "valor"),
                ("一共９７个苹果", "valor"), ("看第三个选项", "posicio")],
    }
    CLEAN = {
        "cat": ["Primer calcula quantes pomes hi ha en total i després resta.",
                "Compta les bosses i multiplica."],
        "esp": ["Primero calcula cuántas manzanas hay en total y después resta.",
                "Cuenta las bolsas y multiplica."],
        "eng": ["First work out how many apples there are in total, then subtract.",
                "Count the bags and multiply."],
        "fra": ["Calcule d'abord combien il y a de pommes en tout, puis soustrais.",
                "C'est une multiplication, puis une soustraction.",
                "Il y a 3 sacs : multiplie, puis enlève celles qu'elle mange."],
        "arb": ["احسب أولاً عدد التفاحات كلها ثم اطرح ما أكلته.", "اضرب عدد الأكياس في عدد التفاحات."],
        "zho": ["先算一共有多少个苹果，再减去吃掉的。", "先乘后减。", "把每袋的苹果数乘以袋数。"],
    }

    def test_six_languages(self):
        self.assertEqual(set(self.LEAKS), set(phrases.LANGS))
        self.assertEqual(set(self.CLEAN), set(phrases.LANGS))
        for lang, cases in self.LEAKS.items():
            for hint, reason in cases:
                self.assertEqual(self.check(hint, "C", self.OPTIONS_97), reason, (lang, hint))
                self.assertIsNotNone(leak.check_strict(hint, self.OPTIONS_97, self.TEXT), (lang, hint))
        for lang, cases in self.CLEAN.items():
            for hint in cases:
                self.assertIsNone(self.check(hint, "C", self.OPTIONS_97), (lang, hint))
                self.assertIsNone(leak.check_strict(hint, self.OPTIONS_97, self.TEXT), (lang, hint))
                self.assertEqual(langs.guess(hint), lang, hint)

    def test_option_written_in_words_in_another_script(self):
        options = {"A": "星期一", "B": "星期二", "C": "星期三", "D": "星期四", "E": "星期五"}
        self.assertEqual(self.check("我想应该是星期三吧，对不对", "C", options), "valor")
        self.assertIsNone(self.check("数一数从今天起过了几天", "C", options))
        options = {"A": "أحمر", "B": "أزرق", "C": "أخضر", "D": "أصفر", "E": "أسود"}
        self.assertEqual(self.check("أظن أنه اللون الأخضر بالتأكيد", "C", options), "valor")
        # a letter the problem itself uses is no answer
        text = ["三角形的边长是 a、b 和 c，求周长。"]
        self.assertIsNone(self.check("把 a、b 和 c 加起来就行了", "C", self.OPTIONS_97, text))

    def test_ordinal_alone_is_a_position(self):
        for hint in ("és la tercera", "Es la tercera, oi?", "it's the third one", "the third one",
                     "c'est la troisième !", "la respuesta es la tercera"):
            self.assertEqual(self.check(hint, "C", self.OPTIONS_97), "posicio", hint)
        for hint in ("la tercera bossa té més pomes", "the third bag has more apples",
                     "es la tercera vez que cuentas", "c'est la troisième boîte qui compte"):
            self.assertIsNone(self.check(hint, "C", self.OPTIONS_97), hint)


class Phrases(unittest.TestCase):
    """The Kangaroo's templates (copilot/phrases.py), in the six languages."""
    OPTIONS = {"A": "37", "B": "41", "C": "43", "D": "47", "E": "53"}
    TEXT = ["How many legs do the animals have? There are 9 animals."]

    def values(self, lang):
        return {"label": "C", "answer": "B", "letter": "B", "sure": 60, "value": "43", "level": 3.5,
                "topic": phrases.topic_name("geometria", lang), "llengua": langs.name("fra"),
                "text": topics.method_hint("geometria", 0, lang)}

    def test_every_phrase_in_every_language(self):
        import string
        fields = lambda text: {name for _, name, _, _ in string.Formatter().parse(text) if name}  # noqa: E731
        for key, by_lang in phrases.PHRASES.items():
            self.assertEqual(set(by_lang), set(phrases.LANGS), key)
            for lang, text in by_lang.items():
                self.assertEqual(fields(text), fields(by_lang["cat"]), (key, lang))
                self.assertTrue(text.strip(), (key, lang))
        for key in topics.NAMES:
            self.assertEqual(set(phrases.TOPIC_NAMES[key]), set(phrases.LANGS) - {"cat"}, key)
        self.assertLessEqual(phrases.AFTER_SOLVING | phrases.STUDENT_VOICE, set(phrases.PHRASES))
        self.assertEqual(set(langs.BRIDGE), set(phrases.LANGS))
        self.assertTrue(all(code in langs.NAMES and code in langs.ISO1 for code in langs.BRIDGE))

    def test_falls_back_to_catalan(self):
        self.assertEqual(phrases.phrase("correcte", "fra"), "‹fra› Correcte!")
        self.assertEqual(phrases.phrase("correcte", "deu"), "Correcte!")           # no German
        self.assertEqual(phrases.phrase("solucio", "esp", label="C", value="10"),
                         "‹esp› La resposta és la C) 10.")
        self.assertEqual(phrases.phrase("solucio", "esp"), phrases.PHRASES["solucio"]["cat"])
        self.assertEqual(phrases.topic_name("logica", "zho"), "‹zho› Lògica")
        self.assertEqual(phrases.topic_name("logica", "deu"), topics.name("logica"))
        self.assertEqual(phrases.phrase("avis_extern"), phrases.EXTERNAL_WARNING)

    def test_machine_translations_file(self):
        # A translation is only used with the same {markers} as its Catalan template
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "mt.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"phrases": {"solucio": {"fra": "La réponse est {label}) {value}.",
                                                   "esp": "La respuesta es la {label}.",   # lost one
                                                   "deu": "x {label} {value}", "arb": "  "},
                                       "nope": {"fra": "x"}, "correcte": "broken"},
                           "topics": {"logica": {"fra": "Logique"}, "nope": {"fra": "x"}},
                           "failed": [["solucio", "zho"]]}, f)
            found, names = phrases.load(path)
            self.assertEqual(found, {"solucio": {"fra": "La réponse est {label}) {value}."}})
            self.assertEqual(names, {"logica": {"fra": "Logique"}})
            self.assertEqual(phrases.load(path + ".missing"), ({}, {}))
        # The real file, when it is there: no phrase gives an option away before the answer
        allowed = (phrases.AFTER_SOLVING | phrases.STUDENT_VOICE | phrases.OTHER_PROBLEM
                   | {"extern_sense_opcions"})
        for key, by_lang in REAL_PHRASES.items():
            for lang, template in by_lang.items():
                text = template.format(**self.values(lang))
                if key not in allowed:
                    self.assertNotIn(leak.check_strict(text, self.OPTIONS, self.TEXT),
                                     ("lletra", "valor", "posicio"), (key, lang))

    def test_no_phrase_leaks_in_any_language(self):
        # Every template, filled in, goes through the leak filter in its six versions.
        # Only the phrases kept for after the answer may name a letter; "A) … E)" names
        # them all, for an outside problem whose options couldn't be read.
        allowed = (phrases.AFTER_SOLVING | phrases.STUDENT_VOICE | phrases.OTHER_PROBLEM
                   | {"extern_sense_opcions"})
        for key in phrases.PHRASES:
            for lang in phrases.LANGS:
                text = phrases.phrase(key, lang, **self.values(lang))
                self.assertNotIn("{", text, (key, lang))
                reason = leak.check_strict(text, self.OPTIONS, self.TEXT)
                if key in allowed:
                    continue
                self.assertNotIn(reason, ("lletra", "valor", "posicio"), (key, lang, text))
        # ... and the filter does see the letter in the ones that have it, in every language
        for key in sorted(phrases.AFTER_SOLVING):
            for lang in phrases.LANGS:
                text = phrases.phrase(key, lang, **self.values(lang))
                letter = "B" if key == "jo_he_dit" else "C"
                self.assertEqual(leak.check(text, letter, self.OPTIONS, self.TEXT), "lletra", (key, lang))

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
        self.assertGreater(elo.update(1000, 1000, True), 1000)
        self.assertLess(elo.update(1000, 1000, False), 1000)
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

    def test_method_hints_in_every_language(self):
        for key, by_lang in topics.HINTS.items():
            self.assertEqual(set(by_lang), set(topics.HINT_LANGS), key)
            self.assertEqual({len(hints) for hints in by_lang.values()}, {3}, key)
            for hints in by_lang.values():
                self.assertTrue(all(0 < len(hint) < 120 for hint in hints), key)
        self.assertEqual(topics.method_hint("geometria", 1, "deu"), topics.method_hint("geometria", 1))
        self.assertEqual(topics.method_hint("geometria", 1), topics.HINTS["geometria"]["cat"][1])
        self.assertNotEqual(topics.method_hint("geometria", 1, "eng"), topics.method_hint("geometria", 1))
        self.assertEqual(topics.method_hint("nothing", 0, "zho"), topics.HINTS[topics.DEFAULT]["zho"][0])


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
                           images_dir=self.folder.name, embedder=fake_embedder, solver=self.solve)

    def solve(self, problem):
        return pipeline.solve(problem, llm_url=self.url)

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
        problem_id = view["problem"]["id"]
        problem_before = self.tutor.store.problem(problem_id)["elo"]
        view = self.tutor.answer(self.wrong_letter())
        self.assertEqual(view["phase"], "help")
        self.assertLess(self.tutor.student["elo_cat"], before)
        # problem ratings are fixed: a student's answer never moves them
        self.assertEqual(self.tutor.store.problem(problem_id)["elo"], problem_before)
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

    def test_precomputed_kangaroo_does_not_call_the_model(self):
        # Wrong-leaning probabilities for every problem, as prep/kangaroo_baseline.py stores them
        self.store.run("UPDATE problems SET k_probs = ?",
                       (json.dumps({"A": 0.4, "B": 0.3, "C": 0.1, "D": 0.1, "E": 0.1}),))
        self.tutor.start("Test", "", 1)
        calls = len(self.model.calls)
        self.tutor.next()
        current = self.tutor.current
        self.assertEqual(len(self.model.calls), calls)               # no reference call
        self.assertTrue(current["ref_done"])
        self.assertIsNotNone(current["ref"])
        view = self.tutor.answer(current["label"])
        self.assertFalse(view["busy"])                               # nothing to wait for
        self.assertEqual(len(self.model.calls), calls)

    def test_kangaroo_is_asked_when_nothing_was_precomputed(self):
        self.tutor.start("Test", "", 1)
        calls = len(self.model.calls)
        self.tutor.next()
        self.assertEqual(len(self.model.calls), calls + 1)           # one reference call
        self.assertTrue(self.tutor.current["ref_done"])

    def test_nonsense_hint_does_not_convince(self):
        self.tutor.start("Test", "", 1)
        self.teachable()
        self.store.set_meta("tau", "0.5")
        for n in range(3):
            view = self.tutor.hint(f"zzzz qqqq xxxx {n} kkkk")
        self.assertEqual(view["phase"], "done")                    # three tries, then it stops
        self.assertTrue(all(not h["convinced"] for h in self.store.hints()))

    def test_leave_the_kangaroo(self):
        self.tutor.start("Test", "", 1)
        self.teachable()
        problem_id = self.tutor.current["id"]
        view = self.tutor.leave_teaching()                          # no hint sent at all
        self.assertEqual(view["phase"], "solving")
        self.assertNotEqual(self.tutor.current["id"], problem_id)
        exits = self.store.teach_exits()
        self.assertEqual([(e["problem_id"], e["tries"]) for e in exits], [(problem_id, 0)])

    def test_cannot_leave_while_solving(self):
        self.tutor.start("Test", "", 1)
        self.tutor.next()
        problem_id = self.tutor.current["id"]
        view = self.tutor.leave_teaching()                          # only after solving it
        self.assertEqual((view["phase"], self.tutor.current["id"]), ("solving", problem_id))
        self.assertEqual(self.store.teach_exits(), [])

    def test_no_silent_switch_to_the_model_language(self):
        self.store.run("DELETE FROM texts WHERE lang = 'cat'")
        self.tutor.start("Test", "", 1)
        view = self.tutor.next()
        self.assertEqual(view["phase"], "empty")
        self.assertIn("català", view["messages"][-1]["text"])

    def machine_french(self, where="1 = 1"):
        """French for some problems, as prep/import_translations.py leaves it."""
        self.store.run("INSERT INTO texts (id, lang, text, options, source) SELECT id, 'fra', "
                       f"'FR ' || text, options, 'opus-mt' FROM texts WHERE lang = 'esp' AND {where}")

    def test_no_silent_switch_to_catalan(self):
        # (a) no problem at all in the student's language: said on every problem
        self.tutor.start("Test", "fra", 1)
        before = dict(self.tutor.student)
        view = self.tutor.next()
        self.assertEqual((view["problem"]["shown"], view["problem"]["origen"]), ("cat", None))
        notice = view["messages"][-1]
        self.assertEqual(notice["text"], "Ja no queden problemes en Français. Continuem en català.")
        self.assertEqual(notice["origen"]["lang"], "fra")           # and in French too
        self.tutor.answer(self.tutor.current["label"])
        last = self.store.attempts()[-1]
        self.assertEqual((last["lang"], last["shown"], last["origin_lang"]), ("cat", "cat", "fra"))
        self.assertGreater(self.tutor.student["elo_cat"], before["elo_cat"])
        self.assertEqual(self.tutor.student["elo_origen"], before["elo_origen"])
        # (b) a given problem that has no text in the student's language
        some = english(TRAIN)[3]["id"]
        self.machine_french(f"id != '{some}'")
        view = self.tutor.next(some)
        self.assertEqual((view["problem"]["shown"], view["problem"]["origen"]), ("cat", None))
        self.assertEqual(view["messages"][-1]["text"],
                         "Aquest problema encara no està traduït a la teva llengua.")
        self.assertEqual(self.tutor.current["counts_for"], "cat")
        view = self.tutor.next()                                    # the others have French
        self.assertEqual(view["problem"]["shown"], "both")
        self.assertEqual(len(view["messages"]), 1)                  # no notice

    def test_machine_translation_is_marked(self):
        self.machine_french()
        view = self.tutor.start("Test", "fra", 1)
        self.assertEqual(view["languages"], ["cat", "arb", "eng", "esp", "fra", "zho"])
        self.assertEqual(view["bank_languages"], ["cat", "eng", "esp", "fra"])
        self.assertEqual(view["lang_names"]["arb"], {"name": "العربية", "iso": "ar"})
        view = self.tutor.next()
        self.assertEqual(view["problem"]["origen_source"], "opus-mt")
        self.assertTrue(view["problem"]["origen"].startswith("FR "))
        self.tutor.set_language("esp")                              # M3Kang's own text
        self.assertEqual(self.tutor.view()["problem"]["origen_source"], "official")

    def test_options_in_the_student_language(self):
        words = {"A": "uno", "B": "dos", "C": "tres", "D": "cuatro", "E": "cinco"}
        self.store.run("UPDATE texts SET options = ? WHERE lang = 'esp'", (json.dumps(words),))
        self.tutor.start("Test", "esp", 1)
        view = self.tutor.next()                                    # stage 1: both
        self.assertEqual(view["problem"]["options_origen"], words)
        self.assertEqual(set(view["problem"]["options"]), set("ABCDE"))
        self.assertNotEqual(view["problem"]["options"], words)      # the Catalan ones stay
        label = self.tutor.current["label"]
        self.tutor.answer(self.wrong_letter())
        for _ in range(4):
            view = self.tutor.help()
        solution = view["messages"][-1]
        self.assertIn(f"{label}) {self.tutor.current['options'][label]}", solution["text"])
        self.assertEqual(solution["origen"]["text"], f"‹esp› La resposta és la {label}) {words[label]}.")
        self.tutor.student["etapa"] = 2
        seen = set()
        for _ in range(6):                                          # stage 2
            view = self.tutor.next()
            problem = view["problem"]
            seen.add(problem["shown"])
            if problem["shown"] == "cat":
                self.assertIsNone(problem["options_origen"])        # behind the button
                self.assertEqual(self.tutor.reveal()["problem"]["options_origen"], words)
            else:
                self.assertEqual(problem["options"], words)         # only the student's language
                self.assertIsNone(problem["options_origen"])
            self.tutor.answer(self.wrong_letter())
        self.assertEqual(seen, {"cat", "origen"})
        # a hint that gives the value in the student's language is a leak too
        self.tutor.student["etapa"] = 1
        self.teachable()
        value = words[self.tutor.current["label"]]
        view = self.tutor.hint(f"Fíjate bien, al final sale {value} seguro")
        self.assertEqual(view["messages"][-1]["kind"], "fuita")

    def test_switching_language_keeps_each_state(self):
        self.machine_french()
        self.tutor.start("Test", "esp", 1)
        for _ in range(4):
            self.tutor.next()
            self.tutor.answer(self.tutor.current["label"])
        spanish = dict(self.tutor.student)
        self.assertEqual(spanish["etapa"], 2)
        view = self.tutor.set_language("fra")                       # a new language starts over
        self.assertEqual((view["student"]["lang_origen"], view["student"]["etapa"]), ("fra", 1))
        self.assertEqual(self.tutor.student["elo_origen"], elo.initial_student(1))
        self.assertEqual(self.tutor.student["elo_cat"], spanish["elo_cat"])     # one for all
        view = self.tutor.next()
        self.assertEqual((view["problem"]["shown"], view["problem"]["origen_lang"]), ("both", "fra"))
        problem_id = view["problem"]["id"]
        view = self.tutor.set_language("esp")                       # not answered: shown again
        self.assertEqual((view["phase"], view["problem"]["id"]), ("solving", problem_id))
        self.assertEqual(view["student"]["etapa"], 2)               # where Spanish was left
        self.assertEqual(self.tutor.student["elo_origen"], spanish["elo_origen"])
        self.tutor.set_language("fra")
        self.tutor.answer(self.tutor.current["label"])
        self.assertEqual(self.tutor.student["streak"], 1)
        self.assertEqual([a["origin_lang"] for a in self.store.attempts()], ["esp"] * 4 + ["fra"])
        self.tutor.set_language("esp")
        self.assertEqual((self.tutor.student["etapa"], self.tutor.student["streak"]), (2, 0))
        self.tutor.set_language("fra")
        self.assertEqual((self.tutor.student["etapa"], self.tutor.student["streak"]), (1, 1))
        self.assertEqual({row["lang"]: row["etapa"] for row in self.tutor.teacher()["languages"]},
                         {"esp": 2, "fra": 1})
        view = self.tutor.set_language("cat")                       # "I already speak Catalan"
        self.assertEqual((view["student"]["etapa"], self.tutor.student["etapa"]), (None, 3))
        self.assertEqual(self.tutor.next()["problem"]["shown"], "cat")
        self.assertEqual(self.tutor.set_language("xx")["student"]["lang_origen"], "")   # unknown
        self.tutor.busy = True                                      # not while the Kangaroo thinks
        self.assertEqual(self.tutor.set_language("esp")["student"]["lang_origen"], "")
        self.tutor.busy = False
        # a new session finds the languages as they were left
        again = Tutor(self.store, ask=self.ask, background=False, embedder=None)
        again.set_language("esp")
        self.assertEqual((again.student["etapa"], again.student["elo_origen"]),
                         (2, spanish["elo_origen"]))

    def test_already_speaks_catalan(self):
        for choice in ("cat", ""):
            view = self.tutor.start("Test", choice, 1, reset=True)
            self.assertEqual((view["student"]["etapa"], view["student"]["lang_origen"]), (None, ""))
            self.assertEqual(self.tutor.student["etapa"], 3)        # no bridge at all
            view = self.tutor.next()
            self.assertEqual((view["problem"]["shown"], view["problem"]["origen"]), ("cat", None))
            self.assertFalse(view["problem"]["can_reveal"])
            self.tutor.answer(self.wrong_letter())
            view = self.tutor.help()
            self.assertTrue(all("origen" not in m for m in view["messages"]))
            self.assertEqual(self.store.attempts()[-1]["origin_lang"], "")

    def test_the_kangaroo_speaks_the_student_language(self):
        self.machine_french()
        # everything said, but a similar problem the bank doesn't have in that language:
        # nothing is translated while the tutor runs
        in_bank = lambda: self.tutor.student["lang_origen"] in self.store.languages()   # noqa: E731
        templates = lambda view: [m for m in view["messages"]       # noqa: E731
                                  if m["kind"] != "exemple" or in_bank()]
        for lang in ("eng", "esp", "fra", "arb", "zho"):            # stage 1: always both
            view = self.tutor.start("Test", lang, 1, reset=True)
            self.assertEqual(view["messages"][0]["origen"]["text"], phrases.phrase("hola", lang))
            self.tutor.next()
            self.tutor.answer(self.wrong_letter())
            for _ in range(4):
                view = self.tutor.help()
            said = templates(view)
            self.assertGreaterEqual(len(said), 6)
            for message in said:
                self.assertEqual(message["origen"]["lang"], lang, message["text"])
                self.assertNotEqual(message["origen"]["text"], message["text"])
        self.tutor.start("Test", "fra", 1, reset=True)              # stage 2: behind the button
        self.tutor.student["etapa"] = 2
        view = self.tutor.next()
        self.assertEqual(view["problem"]["shown"], "cat")
        self.tutor.answer(self.wrong_letter())
        view = self.tutor.help()
        self.assertTrue(all("origen" not in m for m in view["messages"]))
        self.assertTrue(view["problem"]["can_reveal"])
        view = self.tutor.reveal()
        self.assertTrue(all(m["origen"]["lang"] == "fra" for m in templates(view)))
        view = self.tutor.answer(self.tutor.current["label"])       # said after the click too
        self.assertEqual(view["messages"][-1]["origen"]["lang"], "fra")
        self.tutor.student["streak"] = 3                            # one more and it's stage 3
        view = self.tutor.next()
        self.assertTrue(view["problem"]["can_reveal"])
        view = self.tutor.answer(self.tutor.current["label"])
        self.assertEqual(self.tutor.student["etapa"], 3)
        change = next(m for m in view["messages"] if m["text"].startswith("Ja no et cal el botó"))
        self.assertEqual(change["origen"]["text"], phrases.phrase("etapa3", "fra"))   # no button needed
        view = self.tutor.next()                                    # stage 3: Catalan only
        self.tutor.answer(self.wrong_letter())
        view = self.tutor.help()
        self.assertTrue(all("origen" not in m for m in view["messages"]))
        self.assertFalse(view["problem"]["can_reveal"])

    def test_no_template_gives_the_answer_before_it_is_solved(self):
        self.machine_french()
        for lang in ("eng", "esp", "fra", "arb", "zho"):
            self.tutor.start("Test", lang, 1, reset=True)
            self.tutor.next()
            current = self.tutor.current
            self.tutor.answer(self.wrong_letter())
            for _ in range(3):                                      # every rung before the solution
                view = self.tutor.help()
            statements = [current["model"]["text"], current["cat"]["text"]]
            for message in view["messages"]:
                if message["who"] == "alumne" or message["kind"] == "exemple":
                    continue                    # the student's own answer; another problem's answer
                for text in (message["text"], message.get("origen", {}).get("text", "")):
                    for options in (current["options"], current["model"]["options"]):
                        self.assertNotIn(leak.check(text, current["label"], options, statements),
                                         ("lletra", "valor", "posicio"), text)
            self.assertIsNone(view["problem"]["label"])
            # a phrase with the answer in it is refused until then, whoever asks for it
            before = len(self.tutor.messages)
            for key in sorted(phrases.AFTER_SOLVING):
                self.tutor._tell("cangur", (key, {"label": current["label"], "answer": "A",
                                                  "sure": 50, "value": "x"}))
            self.assertEqual(len(self.tutor.messages), before)

    def test_hints_in_any_of_the_six_languages(self):
        self.tutor.start("Test", "fra", 1)
        self.teachable()
        current = self.tutor.current
        self.store.set_meta("tau", "100")                           # nothing convinces
        calls = len(self.model.calls)
        label, value = current["label"], current["options"][current["label"]]
        for hint in (f"Je pense que c'est la {label}", f"答案是{label}", f"الجواب هو {label} بالتأكيد"):
            view = self.tutor.hint(hint)
            self.assertEqual(view["messages"][-1]["kind"], "fuita", hint)
            self.assertEqual(view["messages"][-1]["origen"]["lang"], "fra")   # told in French too
        self.assertEqual((len(self.model.calls), current["tries"]), (calls, 0))
        view = self.tutor.hint("Regarde bien ce que le problème demande et fais un dessin.")
        self.assertEqual(current["tries"], 1)                       # it reached the Kangaroo
        self.assertEqual(self.model.calls[-1]["hint"],              # as written: nothing is translated
                         "Regarde bien ce que le problème demande et fais un dessin.")
        view = self.tutor.hint("先画一张图，再把已知条件标上去。")
        self.assertEqual(current["tries"], 2)
        stored = [(h["lang"], h["rejected"]) for h in self.store.hints()]
        self.assertEqual(stored, [("fra", "lletra"), ("zho", "lletra"), ("arb", "lletra"),
                                  ("fra", None), ("zho", None)])
        self.assertIsNotNone(value)

    def test_hint_limit_is_sent_to_the_page(self):
        self.assertEqual(self.tutor.view()["hint_max_chars"], int(CONFIG.get("HINT_MAX_CHARS", 200)))

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

    def test_rejected_hint_is_kept_as_data_only(self):
        self.tutor.start("Test", "", 1)
        self.teachable()
        current = self.tutor.current
        calls = len(self.model.calls)
        view = self.tutor.hint(f"És la {current['label']}")
        self.assertEqual(view["messages"][-1]["kind"], "fuita")   # the student sees the same
        self.assertEqual((len(self.model.calls), current["tries"]), (calls, 0))
        hint = self.store.hints()[-1]
        self.assertEqual((hint["rejected"], hint["delta"], hint["convinced"], hint["vec"]),
                         ("lletra", None, 0, None))
        self.store.run("UPDATE hints SET convinced = 1, solved_after = 9 WHERE n = ?", (hint["n"],))
        self.assertIsNone(self.store.best_hint(current["id"]))     # never shown to anyone
        self.assertIsNone(self.store.best_neighbour_hint([current["id"]]))
        self.assertEqual(self.store.hint_vectors(current["id"]), [])

    def test_duplicate_hint_is_not_stored_twice(self):
        import embed_refs
        embed_refs.run(self.store, fake_embedder)                  # the topics' method hints
        self.tutor.start("Test", "", 1)
        self.teachable()
        self.store.set_meta("tau", "100")                          # nothing convinces: three tries
        self.tutor.hint("Compta quantes pomes hi ha a cada bossa.")
        self.tutor.hint("Compta quantes pomes hi ha a cada bossa!")  # the same words
        self.tutor.hint("Dibuixa un esquema amb totes les dades.")
        hints = self.store.hints()
        self.assertEqual(len(hints), 2)
        self.assertEqual(hints[0]["dups"], 1)
        self.assertIsNotNone(hints[0]["vec"])
        self.assertIsNotNone(hints[1]["relevance"])                # the topic's method hints

    def test_without_embedding_server_the_hint_is_stored_anyway(self):
        self.tutor.embedder = dead_embedder
        self.tutor.start("Test", "", 1)
        self.teachable()
        self.store.set_meta("tau", "100")
        for _ in range(2):
            view = self.tutor.hint("Compta quantes pomes hi ha a cada bossa.")
        hints = self.store.hints()
        self.assertEqual(len(hints), 2)                            # no duplicate check without vectors
        self.assertTrue(all(h["relevance"] is None and h["vec"] is None for h in hints))
        self.assertIn(view["phase"], ("teach", "done"))            # the student carries on

    def test_hint_of_a_similar_problem(self):
        self.tutor.start("Test", "", 1)
        self.tutor.next()
        current = self.tutor.current
        neighbour = current["row"]["neighbours"][0]
        self.store.add_hint(neighbour, 1, "Agrupa-les de dues en dues.", 2.0, True)
        self.tutor.answer(self.wrong_letter())
        for _ in range(3):
            view = self.tutor.help()
        self.assertIn("Una pista d'un problema semblant: «Agrupa-les de dues en dues.»",
                      [m["text"] for m in view["messages"]])
        self.assertEqual(self.store.hints()[0]["shown"], 0)       # its counts stay its own
        self.store.add_hint(current["id"], None, "La del banc.", None, False, source="agent")
        self.assertEqual(self.store.best_hint(current["id"])["text"], "La del banc.")

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

    def method_message(self, view):
        return next(m for m in reversed(view["messages"]) if m["text"].startswith("És un problema de"))

    def ask_for_method(self):
        self.tutor.answer(self.wrong_letter())
        for _ in range(2):   # rung 1 (a similar problem) is skipped when there is none
            view = self.tutor.help()
            if any(m["text"].startswith("És un problema de") for m in view["messages"]):
                return view
        self.fail("no method hint")

    def test_method_hint_follows_the_language_stage(self):
        self.tutor.start("Test", "esp", 1)                         # stage 1: both languages
        self.tutor.next()
        topic = self.tutor.current["row"]["topic"]
        message = self.method_message(self.ask_for_method())
        self.assertIn(topics.method_hint(topic, 0), message["text"])
        self.assertEqual(message["origen"]["lang"], "esp")
        self.assertEqual(message["origen"]["text"],                # the lead is translated too
                         "‹esp› És un problema de «" + phrases.topic_name(topic, "esp") + "». "
                         + topics.method_hint(topic, 0, "esp"))

        self.tutor.student["etapa"] = 2                            # stage 2: behind the button
        for _ in range(5):
            view = self.tutor.next()
            if view["problem"]["shown"] == "cat":
                break
            self.tutor.answer(self.wrong_letter())
        self.assertEqual(view["problem"]["shown"], "cat")
        view = self.ask_for_method()
        self.assertNotIn("origen", self.method_message(view))
        view = self.tutor.reveal()
        self.assertEqual(self.method_message(view)["origen"]["lang"], "esp")
        self.assertTrue(self.tutor.current["revealed"])            # the same counted click

        self.tutor.start("Test", "", 1, reset=True)                # stage 3 / no other language
        self.tutor.next()
        self.assertNotIn("origen", self.method_message(self.ask_for_method()))

    SPIDERS = "How many legs do 7 spiders have? A) 42 B) 49 C) 56 D) 63 E) 70"

    def test_outside_problem_follows_the_bank_path(self):
        self.tutor.start("Test", "", 1)
        before = dict(self.tutor.student)
        view = self.tutor.external(self.SPIDERS)
        problem = view["problem"]
        self.assertEqual(view["phase"], "solving")
        self.assertTrue(problem["external"])
        self.assertIn("No podem assegurar", problem["warning"])    # always on screen
        self.assertIsNone(problem["label"])                        # never leads with an answer
        self.assertIn(self.tutor.current["label"], tuple("ABCDE")) # the harness's answer
        view = self.tutor.answer(self.wrong_letter())
        self.assertEqual(view["phase"], "help")
        self.assertIn("No podem assegurar", view["problem"]["warning"])
        # stored apart, and no rating moves
        self.assertEqual(self.store.attempts(), [])
        external = self.store.attempts(external=True)
        self.assertEqual(len(external), 1)
        self.assertEqual(external[0]["correct"], 0)
        for key in ("elo_cat", "elo_origen", "etapa", "streak"):
            self.assertEqual(self.tutor.student[key], before[key])
        self.assertEqual(self.tutor.teacher()["external_attempts"], 1)
        self.assertEqual(self.tutor.teacher()["attempts"], 0)
        for _ in range(4):                                         # the same ladder, to the end
            view = self.tutor.help()
        self.assertEqual(view["phase"], "done")
        self.assertEqual(view["problem"]["label"], self.tutor.current["label"])
        self.assertEqual(view["messages"][-1]["kind"], "avis")     # the solution comes with it
        self.assertEqual(len(self.store.attempts(external=True)), 1)
        self.assertEqual(self.tutor.next()["phase"], "solving")    # back to the bank

    def test_outside_problem_right_answer_and_teaching(self):
        # The harness's answer is usually the model's own favourite, so there's often
        # nothing to teach. Here the harness says the model's least likely letter.
        def least_likely(problem):
            probs = self.ask(problem, hint=NEUTRAL_HINT)["probs"]
            return {"answer": min("ABCDE", key=lambda l: probs[l]), "status": "ok", "calls": 1}
        self.tutor.solver = least_likely
        self.tutor.start("Test", "", 1)
        self.tutor.external(self.SPIDERS)
        hints_before = len(self.store.hints())
        view = self.tutor.answer(self.tutor.current["label"])
        self.assertEqual(view["phase"], "teach")
        self.assertEqual(self.store.attempts(external=True)[0]["correct"], 1)
        # strict filter: no option may be named, whichever is right
        view = self.tutor.hint(f"Crec que és la {self.wrong_letter()}, mira-ho bé")
        self.assertEqual(view["messages"][-1]["kind"], "fuita")
        view = self.tutor.hint("Compta quantes potes té una aranya i multiplica")
        self.assertNotEqual(view["messages"][-1]["kind"], "fuita")
        self.assertEqual(self.tutor.current["tries"], 1)           # it reached the Kangaroo
        self.assertEqual(len(self.store.hints()), hints_before)   # never stored for others
        self.assertEqual(self.tutor.leave_teaching()["phase"], "solving")
        self.assertEqual(self.store.teach_exits(), [])

    def test_outside_problem_without_options_is_only_placed(self):
        self.tutor.start("Test", "", 1)
        view = self.tutor.external("How many legs do 7 spiders have?")
        self.assertEqual(view["phase"], "external")
        self.assertIsNone(view["problem"])
        self.assertIsNone(self.tutor.answer("A")["problem"])
        self.assertEqual(self.store.attempts(external=True), [])

    def test_outside_problem_model_down(self):
        def fallback(problem):
            return {"answer": "D", "status": "error: x", "calls": 0}   # what solve() gives then
        tutor = Tutor(self.store, ask=self.ask, background=False, embedder=None, solver=fallback)
        tutor.start("Test", "", 1)
        view = tutor.external(self.SPIDERS)
        self.assertEqual(view["phase"], "done")                   # nothing graded against a guess
        self.assertIsNone(tutor.current["label"])
        self.assertEqual(tutor.answer("D")["phase"], "done")
        self.assertEqual(self.store.attempts(external=True), [])

    def test_model_down(self):
        def dead(problem, **kwargs):
            raise OSError("down")
        tutor = Tutor(self.store, ask=dead, background=False, embedder=None)
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
            tutor = Tutor(store, ask=self.ask, background=False, embedder=None)
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
                view = call("/api/language", {"lang": "esp"})
                self.assertEqual((view["student"]["lang_origen"], view["student"]["etapa"]), ("esp", 1))
                self.assertEqual(call("/api/language", {"lang": "cat"})["student"]["etapa"], None)
                with urllib.request.urlopen(base + "/", timeout=10) as page:
                    html = page.read().decode("utf-8")
                self.assertIn("Ensenya el Cangur", html)
                self.assertNotIn("http://", html.replace("http://127.0.0.1", "").replace("http://www.w3.org/2000/svg", ""))   # nothing from the internet (the SVG namespace is a name, not a request)
                self.assertNotIn("https://", html)
            finally:
                server.shutdown()
                store.close()


# --- agent batches: check_agent_output, the hints' source column, import_hints ---

sys.path.insert(0, os.path.join(ROOT, "prep"))
import agent_lots  # noqa: E402
import check_agent_output  # noqa: E402
import importlib.util  # noqa: E402
import import_hints  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "export_batch", os.path.join(ROOT, "prep", "agent", "export_batch.py"))
export_batch = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(export_batch)

AGENT_TRAIN = [
    {"id": "t1", "language": "eng", "level": 0, "year": 2020, "text_only": True,
     "text": SAMPLE["text"], "options": SAMPLE["options"], "label": "C"},
    {"id": "t1", "language": "cat", "level": 0, "year": 2020, "text_only": True,
     "text": "L'Anna té 3 bosses amb 4 pomes a cada bossa. Es menja 2 pomes. Quantes en queden?",
     "options": SAMPLE["options"], "label": "C"},
    {"id": "t2", "language": "eng", "level": 2, "year": 2021, "text_only": False,
     "text": "Which figure in the picture is shaded?", "options": {}, "label": "B"},
]
AGENT_VAL = [{"id": "v1", "language": "eng", "level": 2, "year": 2022, "text_only": True,
              "text": "What is the value of 2 + 3 x 4?",
              "options": {"A": "20", "B": "14", "C": "24", "D": "9", "E": "10"}, "label": "B"}]
GOOD_HINT = "Compta primer quantes pomes hi ha en total i després treu les que es menja."


def agent_line(kind, problem_id, **fields):
    return {"id": problem_id, "kind": kind, "source": "agent", **fields}


class AgentBatches(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.dir = folder.name
        self.train = self.write("train.jsonl", AGENT_TRAIN)
        self.val = self.write("val.jsonl", AGENT_VAL)

    def write(self, name, rows, raw=()):
        path = os.path.join(self.dir, name)
        with open(path, "w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            for line in raw:
                f.write(line + "\n")
        return path

    def check(self, kind, rows, raw=(), data=True):
        """Run the checker as the command line does: (exit code, kept rows, printed text)."""
        path = self.write(f"{kind}_out.jsonl", rows, raw)
        args = [path, "--kind", kind, "--db", os.path.join(self.dir, "none.db")]
        args += ["--data", self.train, self.val] if data else ["--no-data"]
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            code = check_agent_output.main(args)
        with open(check_agent_output.default_ok_path(path), encoding="utf-8") as f:
            kept = [json.loads(line) for line in f if line.strip()]
        return code, kept, printed.getvalue()

    def test_hint_bank(self):
        code, kept, printed = self.check("hint_bank", [
            agent_line("hint_bank", "t1", lang="cat", hint=GOOD_HINT),
            agent_line("hint_bank", "t1", lang="cat", hint="Fixa't en la resposta C, és la bona."),
            agent_line("hint_bank", "t1", lang="cat", hint="Multiplica les bosses per les pomes de cada bossa."),
            agent_line("hint_bank", "t1", lang="cat", hint="Fes un dibuix de les bosses i les pomes."),
            agent_line("hint_bank", "t1", lang="cat", hint=GOOD_HINT),
            agent_line("hint_bank", "zz", lang="cat", hint=GOOD_HINT),
            agent_line("hint_bank", "t2", lang="cat", hint="Mira bé quina figura està pintada."),
            agent_line("hint_bank", "t1", lang="eng", hint="Count the apples first."),
            agent_line("hint_bank", "t1", lang="cat", hint="Compta les pomes. Després resta."),
        ], raw=["{not json"])
        self.assertEqual(code, 1)
        self.assertEqual([row["hint"] for row in kept],
                         [GOOD_HINT, "Multiplica les bosses per les pomes de cada bossa."])
        for expected in ("line 2 (t1): rejected by copilot.leak (lletra)", "already two hints",
                         "unknown problem id 'zz'", "isn't eligible", "lang must be 'cat'",
                         "one sentence", "not valid JSON"):
            self.assertIn(expected, printed)
        self.assertNotIn(SAMPLE["text"], printed)   # errors never show the problem text

    def test_value_leak_in_another_language_is_caught(self):
        code, kept, printed = self.check("hint_bank", [
            agent_line("hint_bank", "t1", lang="cat", hint="Al final en queden deu, compta-les.")])
        self.assertEqual((code, kept), (2, []))
        self.assertIn("(valor)", printed)

    def test_schema(self):
        code, kept, printed = self.check("hint_bank", [
            {"id": "t1", "kind": "hint_bank", "source": "human", "lang": "cat", "hint": GOOD_HINT},
            agent_line("hint_bank", "t1", lang="cat", hint=GOOD_HINT, extra=1),
            agent_line("solutions", "t1", lang="cat", hint=GOOD_HINT),
            agent_line("hint_bank", "t1", lang="cat"),
            agent_line("hint_bank", "t1", lang="cat", hint=7),
        ])
        self.assertEqual((code, kept), (2, []))
        for expected in ("expected 'agent'", "unknown field 'extra'", "expected 'hint_bank'",
                         "missing field 'hint'", "'hint' should be a string"):
            self.assertIn(expected, printed)

    def test_without_data_it_checks_schema_and_rules(self):
        code, kept, printed = self.check("hint_bank", [
            agent_line("hint_bank", "anything", lang="cat", hint=GOOD_HINT, label="C"),
            agent_line("hint_bank", "other", lang="cat", hint=GOOD_HINT)], data=False)
        self.assertEqual(code, 1)
        self.assertEqual(len(kept), 1)
        self.assertIn("no label to check against", printed)

    def test_hint_experiment(self):
        row = agent_line("hint_experiment", "t1", good=GOOD_HINT,
                         bad="Pensa en el teu color preferit i en com et fa sentir avui.",
                         leak="La resposta és la C.")
        code, kept, printed = self.check("hint_experiment", [
            row,
            agent_line("hint_experiment", "t1", good=GOOD_HINT, bad=row["bad"], leak="Ja ho tens."),
            agent_line("hint_experiment", "v1", good="Fes primer la multiplicació.",
                       bad="Pensa en el teu color preferit i en com et fa sentir avui.",
                       leak="Són 14."),
            agent_line("hint_experiment", "v1", good="Fes primer la multiplicació i després suma.",
                       bad="Pensa en el teu color preferit.", leak="La B."),
        ])
        self.assertEqual(code, 1)
        self.assertEqual(len(kept), 2)
        self.assertEqual(kept[0]["label"], "C")
        self.assertEqual(kept[0]["text"], AGENT_TRAIN[1]["text"])   # the Catalan text, for TUTOR_LANG
        self.assertEqual(kept[0]["options"], SAMPLE["options"])
        self.assertIn("already has hints", printed)
        self.assertIn("about as long as good", printed)
        # what hint_experiment.py reads: id, label, options, text, good, bad, leak
        self.assertLessEqual({"id", "label", "options", "text", "good", "bad", "leak"}, set(kept[0]))

    def test_solutions(self):
        code, kept, printed = self.check("solutions", [
            agent_line("solutions", "t1", solution="12 apples, minus 2, leaves 10.", answer="C",
                       expression="3 * 4 - 2"),
            agent_line("solutions", "v1", solution="2 + 12 = 14", answer="B"),
            agent_line("solutions", "t2", solution="Look at it.", answer="A"),
            agent_line("solutions", "t2", solution="The shaded one.", answer="B",
                       expression="__import__('os')"),
            agent_line("solutions", "t2", solution="The shaded one.", answer="B", type="visual"),
            agent_line("solutions", "t1", solution="Again.", answer="C"),
        ])
        self.assertEqual(code, 1)
        self.assertEqual([row["id"] for row in kept], ["t1"])
        for expected in ("training problems only", "doesn't match the label",
                         "may only use numbers", "unknown field 'type'", "already in the file"):
            self.assertIn(expected, printed)
        _code, _kept, printed = self.check("solutions", [
            agent_line("solutions", "t1", solution="Ten.", answer="C", expression="3 * 4")])
        self.assertIn("expression gives 12, the correct option is 10", printed)

    def test_problem_types(self):
        code, kept, printed = self.check("problem_types", [
            agent_line("problem_types", "t1", type="arithmetic", topic="aritmetica",
                       python_solvable=True),
            agent_line("problem_types", "v1", type="arithmetic"),
            agent_line("problem_types", "t2", type="algebra"),
            agent_line("problem_types", "t2", type="visual", python_solvable="no"),
            agent_line("problem_types", "t2", type="visual", answer="B"),
        ])
        self.assertEqual(code, 1)
        self.assertEqual([row["id"] for row in kept], ["t1", "v1"])
        for expected in ("type must be one of", "'python_solvable' should be true or false",
                         "unknown field 'answer'", "types: arithmetic 2"):
            self.assertIn(expected, printed)

    def test_export_never_gives_validation_labels(self):
        out = os.path.join(self.dir, "types_in.jsonl")
        for kind, split, n in (("problem_types", None, 0), ("hint_bank", None, 0),
                               ("leak_cases", "all", 0)):
            args = ["--kind", kind, "--n", str(n), "--out", out, "--data", self.train, self.val,
                    "--db", os.path.join(self.dir, "none.db")] + (["--split", split] if split else [])
            with contextlib.redirect_stdout(io.StringIO()):
                export_batch.main(args)
            with open(out, encoding="utf-8") as f:
                rows = [json.loads(line) for line in f]
            for row in rows:
                self.assertEqual("label" in row, kind != "problem_types" and row["split"] == "train")
            if kind == "hint_bank":   # eligible training problems only
                self.assertEqual([row["id"] for row in rows], ["t1"])
                self.assertEqual(list(rows[0]["texts"]), ["eng", "cat"])
        with self.assertRaises(SystemExit):
            export_batch.main(["--kind", "solutions", "--split", "all", "--out", out,
                               "--data", self.train, self.val, "--db", "none.db"])

    def test_leak_cases_feed_the_filter_evaluation(self):
        code, kept, _printed = self.check("leak_cases", [
            agent_line("leak_cases", "t1", hint="La resposta és la C.", label="C", leak=True,
                       category="lletra"),
            agent_line("leak_cases", "t1", hint=GOOD_HINT, label="C", leak=False, category="neta"),
            agent_line("leak_cases", "inv-001", hint="Són 17.", label="B", leak=True,
                       options={"A": "15", "B": "17", "C": "18", "D": "20", "E": "23"},
                       text="4 caixes de 5 llapis i en regala 3."),
            agent_line("leak_cases", "inv-002", hint="Són 17.", label="B", leak=True),
            agent_line("leak_cases", "t1", hint="Hi ha deu pomes.", label="C", leak=False,
                       category="valor"),
        ])
        self.assertEqual(code, 1)
        self.assertEqual(len(kept), 3)
        self.assertEqual(kept[0]["options"], SAMPLE["options"])
        report = leak.evaluate(kept)
        self.assertEqual((report["leaks"], report["clean"]), (2, 1))

    def test_topics_reference(self):
        code, kept, printed = self.check("topics_reference", [
            agent_line("topics_reference", "t1", topic="aritmetica", alt=None),
            agent_line("topics_reference", "v1", topic="algebra"),
            agent_line("topics_reference", "t2", topic="geometria", alt="geometria"),
        ])
        self.assertEqual(code, 1)
        self.assertEqual(len(kept), 1)
        self.assertIn("topics.py agrees on 1/1", printed)
        self.assertEqual(set(agent_lots.TOPIC_KEYS), set(topics.NAMES))

    def test_invented_problems(self):
        options = {"A": "15", "B": "17", "C": "18", "D": "20", "E": "23"}
        text = "La Laia té 4 caixes amb 5 llapis cadascuna i en regala 3. Quants llapis li queden?"
        code, kept, printed = self.check("invented_problems", [
            agent_line("invented_problems", "inv-001", language="cat", level=0, text=text,
                       options=options, label="B", topic="aritmetica"),
            agent_line("invented_problems", "inv-002", language="eng", level=0,
                       text=SAMPLE["text"], options=SAMPLE["options"], label="C"),
            agent_line("invented_problems", "t1", language="eng", level=0, text="New text here.",
                       options=options, label="B"),
            agent_line("invented_problems", "inv-003", language="eng", level=9, text="Another one?",
                       options=options, label="B"),
            agent_line("invented_problems", "new-004", language="eng", level=1, text="One more?",
                       options=options, label="B"),
            agent_line("invented_problems", "inv-005", language="eng", level=1, text="Last one?",
                       options={**options, "E": "15"}, label="B"),
        ])
        self.assertEqual(code, 1)
        self.assertEqual([row["id"] for row in kept], ["inv-001"])
        self.assertLessEqual({"id", "language", "level", "text", "options", "label"}, set(kept[0]))
        self.assertIn("too close to the M3Kang problem t1", printed)
        self.assertIn("ids start with 'inv-'", printed)
        self.assertIn("level must be between 0 and 7", printed)
        self.assertIn("can't reuse an M3Kang id", printed)
        self.assertIn("two options have the same value", printed)

    def test_expression_is_safe_arithmetic(self):
        self.assertEqual(check_agent_output.evaluate_expression("(12 + 3) * 4 / 5"), 12)
        for bad in ("open('x')", "2 ** 1000", "1 / 0", "x + 1"):
            with self.assertRaises(check_agent_output.LineError):
                check_agent_output.evaluate_expression(bad)


class HintSource(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = os.path.join(folder.name, "tutor.db")

    def test_old_database_gets_the_column(self):
        import sqlite3
        old = sqlite3.connect(self.path)
        old.execute("CREATE TABLE hints (n INTEGER PRIMARY KEY AUTOINCREMENT, problem_id TEXT, "
                    "student INTEGER, text TEXT, delta REAL, convinced INTEGER, "
                    "shown INTEGER DEFAULT 0, solved_after INTEGER DEFAULT 0, ts REAL)")
        old.execute("INSERT INTO hints (problem_id, student, text, delta, convinced, ts) "
                    "VALUES ('p1', 1, 'old hint', 0.5, 1, 0)")
        old.commit()
        old.close()
        for _ in range(2):   # opening it twice must not fail on the second ALTER
            store = Store(self.path)
            hint = store.hints()[0]
            self.assertEqual((hint["source"], hint["dups"], hint["relevance"], hint["vec"],
                              hint["rejected"]), ("student", 0, None, None, None))
            self.assertEqual(store.ref_vectors("method", "geometria"), [])
            store.close()

    def test_best_hint_order(self):
        store = Store(self.path)
        self.addCleanup(store.close)
        self.assertIsNone(store.best_hint("p1"))
        bank = store.add_hint("p1", None, "from the bank", None, False, source="agent")
        store.add_hint("p1", 1, "did not convince", 3.0, False)
        self.assertEqual(store.best_hint("p1")["n"], bank)          # the bank is the fallback
        first = store.add_hint("p1", 1, "convinced, older", 1.0, True, relevance=0.2)
        second = store.add_hint("p1", 2, "convinced, newer", 1.0, True, relevance=0.2)
        self.assertEqual(store.best_hint("p1")["n"], first)         # a tie: the oldest
        store.run("UPDATE hints SET relevance = 0.5 WHERE n = ?", (second,))
        self.assertEqual(store.best_hint("p1")["n"], second)        # then relevance
        for _ in range(3):
            store.hint_shown(first)
            store.hint_solved(first)
        self.assertEqual(store.best_hint("p1")["n"], first)         # the human signal first
        for _ in range(3):
            store.hint_shown(bank)
            store.hint_solved(bank)
        self.assertEqual(store.best_hint("p1")["n"], first)         # students before the bank
        self.assertEqual(store.best_hint("p1", min_relevance=0.6)["n"], bank)
        store.add_hint("p2", None, "other bank", None, False, source="agent")
        found = store.best_neighbour_hint(["p3", "p2", "p1"])
        self.assertEqual((found["from_problem"], found["n"]), ("p1", first))  # a student's first
        self.assertEqual(store.best_neighbour_hint(["p2"])["text"], "other bank")
        self.assertIsNone(store.best_neighbour_hint(["p3"]))

    def test_assess_and_reference_vectors(self):
        store = Store(self.path)
        self.addCleanup(store.close)
        self.assertIsNone(hintsim.assess(store, "p1", "geometria", "x", None))
        self.assertIsNone(hintsim.assess(store, "p1", "geometria", "x", dead_embedder))
        import embed_refs
        store.add_hint("p1", None, "Fes un dibuix del quadrat.", None, False, source="agent")
        solutions = os.path.join(os.path.dirname(self.path), "solutions.jsonl")
        with open(solutions, "w", encoding="utf-8") as f:
            f.write(json.dumps({"id": "p1", "solution": "Side 9, area 81."}) + "\n")
        store.run("INSERT INTO problems (id, topic) VALUES ('p1', 'geometria')")
        counts = embed_refs.run(store, fake_embedder, solutions)
        self.assertEqual(counts, {"agent_hints": 1, "method": 3 * len(topics.NAMES), "solutions": 1})
        self.assertEqual(embed_refs.run(store, fake_embedder, solutions)["agent_hints"], 0)
        result = hintsim.assess(store, "p1", "geometria", "Fes un dibuix del quadrat!", fake_embedder)
        self.assertAlmostEqual(result["relevance"], 1.0, places=5)  # same words as the bank hint
        self.assertIsNone(result["duplicate_of"])                   # but the bank never duplicates
        first = store.add_hint("p1", 1, "Fes un dibuix del quadrat!", 1.0, True, vec=result["vec"])
        again = hintsim.assess(store, "p1", "geometria", "Fes un dibuix del quadrat.", fake_embedder)
        self.assertEqual(again["duplicate_of"], first)               # another student's hint does
        other = hintsim.assess(store, "p1", "geometria", "Pensa en els angles rectes.", fake_embedder)
        self.assertIsNone(other["duplicate_of"])
        self.assertLess(other["relevance"], 1.0)
        self.assertEqual(len(hintsim.from_blob(result["vec"])), 64)

    def test_add_hint_source(self):
        store = Store(self.path)
        self.addCleanup(store.close)
        store.add_hint("p1", 1, "from a student", 0.3, True)
        store.add_hint("p1", None, "from the bank", None, False, source="agent")
        self.assertEqual([h["source"] for h in store.hints()], ["student", "agent"])
        self.assertTrue(store.has_hint("p1", "from the bank", "agent"))
        self.assertFalse(store.has_hint("p1", "from the bank", "student"))
        with self.assertRaises(ValueError):
            store.add_hint("p1", 1, "x", None, False, source="teacher")

    def test_import_hints_is_idempotent(self):
        store = Store(self.path)
        store.run("INSERT INTO problems (id, label, eligible) VALUES ('t1', 'C', 1)")
        store.close()
        rows = [agent_line("hint_bank", "t1", lang="cat", hint=GOOD_HINT),
                agent_line("hint_bank", "t1", lang="cat", hint="Multiplica abans de restar."),
                agent_line("hint_bank", "zz", lang="cat", hint=GOOD_HINT)]
        path = os.path.join(os.path.dirname(self.path), "agent_hints.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            f.write("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))
        for added in (2, 0):
            printed = io.StringIO()
            with contextlib.redirect_stdout(printed):
                self.assertEqual(import_hints.main([path, "--db", self.path]), 0)
            self.assertIn(f"Added {added} hints", printed.getvalue())
        store = Store(self.path)
        self.addCleanup(store.close)
        hints = store.hints()
        self.assertEqual(len(hints), 2)
        self.assertEqual({h["source"] for h in hints}, {"agent"})
        self.assertEqual(store.best_hint("t1")["source"], "agent")   # the fallback for rung 3


class OcrPass2(unittest.TestCase):
    """laptop/ocr_pass2.py: the pure parts, without images or OCR."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, os.path.join(ROOT, "laptop"))
        import ocr_pass2
        cls.o = ocr_pass2

    @staticmethod
    def box(x0, y0, x1, y1, text):
        return ([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], text, 0.9)

    def test_fraction_joined(self):
        b = self.box
        boxes = [b(0, 15, 20, 35, "A)"), b(30, 0, 45, 20, "1"), b(30, 28, 45, 48, "2"),
                 b(100, 15, 120, 35, "B)"), b(130, 15, 145, 35, "3"),
                 b(200, 15, 220, 35, "C)"), b(230, 15, 245, 35, "4"),
                 b(300, 15, 320, 35, "D)"), b(330, 15, 345, 35, "5"),
                 b(400, 15, 420, 35, "E)"), b(430, 15, 445, 35, "6")]
        opts = self.o.parse_options(self.o.merge_fractions(boxes))
        self.assertEqual(opts, {"A": "1/2", "B": "3", "C": "4", "D": "5", "E": "6"})

    def test_two_rows_of_options_not_joined(self):
        b = self.box
        # A) 12 above D) 15: each number has its marker on its own line.
        boxes = [b(0, 0, 20, 20, "A)"), b(30, 0, 50, 20, "12"),
                 b(0, 26, 20, 46, "D)"), b(30, 26, 50, 46, "15")]
        texts = sorted(t for _, t, _ in self.o.merge_fractions(boxes))
        self.assertEqual(texts, ["12", "15", "A)", "D)"])

    def test_norm_value(self):
        n = self.o.norm_value
        self.assertEqual(n("2,5"), n("2.5"))
        self.assertEqual(n("6 x5 +6 × 2"), n("6×5+6×2"))
        self.assertEqual(n("−3"), n("-3"))
        self.assertNotEqual(n("1 17"), n("17"))

    def rows(self, eng, cat, text_only=True):
        return {("p", "eng"): {"id": "p", "language": "eng", "text_only": text_only, "options": eng},
                ("p", "cat"): {"id": "p", "language": "cat", "text_only": text_only, "options": cat}}

    def test_targets(self):
        good = dict(zip("ABCDE", "12345"))
        other = dict(zip("ABCDE", "12346"))
        t = self.o.classify_targets
        self.assertEqual(set(t(self.rows(good, good)).values()), {"recheck"})
        self.assertEqual(set(t(self.rows(good, other)).values()), {"disagree"})
        self.assertEqual(t(self.rows({}, good)), {("p", "eng"): "other_has"})
        self.assertEqual(t(self.rows({}, {}, text_only=False)), {})
        self.assertEqual(len(t(self.rows({}, {}, text_only=True))), 2)

    def test_recheck_needs_both_languages(self):
        old = {"A": "4", "B": "5", "C": "16", "D": "1 17", "E": "21"}
        fixed = {"A": "4", "B": "5", "C": "16", "D": "17", "E": "21"}
        rows = self.rows(old, old)
        targets = self.o.classify_targets(rows)
        both = self.o.decide(rows, targets, {("p", "eng"): (fixed, "ocr_crop"), ("p", "cat"): (fixed, "ocr_crop")})
        self.assertEqual(both[("p", "eng")]["options"]["D"], "17")
        one = self.o.decide(rows, targets, {("p", "eng"): (fixed, "ocr_crop"), ("p", "cat"): (old, "ocr_crop")})
        self.assertEqual(one[("p", "eng")]["options"]["D"], "1 17")
        self.assertEqual(one[("p", "eng")]["options_source"], "ocr")

    def test_skip_recheck_keeps_matching_problems(self):
        old = {"A": "4", "B": "5", "C": "16", "D": "1 17", "E": "21"}
        fixed = {"A": "4", "B": "5", "C": "16", "D": "17", "E": "21"}
        rows = self.rows(old, old)
        targets = self.o.drop_recheck(self.o.classify_targets(rows))
        self.assertEqual(targets, {})
        out = self.o.decide(rows, targets, {("p", "eng"): (fixed, "ocr_crop"), ("p", "cat"): (fixed, "ocr_crop")})
        self.assertEqual(out[("p", "eng")]["options"]["D"], "1 17")
        # Disagreeing problems are still targets.
        other = dict(old, E="22")
        self.assertEqual(set(self.o.drop_recheck(self.o.classify_targets(self.rows(old, other))).values()), {"disagree"})

    def test_empty_filled_or_copied(self):
        good = dict(zip("ABCDE", "12345"))
        rows = self.rows({}, good)
        targets = self.o.classify_targets(rows)
        out = self.o.decide(rows, targets, {("p", "eng"): ({}, "none")})
        self.assertEqual(out[("p", "eng")]["options"], good)
        self.assertEqual(out[("p", "eng")]["options_source"], "copied_cat")
        self.assertEqual(out[("p", "eng")]["options_check"], "single")
        out = self.o.decide(rows, targets, {("p", "eng"): (dict(good, E="9"), "ocr_crop")})
        self.assertEqual(out[("p", "eng")]["options_check"], "disagree")
        self.assertTrue(out[("p", "eng")]["options_suspect"])

    def test_duplicates_suspect(self):
        dup = dict(zip("ABCDE", ["1", "2", "2", "4", "5"]))
        rows = self.rows(dup, dup)
        out = self.o.decide(rows, self.o.classify_targets(rows), {})
        self.assertTrue(out[("p", "cat")]["options_suspect"])


# --- the language bridge: importing machine translations (invented problems only) ---

import import_translations  # noqa: E402

BRIDGE_OPTIONS = {"A": "8", "B": "9 pomes", "C": "10", "D": "12", "E": "14"}
BRIDGE_CAT = "1. L'Anna té 3 bosses amb 4 pomes a cada bossa. Es menja 2 pomes. Quantes en queden?"
BRIDGE_ENG = "1. Anna has 3 bags with 4 apples in each bag. She eats 2 apples. How many are left?"
BRIDGE_ESP = "1. Anna tiene 3 bolsas con 4 manzanas en cada bolsa. Se come 2 manzanas. ¿Cuántas quedan?"


def bridge_store(path, ids=("b1", "b2", "b3")):
    store = Store(path)
    for problem_id in ids:
        store.run("INSERT INTO problems (id, level, topic, label, text_only, eligible, elo) "
                  "VALUES (?, 0, 'aritmetica', 'C', 1, 1, 1000)", (problem_id,))
        for lang, text in (("cat", BRIDGE_CAT), ("eng", BRIDGE_ENG)):
            store.run("INSERT INTO texts (id, lang, text, options) VALUES (?, ?, ?, ?)",
                      (problem_id, lang, text, json.dumps(BRIDGE_OPTIONS)))
    return store


def translated(problem_id="b1", language="es", text=BRIDGE_ESP, **fields):
    options = dict(BRIDGE_OPTIONS, B="9 manzanas")
    return {"id": problem_id, "language": language, "text": text, "options": options, **fields}


class Translations(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = os.path.join(folder.name, "tutor.db")
        self.store = bridge_store(self.path)
        self.addCleanup(self.store.close)

    def run_import(self, rows, **kwargs):
        return import_translations.import_translations(self.store, rows, **kwargs)

    def test_codes_of_two_and_three_letters(self):
        report = self.run_import([
            translated("b1", "es", translation_suspect=False, language_original="eng"),
            translated("b2", "esp", translation_source="haiku"),
            translated("b3", "ZH", text="1. 安娜有3个袋子，每袋4个苹果。她吃了2个。还剩几个？"),
            translated("b1", "deu"), translated("b2", "xx")])
        self.assertEqual(report["imported"], {"esp:haiku": 1, "esp:opus-mt": 1, "zho:machine": 1})
        self.assertEqual(report["skipped"], {"language_not_allowed": 2})     # deu needs --allow
        self.assertEqual(self.store.languages(), ["cat", "eng", "esp", "zho"])
        self.assertEqual(self.store.text("b1", "esp")["source"], "opus-mt")
        self.assertEqual(self.store.text("b2", "esp")["source"], "haiku")
        self.assertEqual(self.store.text("b1", "cat")["source"], "official")
        self.assertEqual(report["missing"]["esp"], {"eligible": 3, "with_text": 2, "without_text": 1})
        self.assertEqual(report["missing"]["fra"]["with_text"], 0)
        report = self.run_import([translated("b1", "deu")], allowed=("deu",))
        self.assertEqual(report["imported"], {"deu:machine": 1})

    def test_options_numbers_copied_words_translated(self):
        row = translated()
        row["options"]["A"] = "8 "                       # a numeric option comes back untouched
        self.run_import([row])
        self.assertEqual(self.store.text("b1", "esp")["options"],
                         dict(BRIDGE_OPTIONS, B="9 manzanas"))

    def test_which_translation_is_kept(self):
        from_eng = translated(text=BRIDGE_ESP + " (eng)", language_original="eng",
                              text_original=BRIDGE_ENG, translation_suspect=False)
        from_cat = translated(text=BRIDGE_ESP + " (cat)", language_original="cat",
                              text_original=BRIDGE_CAT, translation_suspect=False)
        self.run_import([from_eng, from_cat])
        self.assertIn("(cat)", self.store.text("b1", "esp")["text"])     # esp: from Catalan
        self.run_import([dict(from_eng, language="zh"), dict(from_cat, language="zh")],
                        allowed=("zho",))
        self.assertIn("(eng)", self.store.text("b1", "zho")["text"])     # zho: from English
        # a suspect row loses to a clean one, and is only used when there is nothing else
        self.run_import([dict(from_cat, translation_suspect=True, text=BRIDGE_ESP + " (dubtosa)"),
                         from_eng])
        self.assertIn("(eng)", self.store.text("b1", "esp")["text"])
        report = self.run_import([dict(from_cat, id="b2", translation_suspect=True)])
        self.assertEqual(report["imported"], {"esp:opus-mt": 1})

    def test_translations_that_change_the_maths_are_refused(self):
        bad_option = translated("b2")
        bad_option["options"]["C"] = "11"
        fewer = translated("b3")
        del fewer["options"]["E"]
        report = self.run_import([
            translated("b1", text=BRIDGE_ESP.replace("4 manzanas", "5 manzanas")),
            bad_option, fewer,
            translated("b1", "fr", text="1. 3 4 2"),                # far too short
            translated("b2", "fr", text="   "),
            translated("nope"),
            translated("b3", "cat")])                               # never over an official text
        self.assertEqual(report["rejected"], {"esp:numbers": 1, "esp:option_value": 1,
                                              "esp:option_count": 1, "fra:length": 1, "fra:empty": 1})
        self.assertEqual(report["skipped"], {"unknown_problem": 1, "language_not_allowed": 1})
        self.assertEqual(report["imported"], {})
        self.assertEqual(self.store.languages(), ["cat", "eng"])
        self.assertEqual(self.store.text("b3", "cat")["text"], BRIDGE_CAT)

    def test_import_twice_and_dry_run(self):
        rows = [translated("b1"), translated("b2", "fr", text=BRIDGE_ESP)]
        report = self.run_import(rows, dry_run=True)
        self.assertEqual(sum(report["imported"].values()), 2)
        self.assertEqual(self.store.languages(), ["cat", "eng"])           # nothing written
        self.run_import(rows)
        first = self.store.rows("SELECT * FROM texts ORDER BY id, lang")
        again = self.run_import(rows)
        self.assertEqual(again["imported"], {"esp:machine": 1, "fra:machine": 1})
        self.assertEqual(self.store.rows("SELECT * FROM texts ORDER BY id, lang"), first)
        self.assertEqual(again["missing"]["esp"]["with_text"], 1)

    def test_another_translator_is_kept_unless_replace(self):
        # A pilot translated by another tool stays: a new OPUS-MT run doesn't overwrite it
        self.run_import([translated("b1", translation_source="haiku", text=BRIDGE_ESP + " (h)")])
        opus = translated("b1", text=BRIDGE_ESP + " (o)", translation_suspect=False)
        report = self.run_import([opus, translated("b2", translation_suspect=False)])
        self.assertEqual(report["imported"], {"esp:opus-mt": 1})
        self.assertEqual(report["skipped"], {"esp:kept_haiku": 1})
        self.assertEqual(self.store.text("b1", "esp")["source"], "haiku")
        self.assertEqual(report["missing"]["esp"]["with_text"], 2)
        report = self.run_import([opus], replace=True)
        self.assertEqual(report["imported"], {"esp:opus-mt": 1})
        self.assertEqual(self.store.text("b1", "esp")["source"], "opus-mt")

    def test_script_reports_counts_only(self):
        source = os.path.join(os.path.dirname(self.path), "es.jsonl")
        with open(source, "w", encoding="utf-8") as f:
            f.write(json.dumps(translated("b1"), ensure_ascii=False) + "\n")
        report = os.path.join(os.path.dirname(self.path), "report.json")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(import_translations.main([source, "--db", self.path, "--report", report]), 0)
        with open(report, encoding="utf-8") as f:
            written = f.read()
        for text in (out.getvalue(), written):
            self.assertNotIn("manzanas", text)                           # no problem text
        self.assertEqual(json.loads(written)["imported"], {"esp:machine": 1})
        with self.assertRaises(SystemExit):
            import_translations.main([source + ".missing", "--db", self.path])

    def test_demo_bridge_passes_the_checks(self):
        # The invented problems in French, Arabic and Chinese (tests/demo_data.py --bridge):
        # same numbers as the originals, so the import refuses none.
        folder = os.path.dirname(self.path)
        demo_data.write(folder, 30, bridge=True)
        path = os.path.join(folder, "demo.db")
        built = build_db(path, 1)                 # no embedding server: neighbours by rating
        self.assertEqual(built.returncode, 0, built.stderr)
        store = Store(path)
        self.addCleanup(store.close)
        with open(os.path.join(folder, "bridge.jsonl"), encoding="utf-8") as f:
            rows = [json.loads(line) for line in f]
        report = import_translations.import_translations(store, rows)
        self.assertEqual(report["imported"], {"arb:demo": 30, "fra:demo": 30, "zho:demo": 30})
        self.assertEqual(report["rejected"], {})
        self.assertEqual(store.languages(), ["arb", "cat", "eng", "esp", "fra", "zho"])

    def test_old_database_is_migrated(self):
        import sqlite3
        path = self.path + ".old"
        old = sqlite3.connect(path)
        old.executescript("""
            CREATE TABLE texts (id TEXT, lang TEXT, text TEXT, options TEXT, PRIMARY KEY (id, lang));
            CREATE TABLE student (id INTEGER PRIMARY KEY, name TEXT, lang_origen TEXT, level INTEGER,
                elo_cat REAL, elo_origen REAL, etapa INTEGER, streak INTEGER);
            CREATE TABLE attempts (n INTEGER PRIMARY KEY AUTOINCREMENT, student INTEGER,
                problem_id TEXT, lang TEXT, shown TEXT, answer TEXT, correct INTEGER,
                revealed INTEGER, helps INTEGER, seconds REAL, ts REAL);
            INSERT INTO texts VALUES ('b1', 'cat', 'text', '{}');
            INSERT INTO student VALUES (1, 'Test', 'esp', 1, 1100, 1180, 2, 3);
            INSERT INTO attempts (student, problem_id, lang, shown, answer, correct, revealed, helps)
                VALUES (1, 'b1', 'origen', 'both', 'C', 1, 0, 0), (1, 'b2', 'cat', 'cat', 'C', 1, 0, 0);
        """)
        old.commit()
        old.close()
        for _ in range(2):                      # opening it twice changes nothing more
            store = Store(path)
            self.assertEqual(store.text("b1", "cat")["source"], "official")
            self.assertEqual([a["origin_lang"] for a in store.attempts()], ["esp", "esp"])
            self.assertEqual(store.student_langs(), [{"student": 1, "lang": "esp", "elo": 1180,
                                                      "etapa": 2, "streak": 3}])
            student = store.student()
            store.save_student(student)             # an insert by position would break here
            store.add_attempt(1, "b3", "cat", "cat", "A", False, False, 0, 1.0)
            store.run("DELETE FROM attempts WHERE problem_id = 'b3'")
            store.add_hint("b1", 1, "une piste", None, False, lang="fra")
            self.assertEqual(store.hints()[-1]["lang"], "fra")
            store.close()


if __name__ == "__main__":
    unittest.main()
