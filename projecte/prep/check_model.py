#!/usr/bin/env python3
"""Run this first, on the board: does the model server give us what the project needs?

    python3 prep/check_model.py

It checks three things the whole project rests on, and prints what it found:

1. The server reports a probability for each letter A to E.
2. Asking the same problem again with a hint only reads the hint (the cache works).
3. How long both calls take.

It changes nothing. If check 1 fails, the tutor still runs, but it can only see
whether the Kangaroo's letter flips, not how far a hint moved it.
"""
import json
import time

import common  # noqa: F401  (puts the repository on the path)
from copilot.client import post
from copilot.config import CONFIG
from copilot.llm import LETTERS, URL, _top_tokens, build_messages, letter_probs, parse_letter_probs

PROBLEM = {"id": "check", "text": "Anna has 3 bags with 4 apples in each bag. She eats 2 apples. "
                                  "How many apples does she have left?",
           "options": {"A": "8", "B": "9", "C": "10", "D": "12", "E": "14"}}


def main():
    print(f"Model server: {URL}")
    top = int(CONFIG.get("LOGPROBS_TOP", 64))
    began = time.perf_counter()
    raw = post(URL, {"messages": build_messages(PROBLEM, hint="Think carefully."),
                     "grammar": "root ::= [A-E]", "max_tokens": 1, "temperature": 0,
                     "seed": int(CONFIG["SEED"]), "cache_prompt": True,
                     "logprobs": True, "top_logprobs": top, "n_probs": top}, timeout=180)
    t_first = time.perf_counter() - began
    tokens = _top_tokens(raw)
    print(f"\n1. Probabilities: the server listed {len(tokens)} candidate tokens.")
    if tokens:
        print("   First ones:", json.dumps(tokens[:8], ensure_ascii=False)[:400])
    else:
        print("   Top-level keys of the response:", sorted(raw))
        print("   choices[0] keys:", sorted(raw.get("choices", [{}])[0]))

    # The first call read the whole problem. This one differs only in the hint.
    probs, found = parse_letter_probs(raw, raw["choices"][0]["message"]["content"].strip())
    first = {"probs": probs, "found": found, "timings": raw.get("timings", {})}
    began = time.perf_counter()
    second = letter_probs(PROBLEM, hint="First count all the apples, then take away the eaten ones.",
                          timeout=180)
    t_second = time.perf_counter() - began

    found = first["found"]
    print(f"   Letters with a probability: {found} of 5.")
    print("   " + "  ".join(f"{letter}: {first['probs'][letter]:.3f}" for letter in LETTERS))
    if found == 5:
        print("   OK: all five letters are reported.")
    elif found > 0:
        print(f"   PARTLY: {5 - found} letters were outside the top {top} tokens. "
              f"Raise LOGPROBS_TOP in config.env and run this again.")
    else:
        print("   NOT WORKING: no letter probabilities. The tutor will only see letter flips.")

    read_first = first["timings"].get("prompt_n")
    read_second = second["timings"].get("prompt_n")
    print(f"\n2. Cache: the first call read {read_first} tokens, the call with a hint read {read_second}.")
    if read_first and read_second:
        if read_second < read_first / 2:
            print("   OK: the second call only read the new part.")
        else:
            print("   NOT WORKING: the second call read the problem again. Check that only one "
                  "program is using the server, and that it runs with one slot (--parallel 1).")

    print(f"\n3. Time: first call {t_first:.1f} s, call with a hint {t_second:.1f} s.")
    print("   With a hint: " + "  ".join(f"{letter}: {second['probs'][letter]:.3f}" for letter in LETTERS))


if __name__ == "__main__":
    main()
