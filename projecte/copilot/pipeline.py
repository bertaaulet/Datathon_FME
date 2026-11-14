"""The copilot's solver: one problem in, one letter out.

predict.py and eval.py both call solve(), so what's here is exactly what the
official run measures. The steps, each switched in config.env:

1. No readable options: answer the most common letter (PREDICT_NO_OPTIONS).
2. Ask the model for a probability per letter, in one call.
3. Remove the model's letter bias, if it was measured (PREDICT_DEBIAS).
4. Ask again with the options rotated, while there's time, and average
   (PREDICT_ROTATIONS). The question is cached, so a pass only re-reads the options.

Whatever goes wrong, solve() returns a letter: the official run never stops.
"""
import math
import socket
import time
import urllib.error

from .calib import letter_bias, prior_letter
from .config import CONFIG
from .llm import LETTERS, URL, letter_probs, split_problem

TIME_LIMIT = float(CONFIG["TIME_LIMIT_SECONDS"])
FALLBACK = CONFIG["FALLBACK_ANSWER"]
MARGIN = 3.0  # seconds kept free for Python and for writing the answer
# Rotation s shows the option s places further on in position A. Far apart first.
SHIFTS = (2, 4, 1, 3)


def rotation(shift):
    return "".join(LETTERS[(i + shift) % 5] for i in range(5))


def combine(passes):
    """Average several {"A": p, ...} answers (geometric mean) into one."""
    scores = {letter: sum(math.log(max(p[letter], 1e-9)) for p in passes) / len(passes)
              for letter in LETTERS}
    top = max(scores.values())
    weights = {letter: math.exp(s - top) for letter, s in scores.items()}
    total = sum(weights.values())
    return {letter: w / total for letter, w in weights.items()}


def best_letter(probs):
    """The most likely letter. Ties go to the earlier letter, so runs repeat."""
    return max(LETTERS, key=lambda letter: (probs[letter], -LETTERS.index(letter)))


def solve(problem, index=None, k=0, exclude_id=None, image_b64=None, llm_url=URL,
          time_limit=TIME_LIMIT):
    """Return {"answer", "seconds", "status", "probs", "calls", ...} for one problem.

    index and k turn on retrieval: the k most similar solved problems are
    added to the prompt as examples. Each example costs reading time.
    image_b64 and llm_url send the problem image to a vision server.
    """
    start = time.perf_counter()
    result = {"answer": FALLBACK, "status": "ok", "prompt_tokens": 0, "retrieved": "",
              "examples": [], "probs": {}, "calls": 0, "letters_found": 0}
    try:
        result["answer"] = prior_letter(problem)
        _solve(problem, result, start, index, k, exclude_id, image_b64, llm_url, time_limit)
    except (socket.timeout, TimeoutError):
        result["status"] = "timeout"
    except urllib.error.URLError as error:
        if isinstance(error.reason, (socket.timeout, TimeoutError)):
            result["status"] = "timeout"
        else:
            result["status"] = f"error: {error.reason}"
    except Exception as error:  # a reset connection, odd JSON, a bug: still answer a letter
        result["status"] = f"error: {type(error).__name__}"
    if result["answer"] not in tuple(LETTERS):
        result["answer"] = FALLBACK
    result["seconds"] = round(time.perf_counter() - start, 2)
    return result


def _solve(problem, result, start, index, k, exclude_id, image_b64, llm_url, time_limit):
    def left():
        return time_limit - (time.perf_counter() - start) - MARGIN

    _question, options = split_problem(problem)
    full = all(letter in options for letter in LETTERS)
    blind = not options and not image_b64
    if blind and CONFIG.get("PREDICT_NO_OPTIONS", "prior").lower() == "prior":
        return  # the letters mean nothing to the model: keep the most common one

    examples = []
    if index is not None and k > 0:
        hits = index.search(problem, k=k, exclude_id=exclude_id)
        examples = [p for _score, p in hits]
        result["examples"] = hits
        result["retrieved"] = ";".join(f"{p['id']}:{s:.2f}" for s, p in hits)

    bias = letter_bias() if full else None
    began = time.perf_counter()
    first = letter_probs(problem, examples, timeout=max(left(), 1.0), image_b64=image_b64,
                         url=llm_url, bias=bias)
    slowest = time.perf_counter() - began
    passes = [first["probs"]]
    result.update(calls=1, letters_found=first["found"],
                  prompt_tokens=first["timings"].get("prompt_n", 0),
                  probs=first["probs"], answer=best_letter(first["probs"]))

    wanted = int(CONFIG.get("PREDICT_ROTATIONS", 0) or 0) if full else 0
    for shift in SHIFTS[:max(wanted, 0)]:
        # A pass is cheaper than the first call when the cache works, but until
        # one has been timed, assume it costs as much.
        if left() < slowest * 1.2:
            break
        began = time.perf_counter()
        try:
            extra = letter_probs(problem, examples, timeout=max(left(), 1.0), image_b64=image_b64,
                                 url=llm_url, order=rotation(shift), bias=bias)
        except Exception:  # keep the answer we already have
            break
        took = time.perf_counter() - began
        slowest = took if result["calls"] == 1 else max(slowest, took)
        passes.append(extra["probs"])
        result["calls"] += 1
        result["probs"] = combine(passes)
        result["answer"] = best_letter(result["probs"])
