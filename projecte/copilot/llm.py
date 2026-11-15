"""Ask the small language model about a problem: one letter, or a probability per letter."""
import math
import re
import urllib.error

from .config import CONFIG
from .client import post

URL = f"http://127.0.0.1:{CONFIG['LLM_PORT']}/v1/chat/completions"
LETTERS = "ABCDE"

# Keep the system prompt stable: llama-server caches the start of the prompt,
# so text that never changes is only read once.
SYSTEM = ("You solve multiple-choice math competition problems for school students. "
          "Read the problem and the options, then reply with the letter of the correct option.")

# The Kangaroo of the tutor reads in Catalan (KANGAROO_LANG=cat), so the student's Catalan
# hint arrives in the same language as everything around it. predict.py never passes a
# language and keeps the English prompt above.
KANGAROO_SYSTEM = {
    "cat": ("Resols problemes de matemàtiques de tipus test per a alumnes d'escola. "
            "Llegeix el problema i les opcions, i respon amb la lletra de l'opció correcta."),
}
HINT_LABEL = {"cat": "Pista d'un company: ", "eng": "Hint from a classmate: "}
ANSWER_LABEL = {"cat": "Resposta:", "eng": "Answer:"}

# "A) 12   B) 15 ..." written inside the question text
_MARKER = r"(?:^|(?<=\s))\(?{letter}\)\s*"


def split_problem(problem):
    """Return (question, options). Reads the options from the text when the field is empty."""
    text = (problem.get("text") or "").strip()
    options = problem.get("options") or {}
    if options:
        return text, options
    starts, position = [], 0
    for letter in LETTERS:
        match = re.compile(_MARKER.format(letter=letter)).search(text, position)
        if not match:
            return text, {}
        starts.append(match)
        position = match.end()
    found = {}
    for i, letter in enumerate(LETTERS):
        end = starts[i + 1].start() if i < 4 else len(text)
        found[letter] = text[starts[i].end():end].strip()
    if not all(found.values()):
        return text, {}
    return text[:starts[0].start()].strip(), found


def format_problem(problem, sees_image=False, order=None):
    """order="CDEAB" shows the original option C in position A, D in B, and so on."""
    question, options = split_problem(problem)
    lines = [question]
    for position, letter in enumerate(LETTERS):
        source = order[position] if order else letter
        if source in options:
            lines.append(f"{letter}) {options[source]}")
    if not options:
        lines.append("(The options are in the picture.)" if sees_image else
                     "(The options are in a picture that you can't see. Pick the most likely letter.)")
    return "\n".join(lines)


def correct_value(example):
    """The text of a solved problem's right option, or None when OCR didn't read it."""
    _question, options = split_problem(example)
    value = options.get(example.get("label", ""))
    return " ".join(str(value).split()) if value not in (None, "") else None


def solved_example(example):
    """A retrieved problem as a worked example: its question and the right VALUE, no options.

    The letter of another problem says nothing about this one, and the four wrong
    options only cost reading time.
    """
    question, _options = split_problem(example)
    return f"Similar solved problem:\n{question}\nCorrect answer: {correct_value(example)}\n\n"


def build_messages(problem, examples=(), image_b64=None, order=None, hint=None, lang=None):
    """image_b64 is a PNG as base64 text. Only a server started with --mmproj can see it.

    hint goes after the problem, so the cached start of the prompt is reused.
    lang="cat" writes the Kangaroo's prompt in Catalan (the tutor only); None keeps
    predict.py's English prompt.
    Examples (RAG) follow PREDICT_RAG_FORMAT: "answer" (default) puts each solved
    problem's question and right value before the new problem, in the same message;
    "letter" is the organizers' format (full problem, then its letter as a reply).
    """
    lang = lang if lang in KANGAROO_SYSTEM else None   # None: predict.py's English prompt
    messages = [{"role": "system", "content": KANGAROO_SYSTEM[lang] if lang else SYSTEM}]
    lead = ""
    if CONFIG.get("PREDICT_RAG_FORMAT", "answer").lower() == "letter":
        for ex in examples:
            messages.append({"role": "user", "content": format_problem(ex) + "\nAnswer:"})
            messages.append({"role": "assistant", "content": ex["label"]})
    elif examples:
        lead = "".join(solved_example(ex) for ex in examples) + "Now solve this problem.\n"
    text = lead + format_problem(problem, sees_image=bool(image_b64), order=order)
    if hint:
        text += "\n" + HINT_LABEL[lang or "eng"] + " ".join(hint.split())
    text += "\n" + ANSWER_LABEL[lang or "eng"]
    if image_b64:
        content = [{"type": "image_url", "image_url": {"url": "data:image/png;base64," + image_b64}},
                   {"type": "text", "text": text}]
    else:
        content = text
    messages.append({"role": "user", "content": content})
    return messages


EXPR_SYSTEM = ("You solve multiple-choice math competition problems for school students. "
               "Write one arithmetic expression whose value is the correct answer. "
               "Use only numbers, + - * / ^ and parentheses. Do not compute it.")
EXPR_MAX_TOKENS = 32


def expression(problem, timeout=60, url=URL):
    """Ask the model to write the answer as an expression. Return (text, timings).

    A grammar (copilot/mathexpr.py) allows only numbers, operators and
    parentheses, so Python can compute the value exactly.
    """
    from .mathexpr import GRAMMAR
    messages = [{"role": "system", "content": EXPR_SYSTEM},
                {"role": "user", "content": format_problem(problem) + "\nExpression:"}]
    response = post(url, {
        "messages": messages,
        "grammar": GRAMMAR,
        "max_tokens": EXPR_MAX_TOKENS,
        "temperature": 0,
        "seed": int(CONFIG["SEED"]),
        "cache_prompt": True,
    }, timeout=timeout)
    return response["choices"][0]["message"]["content"].strip(), response.get("timings", {})


def answer_letter(problem, examples=(), timeout=60, image_b64=None, url=URL):
    """Return (letter, timings). The grammar makes any other output impossible."""
    response = post(url, {
        "messages": build_messages(problem, examples, image_b64),
        "grammar": "root ::= [A-E]",
        "max_tokens": 1,
        "temperature": 0,
        "seed": int(CONFIG["SEED"]),
        "cache_prompt": True,
    }, timeout=timeout)
    letter = response["choices"][0]["message"]["content"].strip()
    return letter, response.get("timings", {})


def _top_tokens(node):
    """Find the first list of candidate tokens in a llama-server response, whatever its shape."""
    if isinstance(node, dict):
        for key in ("top_logprobs", "top_probs"):
            if isinstance(node.get(key), list) and node[key]:
                return node[key]
        for value in node.values():
            found = _top_tokens(value)
            if found:
                return found
    elif isinstance(node, list):
        for value in node:
            found = _top_tokens(value)
            if found:
                return found
    return []


def parse_letter_probs(response, generated):
    """Return ({"A": p, ..., "E": p}, how many letters the server reported).

    The server lists its top tokens with a log probability each. We keep the
    five letters and share 100% among them. A letter that isn't listed is less
    likely than every listed token, so it gets a small floor. With no list at
    all, the generated letter gets almost everything (found = 0).
    """
    mass, lowest = {}, None
    for entry in _top_tokens(response):
        if not isinstance(entry, dict):
            continue
        if "prob" in entry:
            p = float(entry["prob"])
        elif "logprob" in entry:
            p = math.exp(float(entry["logprob"]))
        else:
            continue
        lowest = p if lowest is None else min(lowest, p)
        token = str(entry.get("token", "")).strip()
        if len(token) == 1 and token in LETTERS:
            mass[token] = mass.get(token, 0.0) + p
    found = len(mass)
    if not mass:
        if generated in tuple(LETTERS):
            probs = {letter: 0.01 for letter in LETTERS}
            probs[generated] = 0.96
        else:
            probs = {letter: 0.2 for letter in LETTERS}
        return probs, 0
    floor = max((lowest or 1e-6) * 0.5, 1e-9)
    if generated in tuple(LETTERS) and generated not in mass:
        mass[generated] = max(mass.values()) * 1.01  # the grammar chose it, so it leads
    probs = {letter: mass.get(letter, floor) for letter in LETTERS}
    total = sum(probs.values())
    return {letter: p / total for letter, p in probs.items()}, found


def letter_probs(problem, examples=(), timeout=60, image_b64=None, url=URL, order=None,
                 hint=None, bias=None, lang=None):
    """One model call. Return {"letter", "probs", "found", "timings"}.

    probs maps each ORIGINAL option letter to a probability, also when order
    rotates the options. bias maps a position (A to E) to how often the model
    says it whatever the problem; dividing by it removes the letter bias.
    found is how many of the five letters the server reported: 0 means the
    server sent no probabilities, and probs is only a guess from the letter.
    """
    top = int(CONFIG.get("LOGPROBS_TOP", 64))
    payload = {
        "messages": build_messages(problem, examples, image_b64, order=order, hint=hint,
                                   lang=lang),
        "grammar": "root ::= [A-E]",
        "max_tokens": 1,
        "temperature": 0,
        "seed": int(CONFIG["SEED"]),
        "cache_prompt": True,
        "logprobs": True,
        "top_logprobs": top,
        "n_probs": top,
    }
    try:
        response = post(url, payload, timeout=timeout)
    except urllib.error.HTTPError as error:
        # A server that refuses this many top tokens (4xx): ask again with the old 64
        if not 400 <= error.code < 500 or top <= 64:
            raise
        payload.update(top_logprobs=64, n_probs=64)
        response = post(url, payload, timeout=timeout)
    generated = response["choices"][0]["message"]["content"].strip()
    by_position, found = parse_letter_probs(response, generated)
    if bias:
        adjusted = {letter: by_position[letter] / max(float(bias.get(letter, 0.2)), 1e-6)
                    for letter in LETTERS}
        total = sum(adjusted.values())
        by_position = {letter: p / total for letter, p in adjusted.items()}
    if order:
        probs = {order[i]: by_position[letter] for i, letter in enumerate(LETTERS)}
        if generated in tuple(LETTERS):
            generated = order[LETTERS.index(generated)]
    else:
        probs = by_position
    return {"letter": generated, "probs": probs, "found": found,
            "timings": response.get("timings", {})}
