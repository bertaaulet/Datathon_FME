"""A one-sentence hint for a problem from outside the bank, written by the board's model.

Bank problems have the agent's hints (prep/import_hints.py). An outside problem has
none, so the model writes one, with ONE similar bank problem as the example: its
statement and its first agent hint (docs/DECISIONS.md, 2026-11-15). Two neighbours
come close to the time limit, and a hint without its statement is a poor example.

The hint always goes through the strict leak filter (copilot.leak.check_strict): the
answer of an outside problem comes from the harness and may be wrong, so the hint may
name no option at all. If it fails, or the model doesn't answer, the caller shows a
topic's method hint instead. Options are left out of the prompt on purpose: fewer
tokens to read, and less to leak.

Standard library only. Temperature 0 and SEED, like every model call.
"""
import re

from . import leak
from .client import post
from .config import CONFIG
from .llm import URL

SYSTEM = ("Ets un tutor de matemàtiques per a alumnes d'escola. Escriu UNA sola frase en català "
          "amb una pista de mètode per començar el problema: què han de mirar o per on començar. "
          "No facis el càlcul, no diguis la resposta ni cap resultat, i no parlis de les opcions.")
# One line that ends at the first full stop: the hint is one sentence.
GRAMMAR = r'root ::= [^\n.?!]+ [.?!]'


def enabled():
    return str(CONFIG.get("HINTGEN", "on")).strip().lower() not in ("off", "0", "no", "")


def max_tokens():
    return int(CONFIG.get("HINTGEN_MAX_TOKENS", 48))


def messages(problem_text, example_text, example_hint):
    user = (f"Problema semblant:\n{example_text.strip()}\nPista: {example_hint.strip()}\n\n"
            f"Problema nou:\n{problem_text.strip()}\nPista:")
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]


def clean(text):
    """One sentence, no surrounding quotes or spaces."""
    text = " ".join((text or "").split()).strip(" \"'«»")
    first = re.match(r"(.+?[.?!])(\s|$)", text)
    return first.group(1) if first else text


def generate(problem, example_text, example_hint, timeout=90, url=URL, post_fn=post):
    """Return (hint, reason): a clean hint and None, or None and why there is none.

    problem: {"text", "options"}. reason is a leak.check reason, "buida" or "error".
    """
    try:
        response = post_fn(url, {
            "messages": messages(problem["text"], example_text, example_hint),
            "grammar": GRAMMAR,
            "max_tokens": max_tokens(),
            "temperature": 0,
            "seed": int(CONFIG["SEED"]),
            "cache_prompt": True,
        }, timeout=timeout)
        hint = clean(response["choices"][0]["message"]["content"])
    except Exception:
        return None, "error"
    if not hint:
        return None, "buida"
    reason = leak.check_strict(hint, problem.get("options") or {}, [problem["text"]])
    return (None, reason) if reason else (hint, None)
