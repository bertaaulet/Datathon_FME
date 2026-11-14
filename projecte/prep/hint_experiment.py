#!/usr/bin/env python3
"""The go / no-go experiment: does the Kangaroo tell a good hint from a nonsense one?

Step 1. Make a file to fill in, with 25 problems the model gets wrong:

    python3 prep/hint_experiment.py --make-template 25

Step 2. Open data/hints_experiment.jsonl and write, for every problem, three hints
        (in the language your students will use):

    "good"  a real hint that doesn't give the answer away
    "bad"   a nonsense hint of about the same length ("Pensa en el teu color preferit.")
    "leak"  a hint that gives the answer away ("La resposta és 10."), as the ceiling

Step 3. Run it on the board (about 1 minute per problem):

    python3 prep/hint_experiment.py

For each hint it measures delta: how far the hint moved the Kangaroo's margin
towards the right answer, compared with a hint that says nothing. It prints a
summary, suggests the threshold tau, and writes results/hints-<time>.csv (ids
and numbers only) for the dashboard.

What to look for: good hints should beat nonsense hints clearly more often than
half the time, and the call with a hint should take a few seconds. If good and
nonsense hints move the Kangaroo alike, the bar on the LED matrix means nothing:
drop that part and keep the rest of the tutor (see the README).
"""
import argparse
import csv
import json
import math
import os
import statistics
import time

import common
from copilot import leak
from copilot.config import CONFIG
from copilot.llm import letter_probs
from copilot.store import Store, default_path
from copilot.tutor import NEUTRAL_HINT, kangaroo

KINDS = ("good", "bad", "leak")


def make_template(store, count, path):
    lang, shown = CONFIG.get("MODEL_LANG", "eng"), CONFIG.get("TUTOR_LANG", "cat")
    rows = store.rows("SELECT id, label, k_margin FROM problems WHERE eligible = 1 ORDER BY id")
    measured = [r for r in rows if r["k_margin"] is not None]
    pool = [r for r in measured if r["k_margin"] < 0] if measured else rows
    if not measured:
        print("Tip: run prep/kangaroo_baseline.py first, to pick problems the model gets wrong.")
    chosen = common.sample(pool, count)
    with open(path, "w", encoding="utf-8") as f:
        for row in chosen:
            text = store.text(row["id"], shown) or store.text(row["id"], lang)
            options = text["options"] or store.text(row["id"], lang)["options"]
            f.write(json.dumps({"id": row["id"], "text": text["text"], "options": options,
                                "label": row["label"], "good": "", "bad": "", "leak": ""},
                               ensure_ascii=False) + "\n")
    print(f"Wrote {path} with {len(chosen)} problems. Fill in good, bad and leak for each one, "
          f"then run this script again without --make-template. Don't commit the file: it holds "
          f"M3Kang text.")


def sign_test(wins, losses):
    """Two-sided sign test: how likely is a split this uneven if hints made no difference?"""
    n = wins + losses
    if n == 0:
        return None
    tail = sum(math.comb(n, k) for k in range(max(wins, losses), n + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--db", default=default_path())
    p.add_argument("--hints", default="data/hints_experiment.jsonl")
    p.add_argument("--make-template", type=int, default=0, metavar="N")
    p.add_argument("--no-save-tau", action="store_true", help="don't store tau in the database")
    args = p.parse_args()

    store = Store(args.db)
    if args.make_template:
        make_template(store, args.make_template, args.hints)
        return
    cases = [c for c in common.read_jsonl(args.hints) if any(c.get(kind) for kind in KINDS)]
    if not cases:
        raise SystemExit(f"No hints in {args.hints}. Start with --make-template 25.")

    lang = CONFIG.get("MODEL_LANG", "eng")
    os.makedirs("results", exist_ok=True)
    out_path = f"results/hints-{time.strftime('%Y%m%d-%H%M%S')}.csv"
    deltas = {kind: [] for kind in KINDS}
    seconds, read, pairs, filter_hits = [], [], [], {kind: 0 for kind in KINDS}
    with open(out_path, "w", newline="", encoding="utf-8") as out:
        writer = csv.writer(out)
        writer.writerow(["id", "kind", "delta", "margin_ref", "margin_after", "seconds",
                         "prompt_tokens", "filter"])
        for n, case in enumerate(cases, 1):
            text = store.text(case["id"], lang)
            if not text:
                print(f"  {case['id']}: not in the database, skipped")
                continue
            problem = {"id": case["id"], "text": text["text"], "options": text["options"]}
            try:
                ref = kangaroo(letter_probs(problem, hint=NEUTRAL_HINT, timeout=180)["probs"],
                               case["label"])
            except Exception as error:
                print(f"  {case['id']}: {error}")
                continue
            got = {}
            for kind in KINDS:
                hint = (case.get(kind) or "").strip()
                if not hint:
                    continue
                reason = leak.check(hint, case["label"], case.get("options") or text["options"],
                                    [case.get("text", ""), text["text"]])
                filter_hits[kind] += reason is not None
                began = time.perf_counter()
                try:
                    answer = letter_probs(problem, hint=hint, timeout=180)
                except Exception as error:
                    print(f"  {case['id']} {kind}: {error}")
                    continue
                took = time.perf_counter() - began
                after = kangaroo(answer["probs"], case["label"])
                delta = after["margin"] - ref["margin"]
                got[kind] = delta
                deltas[kind].append(delta)
                seconds.append(took)
                read.append(answer["timings"].get("prompt_n", 0))
                writer.writerow([case["id"], kind, f"{delta:.4f}", f"{ref['margin']:.4f}",
                                 f"{after['margin']:.4f}", f"{took:.2f}",
                                 answer["timings"].get("prompt_n", ""), reason or ""])
                out.flush()
            if "good" in got and "bad" in got:
                pairs.append((got["good"], got["bad"]))
            print(f"[{n}/{len(cases)}] {case['id']}: "
                  + "  ".join(f"{kind} {got[kind]:+.2f}" for kind in KINDS if kind in got), flush=True)

    print("\n" + "=" * 62)
    print("delta = how far a hint moved the Kangaroo towards the right answer")
    for kind in KINDS:
        values = deltas[kind]
        if values:
            print(f"  {kind:5} n={len(values):3}  median {statistics.median(values):+.2f}  "
                  f"moved it the right way in {sum(v > 0 for v in values)}/{len(values)}  "
                  f"(the leak filter rejected {filter_hits[kind]})")
    tau = None
    if deltas["bad"]:
        tau = max(common.percentile(deltas["bad"], 90), 0.1)
        print(f"\nSuggested tau: {tau:.2f}  (9 nonsense hints in 10 move the Kangaroo less than this)")
        if deltas["good"]:
            above = sum(v > tau for v in deltas["good"])
            print(f"Good hints above tau: {above}/{len(deltas['good'])}")
    if pairs:
        wins = sum(good > bad for good, bad in pairs)
        losses = sum(good < bad for good, bad in pairs)
        p_value = sign_test(wins, losses)
        print(f"\nSame problem, good against nonsense: good wins {wins}, nonsense wins {losses}, "
              f"ties {len(pairs) - wins - losses}.")
        print(f"Sign test: p = {p_value:.3f}  (small p: the difference is unlikely to be luck)")
        if len(pairs) < 20:
            print(f"Only {len(pairs)} problems: treat this as a first look, not a result.")
    if seconds:
        print(f"\nA call with a hint: median {statistics.median(seconds):.1f} s, "
              f"worst {max(seconds):.1f} s, {statistics.median(read):.0f} tokens read.")
    if tau is not None and not args.no_save_tau:
        store.set_meta("tau", f"{tau:.4f}")
        with open("data/tau.json", "w", encoding="utf-8") as f:
            json.dump({"tau": tau, "n_bad": len(deltas["bad"]), "source": out_path}, f)
        print(f"\nStored tau = {tau:.2f} in the tutor database.")
    print(f"Details: {out_path}")
    store.close()


if __name__ == "__main__":
    main()
