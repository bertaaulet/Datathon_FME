"""The languages of the tutor: one place for their names, for the server and the page.

Codes are M3Kang's (three letters). BRIDGE lists the languages the Kangaroo's own
phrases exist in (copilot/phrases.py); the problems of each one are in the database
only if they were prepared (official M3Kang text, or prep/import_translations.py).
"""
import re

BRIDGE = ("cat", "eng", "esp", "fra", "arb", "zho")

# How each language calls itself: what the student reads when choosing one
NAMES = {
    "cat": "Català", "eng": "English", "esp": "Castellano", "fra": "Français",
    "arb": "العربية", "zho": "中文", "deu": "Deutsch", "tur": "Türkçe", "vie": "Tiếng Việt",
    "ind": "Bahasa Indonesia", "swh": "Kiswahili", "kor": "한국어", "jpn": "日本語",
    "lit": "Lietuvių", "ron": "Română", "urd": "اردو", "ukr": "Українська", "rus": "Русский",
    "por": "Português", "ita": "Italiano",
}
# The name in Catalan, for a sentence written in Catalan
CATALAN = {"cat": "català", "eng": "anglès", "esp": "castellà", "fra": "francès",
           "arb": "àrab", "zho": "xinès", "deu": "alemany"}
# Two-letter codes, for the page's lang attribute (fonts, hyphenation, screen readers)
ISO1 = {"cat": "ca", "eng": "en", "esp": "es", "fra": "fr", "deu": "de", "ita": "it", "por": "pt",
        "arb": "ar", "zho": "zh", "tur": "tr", "vie": "vi", "ind": "id", "swh": "sw", "kor": "ko",
        "jpn": "ja", "lit": "lt", "ron": "ro", "urd": "ur", "ukr": "uk", "rus": "ru"}

CJK = re.compile(r"[㐀-鿿]")
ARABIC = re.compile(r"[؀-ۿ]")
# A few very common words of each Latin-script language: enough to tell a one-sentence
# hint apart most of the time, and nothing more than a guess.
COMMON = {
    "cat": {"el", "els", "les", "amb", "què", "és", "i", "per", "dels", "això", "però", "quants",
            "quantes", "fes", "mira", "compta", "cada", "després", "hi", "ha", "com", "més",
            "primer", "quina", "quin", "si", "al", "aquest", "aquesta"},
    "esp": {"el", "los", "las", "con", "qué", "es", "y", "por", "del", "esto", "pero", "cuántos",
            "cuántas", "haz", "cuenta", "cada", "después", "hay", "como", "más", "primero",
            "cuál", "si", "al", "este", "esta", "luego"},
    "fra": {"le", "les", "des", "avec", "est", "et", "pour", "une", "du", "ce", "mais", "combien",
            "fais", "regarde", "compte", "chaque", "après", "il", "dans", "plus", "que", "qui",
            "puis", "si", "au", "cette", "ensuite"},
    "eng": {"the", "and", "with", "is", "for", "of", "this", "but", "how", "many", "count",
            "each", "then", "first", "you", "it", "to", "in", "what", "if", "that", "are"},
}


def name(code):
    return NAMES.get(code, code)


def catalan(code):
    return CATALAN.get(code, NAMES.get(code, code))


def table():
    """What the page needs to show a language: its own name and its two-letter code."""
    return {code: {"name": NAMES[code], "iso": ISO1.get(code)} for code in NAMES}


def guess(text, default=None):
    """The language a short text seems written in: a guess, kept only as data."""
    text = text or ""
    if CJK.search(text):
        return "zho"
    if ARABIC.search(text):
        return "arb"
    words = set(re.findall(r"[^\W\d_]+", text.lower()))
    scores = sorted(((len(words & common), lang) for lang, common in COMMON.items()), reverse=True)
    if scores[0][0] == 0 or scores[0][0] == scores[1][0]:
        return default
    return scores[0][1]
