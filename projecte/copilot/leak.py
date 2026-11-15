"""Does a student's hint give the answer away? Plain rules, no model.

check(hint, label, options, statements) returns None when the hint is clean,
or a reason: "curta", "llarga", "lletra", "valor", "posicio".

What it catches: the correct letter, the correct option's value in digits or
in words, and the option's position, in the six languages of the language bridge
(Catalan, Spanish, English, French, Arabic and Chinese). What it misses: indirect
leaks such as "it's twice five". Measure both kinds of mistake on a test list:

    python3 -m copilot.leak data/leak_cases.jsonl
"""
import json
import re
import sys
import unicodedata

from .config import CONFIG

LETTERS = "ABCDE"
MIN_CHARS = 8
MIN_CHARS_CJK = 4       # a Chinese sentence needs far fewer characters

MESSAGES = {
    "curta": "Aquesta pista és molt curta. Explica una mica més la idea.",
    "llarga": "Aquesta pista és massa llarga. Digues-ho en una o dues frases.",
    "lletra": "Ep! Has dit la lletra de la resposta. Dona una pista sense dir quina opció és.",
    "valor": "Ep! Has escrit el resultat. Explica com s'hi arriba, sense dir-lo.",
    "posicio": "Ep! Has dit quina opció és. Dona una pista sense assenyalar-la.",
}

# Number words in Catalan, Spanish and English (French and Arabic follow). "un", "una",
# "u" and "one" are left out on purpose: they are articles far more often than numbers.
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
    # compounds written as one word, and the hundreds
    "veintiuno": 21, "veintidos": 22, "veintitres": 23, "veinticuatro": 24, "veinticinco": 25,
    "veintiseis": 26, "veintisiete": 27, "veintiocho": 28, "veintinueve": 29,
    "cents": 100, "ciento": 100, "cientos": 100, "hundreds": 100,
    "doscientos": 200, "trescientos": 300, "cuatrocientos": 400, "quinientos": 500,
    "seiscientos": 600, "setecientos": 700, "ochocientos": 800, "novecientos": 900,
    # French ("quatre", "six", "onze", "quinze" and "cent" are above)
    "deux": 2, "trois": 3, "cinq": 5, "sept": 7, "huit": 8, "neuf": 9, "dix": 10,
    "douze": 12, "treize": 13, "quatorze": 14, "seize": 16, "vingt": 20, "vingts": 20,
    "trente": 30, "quarante": 40, "cinquante": 50, "soixante": 60, "septante": 70,
    "huitante": 80, "octante": 80, "nonante": 90, "mille": 1000,
    # Arabic, as plain() leaves it: no hamza on the alef, final ة as ه
    "صفر": 0, "واحد": 1, "واحده": 1, "اثنان": 2, "اثنين": 2, "اثنتان": 2, "اثنتين": 2,
    "اثنا": 2, "اثني": 2, "اثنتا": 2, "اثنتي": 2, "ثلاثه": 3, "ثلاث": 3, "اربعه": 4,
    "اربع": 4, "خمسه": 5, "خمس": 5, "سته": 6, "ست": 6, "سبعه": 7, "سبع": 7, "ثمانيه": 8,
    "ثماني": 8, "ثمان": 8, "تسعه": 9, "تسع": 9, "عشره": 10, "عشر": 10, "عشرون": 20,
    "عشرين": 20, "ثلاثون": 30, "ثلاثين": 30, "اربعون": 40, "اربعين": 40, "خمسون": 50,
    "خمسين": 50, "ستون": 60, "ستين": 60, "سبعون": 70, "سبعين": 70, "ثمانون": 80,
    "ثمانين": 80, "تسعون": 90, "تسعين": 90, "مئه": 100, "مائه": 100, "مئتان": 200,
    "مئتين": 200, "مائتان": 200, "مائتين": 200, "الف": 1000, "الاف": 1000, "الفان": 2000,
    "الفين": 2000,
}
# "one" only counts inside a longer number: "vint-i-un", "twenty-one", "أحد عشر"
ONE_WORDS = {"un", "una", "u", "uno", "one", "une", "احد", "احدي"}
JOINERS = {"i", "y", "et", "and", "e"}      # "trenta-i-dos", "treinta y dos", "vingt et un"
CHINESE_DIGITS = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
                  "六": 6, "七": 7, "八": 8, "九": 9}
CHINESE_UNITS = {"十": 10, "百": 100, "千": 1000, "万": 10000}
CHINESE_NUMBER = re.compile("(第?)([%s]+)" % "".join(list(CHINESE_DIGITS) + list(CHINESE_UNITS)))
# Arabic-Indic and Persian digits; full-width forms fold to ASCII in normal()
OTHER_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹٫٬", "01234567890123456789.,")
ARABIC_LETTERS = {"A": "ا", "B": "ب", "C": "ج", "D": "د", "E": "ه"}   # أ ب ج د هـ, as plain() leaves them
CJK = re.compile(r"[\u3400-\u9fff]")
ARABIC = re.compile(r"[\u0600-\u06ff]")
OTHER_SCRIPT = re.compile(r"[\u0600-\u06ff\u3400-\u9fff]")
# A word's start and end for a Latin letter. Arabic and Chinese characters don't make a
# word with it: Chinese has no spaces, so "答案是B" must count as a lone B.
WORD_CHAR = r"[^\W\u0600-\u06ff\u3040-\u9fff]"
START = rf"(?<!{WORD_CHAR})"
END = rf"(?!{WORD_CHAR})"

OPTION_NOUN = (r"(?:opci\w*|options?|answer|resposta|respuesta|reponse|lletra|letra|lettre|choix|"
               r"soluci\w*|solution|الجواب|الاجابه|الخيار|الحرف|الحل|答案|选项|选|答)")
IS = r"(?:es|is|est|c['’]est|هو|هي|是|为|:|=)"
POSITION_WORDS = [
    r"(?:primera|first|premiere|1a|1ª|1ere|الاولي|الاول)",
    r"(?:segona|segunda|second|seconde|deuxieme|2a|2ª|2e|الثانيه|الثاني)",
    r"(?:tercera|third|troisieme|3a|3ª|3e|الثالثه|الثالث)",
    r"(?:quarta|cuarta|fourth|quatrieme|4a|4ª|4e|الرابعه|الرابع)",
    r"(?:cinquena|quinta|fifth|cinquieme|derniere|5a|5ª|5e|[uú]ltima|darrera|last|"
    r"الخامسه|الخامس|الاخيره|الاخير)",
]
CHINESE_POSITION = ["一1", "二2", "三3", "四4", "五5"]
MIDDLE = (r"(?:la del mig|la del medio|the middle one|la del centre|la del centro|celle du milieu|"
          r"(?:option|reponse) du milieu|(?:الخيار|الجواب|الاجابه)\s+(?:الاوسط|الوسطي)|"
          r"中间的?(?:那个|一个|选项|答案|项))")
NUMBER = re.compile(r"\d+(?:[.,]\d+)?(?:\s*/\s*\d+)?")
WORD = re.compile(r"[^\W\d_]+")


def normal(text):
    """One way to write each character: full-width forms (Ｂ, ３) and Arabic-Indic digits
    become ASCII. Not a full NFKC, which would also turn the ² of "cm²" into a number."""
    folded = "".join(chr(ord(ch) - 0xFEE0) if "\uff01" <= ch <= "\uff5e" else ch for ch in text or "")
    return folded.replace("\u3000", " ").translate(OTHER_DIGITS)


def plain(text):
    """Lower case, no accents: 'Opció' and 'opcio' compare equal. Arabic loses its
    vowel marks and hamzas, and ة, ى and the tatweel are written one way."""
    decomposed = unicodedata.normalize("NFD", normal(text).lower())
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return stripped.replace("ة", "ه").replace("ى", "ي").replace("ـ", "")


# The tables above are written as people write; compare them as plain() leaves a text
NUMBER_WORDS = {plain(word): value for word, value in NUMBER_WORDS.items()}
ONE_WORDS = {plain(word) for word in ONE_WORDS}


def _arabic(word):
    """An Arabic number word without its "and" (و) or its article (ال), or None."""
    if not ARABIC.search(word):
        return None
    for prefix in ("", "و", "ال", "وال"):
        rest = word[len(prefix):]
        if word.startswith(prefix) and (rest in NUMBER_WORDS or rest in ONE_WORDS):
            return rest
    return None


def _join(run, value, word, arabic):
    """Add a number word to the number being read: (thousands, rest, last word's value).

    Returns the new state when the word continues the number ("vint" + "tres", "quatre" +
    "vingt", "dos" + "cents", "ثلاثة" + "عشرون"), or None when it starts another one.
    """
    if run is None:
        return None
    total, rest, last = run
    tail = rest % 100
    after_big = tail == 0 and (rest > 0 or total > 0)       # after "hundred" or "thousand"
    if value == 1000:
        return (total + max(rest, 1) * 1000, 0, value) if rest or not total else None
    if value == 100:
        return (total, rest * 100, value) if 1 <= rest <= 9 else None
    if word in ("vingt", "vingts") and tail == 4 and last == 4:      # quatre-vingt
        return total, rest + 76, value
    if 1 <= value <= 9:
        fits = tail % 10 == 0 and (tail > 0 or after_big)
        return (total, rest + value, value) if fits else None
    if 10 <= value <= 19:
        # French "soixante-dix"; Arabic "ثلاثة عشر" (three + ten)
        fits = tail in (60, 80) or after_big or (arabic and value == 10 and 1 <= tail <= 9)
        return (total, rest + value, value) if fits else None
    if value < 100:
        # Arabic says the unit first: "ثلاثة وعشرون" is 23
        fits = after_big or (arabic and value % 10 == 0 and 1 <= tail <= 9)
        return (total, rest + value, value) if fits else None
    return (total, rest + value, value) if rest == 0 and total else None


def word_numbers(text):
    """The numbers written in words in a text that plain() has been through.

    Every number word counts on its own, and so does the number that neighbouring words
    add up to ("quatre-vingt-dix-sept" is 4, 20, 10, 7 and 97): better one hint too many
    sent back than a result given away.
    """
    found = set()
    run, end, joined = None, None, False
    for match in WORD.finditer(text):
        word = match.group()
        if end is not None and text[end:match.start()].strip(" -‐‑") != "":
            run = None                       # something else in between: another number
        end = match.end()
        arabic = _arabic(word)
        if arabic is None and OTHER_SCRIPT.search(word):
            run = None                       # Chinese numbers are read apart
            continue
        key = arabic or word
        if key in JOINERS and run is not None:
            continue                         # keeps the number open
        if key in ONE_WORDS:
            value, counts = 1, False
        elif key in NUMBER_WORDS:
            value, counts = NUMBER_WORDS[key], True
        else:
            run = None
            continue
        if counts:
            found.add(str(value))
        longer = _join(run, value, key, arabic is not None)
        if longer:
            run = longer
            found.add(str(run[0] + run[1]))
        elif value == 1000:
            run = (1000, 0, value)
        else:
            run = (0, value, value)
    for ordinal, digits in CHINESE_NUMBER.findall(text):
        if ordinal or digits == "一":         # "第三步" is a step, and a lone 一 an article
            continue
        if not any(ch in CHINESE_UNITS for ch in digits):
            found.add(str(int("".join(str(CHINESE_DIGITS[ch]) for ch in digits))))
            continue
        total = section = digit = 0
        for ch in digits:
            if ch in CHINESE_DIGITS:
                digit = CHINESE_DIGITS[ch]
            elif ch == "万":
                total, section, digit = total + max(section + digit, 1) * 10000, 0, 0
            else:
                section, digit = section + max(digit, 1) * CHINESE_UNITS[ch], 0
        found.add(str(total + section + digit))
    return found


def numbers(text, words=True):
    """The numbers in a text, as normalised strings: '3,50' and '3.5' are both '3.5'."""
    found = set()
    text = normal(text)
    for token in NUMBER.findall(text):
        token = token.replace(" ", "").replace(",", ".")
        if "/" not in token and "." in token:
            token = token.rstrip("0").rstrip(".")
        if "/" not in token and "." not in token:
            token = token.lstrip("0") or "0"
        found.add(token)
    if words:
        found |= word_numbers(plain(text))
    return found


def says_letter(hint, label, statements):
    """The correct letter, written as an answer: 'la C', 'C)', 'opció c', '答案是C', or a lone 'C'."""
    hint = normal(hint)
    lowered = plain(hint)
    letter = label.lower()
    if re.search(rf"\(\s*{letter}\s*\)|{START}{letter}\s*\)", lowered):
        return True
    # not before an apostrophe: "la resposta d'aquest problema" names no option
    if re.search(rf"{START}{OPTION_NOUN}\s*{IS}?\s*(?:la\s+|the\s+|le\s+)?\(?{letter}{END}(?!['’])",
                 lowered):
        return True
    if re.search(rf"{START}(?:la|the|le)\s+{letter}{END}(?!['’])", lowered) or \
            re.search(rf"{START}l['’]{letter}{END}", lowered):
        return True
    # Arabic may name the options with its own letters: "الجواب ب"
    if re.search(rf"{OPTION_NOUN}\s*{IS}?\s*\(?{ARABIC_LETTERS[label]}(?![\u0600-\u06ff])", lowered):
        return True
    named = any(re.search(rf"{START}(?<!['’]){label}{END}(?![)'’])", normal(s))
                for s in statements)
    # A lone capital letter. Not for A, which starts many sentences ("A la figura..."),
    # and not when the problem itself names things with that letter (a point C).
    if label != "A" and not named and re.search(rf"{START}(?<!['’]){label}{END}(?!['’])", hint):
        return True
    # In Arabic or Chinese a lone Latin letter is no word of the sentence: any A-E counts,
    # unless the problem uses that letter itself (a side a, a point B)
    if OTHER_SCRIPT.search(hint) and re.search(rf"{START}{letter}{END}(?!['’])", lowered):
        return not any(re.search(rf"{START}{letter}{END}(?![)'’])", plain(s)) for s in statements)
    return False


def says_position(hint, label):
    lowered = plain(hint)
    word = plain(POSITION_WORDS[LETTERS.index(label)])
    if re.search(rf"\b{word}\s+{OPTION_NOUN}", lowered) or \
            re.search(rf"\b{OPTION_NOUN}\s+(?:\w+\s+)?{word}\b", lowered):
        return True
    # "és la tercera", "it's the third one", "c'est la troisième": the ordinal alone ends
    # the sentence. "la tercera bossa" goes on with a noun, and passes.
    if re.search(rf"(?:\b{IS}|it\s+is|it['’]s)\s+(?:la|el|the|le)\s+{word}(?:\s+one)?\s*(?:[.!?,;]|$)",
                 lowered) or re.search(rf"\bthe\s+{word}\s+one\b", lowered):
        return True
    nth = CHINESE_POSITION[LETTERS.index(label)]
    if re.search(rf"第[{nth}]个?(?:选项|答案|项)|[选答]第[{nth}]", lowered):
        return True
    if label == "E" and re.search(r"最后一?个?(?:选项|答案|项)", lowered):
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
    text = _words(value)
    if len(text) < (2 if CJK.search(text) else 3):
        return False
    if any(text in _words(statement) for statement in statements):
        return False
    return text in _words(hint)


def _words(text):
    """Letters and digits only, in any script, with single spaces."""
    return " ".join(re.sub(r"[^\w ]+", " ", plain(text)).split())


def check(hint, label, options=None, statements=()):
    """Return None for a clean hint, or the reason it's rejected."""
    hint = normal(hint).strip()
    statements = [s for s in statements if s]
    if label in tuple(LETTERS):  # a leak is the first thing to tell the student about
        if says_letter(hint, label, statements):
            return "lletra"
        if says_position(hint, label):
            return "posicio"
        if says_value(hint, label, options, statements):
            return "valor"
    if len(hint) < (MIN_CHARS_CJK if CJK.search(hint) else MIN_CHARS):
        return "curta"
    if len(hint) > int(CONFIG.get("HINT_MAX_CHARS", 200)):
        return "llarga"
    return None


def check_strict(hint, options=None, statements=()):
    """For a problem from outside the bank, whose answer nobody can be sure of.

    The answer used there comes from the harness and may be wrong, so a hint may name
    no option at all: no letter, no position and no option's value. Returns None or a reason.
    """
    letters = [letter for letter in LETTERS if letter in (options or {})] or list(LETTERS)
    for letter in letters:
        reason = check(hint, letter, options, statements)
        if reason in ("lletra", "posicio", "valor"):
            return reason
    return check(hint, None, options, statements)


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
