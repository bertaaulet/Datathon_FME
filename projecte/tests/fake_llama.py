#!/usr/bin/env python3
"""A stand-in for the two llama.cpp servers, to try the code without the board.

    python3 tests/fake_llama.py --answers data/demo/train.jsonl data/demo/val.jsonl

It listens on the ports in config.env (8081 and 8082) and answers the same
requests as llama-server. It is NOT a language model: its "opinions" come from
a hash of the text, a built-in letter bias, a little knowledge of the right
answer, and a rule that a hint sharing words with the problem helps. It exists
to check that the plumbing works. Every number it produces is meaningless:
never report a result measured against it.
"""
import argparse
import hashlib
import json
import math
import os
import re
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

LETTERS = "ABCDE"
BIAS = {"A": 0.6, "B": 0.0, "C": -0.2, "D": 0.9, "E": -0.4}   # like the real model: loves D and A
SKILL = 0.8          # how much it favours the right option
NEUTRAL = ("think carefully.", "pensa-ho bé.")   # the neutral hints, English and Catalan
HINT_LABELS = ("Hint from a classmate: ", "Pista d'un company: ")
GENERATED_HINT = "Fixa't bé en les dades de l'enunciat i escriu-les ordenades."
STOP = {"with", "from", "that", "this", "what", "have", "many", "then", "first", "quina",
        "quant", "quants", "quantes", "primer", "despres", "després", "calcula", "pensa"}


class Model:
    """Shared state: what the fake knows, how fast it is, and what it has cached."""

    def __init__(self, answers=None, delay=0.0, shape="openai"):
        self.answers = answers or {}    # question text -> the text of the right option
        self.delay = delay              # seconds per token "read"
        self.shape = shape              # openai, native, or none (no probabilities)
        self.last_prompt = ""
        self.calls = []
        self.fail_next = 0              # answer this many requests with an error
        self.lock = threading.Lock()

    def learn(self, problems):
        for problem in problems:
            options = problem.get("options") or {}
            if problem.get("label") in options:
                self.answers[problem["text"].strip()] = str(options[problem["label"]])


def noise(*parts):
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).digest()
    return digest[0] / 127.5 - 1.0   # -1 to 1, the same every time


def words(text):
    return {w for w in re.findall(r"[a-zà-ÿ]{4,}", text.lower()) if w not in STOP}


def read_prompt(messages):
    content = messages[-1]["content"]
    if isinstance(content, list):
        content = "\n".join(part.get("text", "") for part in content if part.get("type") == "text")
    question, options, hint = [], {}, ""
    for line in content.split("\n"):
        match = re.match(r"^([A-E])\) (.*)$", line)
        if match:
            options[match.group(1)] = match.group(2)
        elif line.startswith(HINT_LABELS):
            label = next(lab for lab in HINT_LABELS if line.startswith(lab))
            hint = line[len(label):]
        elif line.strip() not in ("Answer:", "Resposta:", "Expression:"):
            question.append(line)
    full = "\n".join(json.dumps(m["content"], ensure_ascii=False) for m in messages)
    return "\n".join(question).strip(), options, hint, full


def letter_logits(model, question, options, hint):
    right = model.answers.get(question)
    boost = 0.0
    if hint and hint.strip().lower() not in NEUTRAL:
        shared = len(words(hint) & words(question))
        boost = 2.5 if shared >= 2 else 1.0 if shared == 1 else 0.2 * noise("hint", hint, question)
    logits = {}
    for letter in LETTERS:
        value = options.get(letter, "")
        logit = BIAS[letter] + noise(question, value)
        if right is not None and value == right:
            logit += SKILL + boost
        logits[letter] = logit
    return logits


def fake_expression(model, question, options):
    """Like a weak model: often the right value, written as a sum; sometimes a wrong one."""
    from copilot.mathexpr import option_value
    right = option_value(model.answers.get(question))
    if right is None or noise("expr", question) < -0.3:
        numbers = re.findall(r"\d+", question) or ["1"]
        return " + ".join(numbers[:3])
    whole = int(right) if right == int(right) else right
    return f"{whole} - 1 + 1"


def completion(model, request):
    question, options, hint, full = read_prompt(request["messages"])
    if str(request.get("grammar", "")).startswith("root ::= [^"):   # a hint (copilot/hintgen.py)
        with model.lock:
            model.calls.append({"question": question, "hint": "", "prompt_n": len(full) // 4,
                                "options": options, "hint_writer": True})
        return {"choices": [{"index": 0, "finish_reason": "stop",
                             "message": {"role": "assistant", "content": GENERATED_HINT}}],
                "timings": {"prompt_n": len(full) // 4, "predicted_n": len(GENERATED_HINT) // 2}}
    if str(request.get("grammar", "")).startswith("root ::= expr"):
        with model.lock:
            model.calls.append({"question": question, "hint": "", "prompt_n": len(full) // 4,
                                "options": options, "expression": True})
        text = fake_expression(model, question, options)
        return {"choices": [{"index": 0, "finish_reason": "stop",
                             "message": {"role": "assistant", "content": text}}],
                "timings": {"prompt_n": len(full) // 4, "predicted_n": len(text) // 2}}
    logits = letter_logits(model, question, options, hint)
    # Other tokens compete with the letters, as in the real model before the grammar
    tokens = dict(logits)
    tokens.update({"The": 0.3, "\n": -0.5, " ": -1.0, "Answer": -1.5, " C": logits["C"] - 2.0})
    total = math.log(sum(math.exp(v) for v in tokens.values()))
    ranked = sorted(tokens.items(), key=lambda kv: -kv[1])
    top = [{"token": tok, "logprob": value - total, "bytes": list(tok.encode())}
           for tok, value in ranked[:int(request.get("top_logprobs") or request.get("n_probs") or 0)]]
    generated = max(LETTERS, key=lambda letter: (logits[letter], -LETTERS.index(letter)))

    with model.lock:
        common = 0
        for a, b in zip(model.last_prompt, full):
            if a != b:
                break
            common += 1
        if not request.get("cache_prompt"):
            common = 0
        prompt_n = max(1, (len(full) - common) // 4)
        model.last_prompt = full
        model.calls.append({"question": question, "hint": hint, "prompt_n": prompt_n,
                            "options": options})
    if model.delay:
        time.sleep(model.delay * prompt_n)

    response = {
        "choices": [{"index": 0, "finish_reason": "length",
                     "message": {"role": "assistant", "content": generated}}],
        "timings": {"prompt_n": prompt_n, "predicted_n": 1,
                    "prompt_per_second": 11.0, "predicted_per_second": 6.0},
    }
    entry = {"token": generated, "logprob": logits[generated] - total, "top_logprobs": top}
    if model.shape == "openai" and top:
        response["choices"][0]["logprobs"] = {"content": [entry]}
    elif model.shape == "native" and top:
        response["completion_probabilities"] = [entry]
    return response


def embedding(text, size=384):
    vector = [0.0] * size
    for word in re.findall(r"\w+", text.lower()):
        digest = hashlib.sha256(word.encode("utf-8")).digest()
        vector[int.from_bytes(digest[:2], "big") % size] += 1.0 if digest[2] % 2 else -1.0
    return vector


def handler_for(model, kind):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def send(self, status, payload):
            body = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/health":
                self.send(200, {"status": "ok"})
            elif self.path == "/props":
                self.send(200, {"modalities": {"vision": False}})
            else:
                self.send(404, {"error": "not found"})

        def do_POST(self):
            request = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            with model.lock:
                failing = model.fail_next > 0
                model.fail_next -= failing
            if failing:
                self.send(500, {"error": "the fake server was told to fail"})
            elif kind == "llm" and self.path == "/v1/chat/completions":
                self.send(200, completion(model, request))
            elif kind == "embed" and self.path == "/v1/embeddings":
                texts = request["input"] if isinstance(request["input"], list) else [request["input"]]
                self.send(200, {"data": [{"index": i, "embedding": embedding(t)}
                                         for i, t in enumerate(texts)]})
            else:
                self.send(404, {"error": "not found"})

    return Handler


def start(model=None, llm_port=0, embed_port=0):
    """Start both servers in threads. Port 0 picks a free port. Returns (model, llm, embed)."""
    model = model or Model()
    servers = []
    for kind, port in (("llm", llm_port), ("embed", embed_port)):
        server = ThreadingHTTPServer(("127.0.0.1", port), handler_for(model, kind))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        servers.append(server)
    return model, servers[0], servers[1]


def main():
    from copilot.config import CONFIG
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--answers", nargs="*", default=[], help="problem files the fake may 'know'")
    p.add_argument("--delay", type=float, default=0.0, help="seconds per token read (the board: 0.09)")
    p.add_argument("--shape", default="openai", choices=["openai", "native", "none"])
    args = p.parse_args()
    model = Model(delay=args.delay, shape=args.shape)
    for path in args.answers:
        with open(path, encoding="utf-8") as f:
            model.learn(json.loads(line) for line in f if line.strip())
    _model, llm, embed = start(model, int(CONFIG["LLM_PORT"]), int(CONFIG["EMBED_PORT"]))
    print(f"FAKE model servers on ports {llm.server_port} and {embed.server_port}. "
          f"Not a language model: don't report anything measured with it. Ctrl+C to stop.")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
