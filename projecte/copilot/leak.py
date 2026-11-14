"""Does a student's hint give the answer away? Plain rules, no model.

check(hint, label, options, statements) returns None when the hint is clean,
or a reason: "curta", "llarga", "lletra", "valor", "posicio".

What it catches: the correct letter, the correct option's value in digits or
in words, and the option's position. What it misses: indirect leaks such as
"it's twice five". Measure both kinds of mistake on a test list:

    python3 -m copilot.leak data/leak_cases.jsonl
"""
import json
import re
import sys
import unicodedata

from .config import CONFIG

LETTERS = "ABCDE"
MIN_CHARS = 8

MESSAGES = {
    "curta": "Aquesta pista és molt curta. Explica una mica més la idea.",
    "llarga": "Aquesta pista és massa llarga. Digues-ho en una o dues frases.",
    "lletra": "Ep! Has dit la lletra de la resposta. Dona una pista sense dir quina opció és.",
    "valor": "Ep! Has escrit el resultat. Explica com s'hi arriba, sense dir-lo.",
    "posicio": "Ep! Has dit quina opció és. Dona una pista sense assenyalar-la.",
}

# Number words in Catalan, Spanish and English. "un", "una", "u" and "one" are
# left out on purpose: they are articles far more often than numbers.
NUMBER_WORDS = {
    "zero": 0, "cero": 0, "dos": 2, "dues": 2, "two": 2, "tres": 3, "three": 3,
    "quatre": 4, "cuatro": 4, "four": 4, "cinc": 5, "cinco": 5, "five": 5, "sis": 6,
    "seis": 6, "six": 6, "set": 7, "siete": 7, "seven": 7, "vuit": 8, "ocho": 8,
    "eight": 8, "nou": 9, "nueve": 9, "nine": 9, "deu": 10, "diez": 10, "ten": 10,
    "onze": 11, "once": 11, "eleven": 11, "dotze": 12, "doce": 12, "twelve": 12,
    "tretze": 13, "trece": 13, "thirteen": 13, "catorze": 14, "catorce": 14,
    "fourteen": 14, "quinze": 15, "quince": 15, "fifteen": 15, "setze": 16,
    "dieciseis": 16, "sixteen": 16, "disset": 17, "diecisiete": 17, "seventeen": 17,
    "divuit": 18, "dieciocho": 18, "eighteen": 18, "dinou": 19, "diecinueve": 19,
    "nineteen": 19, "vint": 20, "veinte": 20, "twenty": 20, "trenta": 30, "treinta": 30,
    "thirty": 30, "quaranta": 40, "cuarenta": 40, "forty": 40, "cinquanta": 50,
    "cincuenta": 50, "fifty": 50, "seixanta": 60, "sesenta": 60, "sixty": 60,
    "setanta": 70, "setenta": 70, "seventy": 70, "vuitanta": 80, "ochenta": 80,
    "eighty": 80, "noranta": 90, "noventa": 90, "ninety": 90, "cent": 100, "cien": 100,
    "hundred": 100, "mil": 1000, "thousand": 1000,
}

OPTION_NOUN = r"(?:opci\w*|option|answer|resposta|respuesta|lletra|letra|soluci\w*|solution)"
POSITION_WORDS = [
    r"(?:primera|first|1a|1ª)",
    r"(?:segona|segunda|second|2a|2ª)",
    r"(?:tercera|third|3a|3ª)",
    r"(?:quarta|cuarta|fourth|4a|4ª)",
    r"(?:cinquena|quinta|fifth|5a|5ª|[uú]ltima|darrera|last)",
]
MIDDLE = r"(?:la del mig|la del medio|the middle one|la del centre|la del centro)"
NUMBER = re.compile(r"\d+(?:[.,]\d+)?(?:\s*/\s*\d+)?")


def plain(text):
    """Lower case, no accents: 'Opció' and 'opcio' compare equal."""
    decomposed = unicodedata.normalize("NFD", (text or "").lower())
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def numbers(text, words=True):
    """The numbers in a text, as normalised strings: '3,50' and '3.5' are both '3.5'."""
    found = set()
    for token in NUMBER.findall(text or ""):
        token = token.replace(" ", "").replace(",", ".")
        if "/" not in token and "." in token:
            token = token.rstrip("0").rstrip(".")
        if "/" not in token and "." not in token:
            token = token.lstrip("0") or "0"
        found.add(token)
    if words:
        for word in re.findall(r"[a-z]+", plain(text)):
            if word in NUMBER_WORDS:
                found.add(str(NUMBER_WORDS[word]))
    return found


def says_letter(hint, label, statements):
    """The correct letter, written as an answer: 'la C', 'C)', 'opció c', or a lone 'C'."""
    lowered = plain(hint)
    letter = label.lower()
    if re.search(rf"\(\s*{letter}\s*\)|\b{letter}\s*\)", lowered):
        return True
    if re.search(rf"\b{OPTION_NOUN}\s*(?:es|is|:|=)?\s*(?:la\s+|the\s+)?\(?{letter}\b", lowered):
        return True
    if re.search(rf"\b(?:la|the)\s+{letter}\b(?!['’])", lowered) or \
            re.search(rf"\bl['’]{letter}\b", lowered):
        return True
    # A lone capital letter. Not for A, which starts many sentences ("A la figura..."),
    # and not when the problem itself names things with that letter (a point C).
    if label != "A" and re.search(rf"(?<![\w'’]){label}(?![\w'’])", hint):
        named = any(re.search(rf"(?<![\w'’]){label}(?![\w'’)])", s or "") for s in statements)
        if not named:
            return True
    return False


def says_position(hint, label):
    lowered = plain(hint)
    word = plain(POSITION_WORDS[LETTERS.index(label)])
    if re.search(rf"\b{word}\s+{OPTION_NOUN}", lowered) or \
            re.search(rf"\b{OPTION_NOUN}\s+(?:\w+\s+)?{word}\b", lowered):
        return True
    return label == "C" and re.search(MIDDLE, lowered) is not None


def says_value(hint, label, options, statements):
    """The correct option's value, unless the problem statement already shows it."""
    value = str((options or {}).get(label, "")).strip()
    if not value:
        return False
    wanted = numbers(value, words=False)
    if wanted:
        in_statement = set()
        for statement in statements:
            in_statement |= numbers(statement, words=False)
        if wanted <= in_statement:
            return False
        return wanted <= numbers(hint)
    text = re.sub(r"[^a-z0-9 ]+", " ", plain(value)).strip()
    if len(text) < 3:
        return False
    if any(text in plain(statement) for statement in statements):
        return False
    return text in re.sub(r"[^a-z0-9 ]+", " ", plain(hint))


def check(hint, label, options=None, statements=()):
    """Return None for a clean hint, or the reason it's rejected."""
    hint = (hint or "").strip()
    statements = [s for s in statements if s]
    if label in tuple(LETTERS):  # a leak is the first thing to tell the student about
        if says_letter(hint, label, statements):
            return "lletra"
        if says_position(hint, label):
            return "posicio"
        if says_value(hint, label, options, statements):
            return "valor"
    if len(hint) < MIN_CHARS:
        return "curta"
    if len(hint) > int(CONFIG.get("HINT_MAX_CHARS", 200)):
        return "llarga"
    return None


def evaluate(cases):
    """Score the filter on [{"hint", "label", "options", "text", "leak": true/false}, ...]."""
    caught = missed = clean_ok = clean_rejected = 0
    mistakes = []
    for case in cases:
        reason = check(case["hint"], case["label"], case.get("options"), [case.get("text", "")])
        if case["leak"]:
            caught += reason is not None
            missed += reason is None
        else:
            clean_ok += reason is None
            clean_rejected += reason is not None
        if (reason is not None) != bool(case["leak"]):
            mistakes.append({"hint": case["hint"], "leak": case["leak"], "reason": reason})
    return {"leaks": caught + missed, "leaks_caught": caught, "leaks_missed": missed,
            "clean": clean_ok + clean_rejected, "clean_accepted": clean_ok,
            "clean_rejected": clean_rejected, "mistakes": mistakes}


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    with open(sys.argv[1], encoding="utf-8") as f:
        cases = [json.loads(line) for line in f if line.strip()]
    report = evaluate(cases)
    print(f"Leaks caught:   {report['leaks_caught']}/{report['leaks']}")
    print(f"Clean accepted: {report['clean_accepted']}/{report['clean']}")
    for mistake in report["mistakes"]:
        kind = "MISSED LEAK " if mistake["leak"] else "REJECTED OK "
        print(f"  {kind} {mistake['hint']!r} ({mistake['reason']})")
    if len(sys.argv) > 2:  # also write the counts, for the dashboard
        with open(sys.argv[2], "w", encoding="utf-8") as out:
            json.dump({k: v for k, v in report.items() if k != "mistakes"}, out)


if __name__ == "__main__":
    main()
