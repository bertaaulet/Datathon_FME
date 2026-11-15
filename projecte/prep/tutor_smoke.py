#!/usr/bin/env python3
"""The tutor end to end on the board, with the final settings, timed. Run it on the board.

    python3 prep/tutor_smoke.py                 # 4 problems to fail + 6 to teach + 1 outside
    python3 prep/tutor_smoke.py --fail 2 --teach 3

It drives copilot/tutor.py exactly as the web page does, against the real model servers
and a COPY of data/tutor.db (the real one is never touched), with config.env as it is
(KANGAROO_RULE, HINTGEN, HINT_TAU from the database):

  fail   answer wrong, then the five rungs of help: method, agent hint 1, agent hint 2,
         a similar problem to try (answered), the solution
  teach  answer right; the Kangaroo must give a WRONG option; a hint with the answer must
         be rejected without spending a try; then the problem's own agent hint (step 1)
         is sent as the student's hint, and the Kangaroo's verdict and time are recorded
  outside an invented problem (prep/hintgen_problems.jsonl): harness + Kangaroo, and the
         help rungs (with HINTGEN=off, method hints)

Prints PASS/FAIL per check and writes results/tutor-smoke-<time>.csv: ids, step, seconds,
ok, and short notes. No problem text and no hint text, so nothing from M3Kang.
Stop math-tutor first (sudo systemctl stop math-tutor) so nothing else uses the model.
"""
import argparse
import csv
import json
import os
import shutil
import sys
import tempfile
import time

import common  # noqa: F401  (puts the repository on sys.path)
from copilot.config import CONFIG, ROOT
from copilot.store import Store, default_path
from copilot.tutor import KANGAROO_LANG, KANGAROO_RULE, Tutor


class Run:
    def __init__(self):
        self.rows, self.failed = [], 0

    def record(self, problem_id, step, seconds, ok, note=""):
        self.rows.append({"id": problem_id, "step": step, "seconds": round(seconds, 1),
                          "ok": int(bool(ok)), "note": note})
        self.failed += not ok
        print(f"  {'PASS' if ok else 'FAIL'}  {step:<26} {seconds:6.1f} s  {note}")


def timed(function, *args):
    began = time.perf_counter()
    result = function(*args)
    return result, time.perf_counter() - began


def wrong_letter(current):
    return next(letter for letter in "ABCDE" if letter != current["label"]
                and letter in current["options"])


def fail_one(tutor, run):
    view, seconds = timed(tutor.next)
    current = tutor.current
    pid = current["id"]
    print(f"[fail] {pid}")
    run.record(pid, "next problem", seconds, view["phase"] == "solving")
    view, seconds = timed(tutor.answer, wrong_letter(current))
    run.record(pid, "wrong answer", seconds, view["phase"] == "help")
    hints = tutor.store.agent_hints(pid)
    for rung in range(1, 6):
        before = len(view["messages"])
        view, seconds = timed(tutor.help)
        new = view["messages"][before:]
        texts = " ".join(m["text"] for m in new)
        if rung in (2, 3):
            expected = hints[rung - 2]["text"] if len(hints) > rung - 2 else None
            ok = expected is not None and expected in texts
            note = "agent hint shown" if ok else "agent hint missing"
        elif rung == 4:
            side = view["problem"] and view["problem"]["side"]
            ok = bool(side) and side["label"] is None
            note = "similar problem, answer hidden" if ok else "no similar problem"
            if side:
                letter = next(iter(side["options"]))
                view2, s2 = timed(tutor.side_answer, letter)
                run.record(pid, "similar problem answered", s2,
                           view2["problem"]["side"]["label"] is not None)
                view = view2
        elif rung == 5:
            ok = view["phase"] == "done" and view["problem"]["label"] == current["label"]
            note = "solution shown"
        else:
            ok = bool(new)
            note = "method hint"
        run.record(pid, f"help rung {rung}", seconds, ok, note)
        if view["phase"] == "done":
            break


def teach_one(tutor, run, rule):
    for _ in range(20):
        view, seconds = timed(tutor.next)
        current = tutor.current
        if tutor.store.agent_hints(current["id"]):
            break
    pid = current["id"]
    print(f"[teach] {pid}")
    precomputed = bool(current["row"].get("k_probs")) and \
        tutor.store.meta("kangaroo_lang", "eng") == KANGAROO_LANG
    run.record(pid, "next problem", seconds, view["phase"] == "solving",
               "precomputed Kangaroo" if precomputed else "Kangaroo asked live")
    view, seconds = timed(tutor.answer, current["label"])
    if view["busy"]:                       # the Kangaroo was still reading: wait for it
        while tutor.busy:
            time.sleep(0.5)
        view = tutor.view()
    ref = current["ref"]
    run.record(pid, "right answer -> teach", seconds, view["phase"] == "teach",
               "feigned" if ref and ref["feigned"] else "really wrong")
    run.record(pid, "Kangaroo says a wrong option", 0,
               bool(ref) and ref["answer"] != current["label"])
    tries = current["tries"]
    view, seconds = timed(tutor.hint, f"És la {current['label']}")
    run.record(pid, "leak rejected, no try spent", seconds,
               view["messages"][-1].get("kind") == "fuita" and current["tries"] == tries)
    hint = tutor.store.agent_hints(pid)[0]["text"]
    view, seconds = timed(tutor.hint, hint)
    event = tutor.store.hint_events()[-1]
    convinced = event["outcome"] == "convinced"
    delta = "" if event["delta"] is None else f"delta {event['delta']:+.2f}"
    ok = convinced if rule == "clean" else view["phase"] in ("teach", "done")
    run.record(pid, f"Kangaroo reads the hint", seconds, ok,
               f"{'convinced' if convinced else 'not convinced'} {delta}".strip())


def outside_one(tutor, run, problem):
    print(f"[outside] {problem['id']}")
    view, seconds = timed(tutor.external, problem["text"])
    current = tutor.current
    ok = current is not None and current["label"] in tuple("ABCDE") and current["ref"] is not None
    run.record(problem["id"], "harness + Kangaroo", seconds, ok,
               "generated hint ready" if current and current.get("generated") else "")
    view, seconds = timed(tutor.answer, wrong_letter(current))
    for rung in (1, 2, 3):
        before = len(view["messages"])
        view, seconds = timed(tutor.help)
        run.record(problem["id"], f"help rung {rung}", seconds, len(view["messages"]) > before)
    run.record(problem["id"], "warning on screen", 0, bool(view["problem"]["warning"]))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--fail", type=int, default=4)
    p.add_argument("--teach", type=int, default=6)
    p.add_argument("--db", default=default_path())
    p.add_argument("--index", default=os.path.join(ROOT, "data", "index.db"))
    p.add_argument("--problems", default=os.path.join(ROOT, "prep", "hintgen_problems.jsonl"))
    args = p.parse_args()

    folder = tempfile.mkdtemp()
    copy = os.path.join(folder, "tutor.db")
    shutil.copyfile(args.db, copy)
    store = Store(copy)
    index = None
    if os.path.exists(args.index):
        from copilot.rag import Index
        index = Index(args.index)
    rule = KANGAROO_RULE()
    tau = float(store.meta("tau", CONFIG.get("HINT_TAU", 1.0)))
    print(f"KANGAROO_RULE={rule}  tau={tau:.2f}  HINTGEN={CONFIG.get('HINTGEN')}  "
          f"KANGAROO_LANG={CONFIG.get('KANGAROO_LANG')}  Kangaroo measured in "
          f"{store.meta('kangaroo_lang', 'eng')}")
    tutor = Tutor(store, index=index, background=False)
    tutor.start("smoke", "", 3, reset=True)
    run = Run()
    began = time.time()
    for _ in range(args.fail):
        fail_one(tutor, run)
    for _ in range(args.teach):
        teach_one(tutor, run, rule)
    if os.path.exists(args.problems):
        with open(args.problems, encoding="utf-8") as f:
            problems = [json.loads(line) for line in f if line.strip()]
        if problems:
            outside_one(tutor, run, problems[0])
    counts = store.hint_counts()
    store.close()
    shutil.rmtree(folder, ignore_errors=True)

    os.makedirs(os.path.join(ROOT, "results"), exist_ok=True)
    out = os.path.join(ROOT, "results", f"tutor-smoke-{time.strftime('%Y%m%d-%H%M%S')}.csv")
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "step", "seconds", "ok", "note"])
        writer.writeheader()
        writer.writerows(run.rows)
    hint_times = [r["seconds"] for r in run.rows if r["step"] == "Kangaroo reads the hint"]
    print(f"\n{len(run.rows) - run.failed}/{len(run.rows)} checks passed in "
          f"{(time.time() - began) / 60:.1f} min. Hint counts: {counts}")
    if hint_times:
        print(f"Kangaroo with a hint: median {sorted(hint_times)[len(hint_times) // 2]} s, "
              f"worst {max(hint_times)} s")
    print(f"Wrote {out}")
    sys.exit(1 if run.failed else 0)


if __name__ == "__main__":
    main()
