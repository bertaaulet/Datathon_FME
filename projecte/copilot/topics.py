"""A topic for every problem, from keywords. M3Kang has no topic field.

The classifier is a plain keyword count, so it's fast, the same every time,
and easy to explain in the write-up. It's also rough: check it by hand on 50
problems (prep/build_tutor_db.py --show-topics) before you trust a table by topic.

Each topic has a Catalan name and two or three method hints written by the
team. They are general problem-solving advice, not derived from any M3Kang
problem, so they can be published.
"""
import re

# (key, Catalan name, keywords, method hints). English and Catalan keywords.
# A keyword matches at the start of a word, so "triangle" also finds "triangles".
# A keyword that ends with a space must be the whole word: "even " skips "evening".
TOPICS = [
    ("geometria", "Geometria", [
        "triangle", "square", "rectangle", "circle", "angle", "perimeter", "area", "cube",
        "polygon", "diagonal", "parallel", "perpendicular", "radius", "diameter", "shape",
        "figure", "hexagon", "pentagon", "side length", "vertex", "vertices", "symmetr",
        "quadrat", "cercle", "perímetre", "àrea", "cub ", "polígon", "costat", "vèrtex",
    ], [
        "Fes un dibuix i escriu-hi totes les mides que saps.",
        "Mira si pots partir la figura en trossos més senzills.",
        "Busca què es manté igual: costats iguals, angles iguals o simetries.",
    ]),
    ("comptar", "Comptar i combinar", [
        "how many ways", "how many different", "in how many", "arrange", "combination",
        "possibilit", "choose", "different ways", "order ", "de quantes maneres",
        "quantes maneres", "combinaci", "ordenar",
    ], [
        "Fes una llista ordenada de tots els casos, sense saltar-te'n cap.",
        "Comença amb un cas més petit i mira com creix.",
        "Vigila de no comptar el mateix cas dues vegades.",
    ]),
    ("nombres", "Nombres i divisibilitat", [
        "digit", "divisible", "multiple", "prime ", "remainder", "even ", "odd ", "divisor",
        "factor ", "consecutive", "integer", "xifra", "divisible", "múltiple", "primer ",
        "residu", "parell", "senar", "consecutiu",
    ], [
        "Prova amb exemples petits i busca què tenen en comú.",
        "Fixa't en l'última xifra o en si el nombre és parell o senar.",
        "Descompon els nombres en factors.",
    ]),
    ("fraccions", "Fraccions, percentatges i proporcions", [
        "fraction", "percent", "%", "half ", "third ", "quarter", "ratio", "proportion",
        "twice", "fracci", "per cent", "meitat", "terç", "quart ", "doble", "proporci",
    ], [
        "Tria un total fàcil, com 100 o 12, i calcula amb aquest.",
        "Escriu totes les parts amb la mateixa unitat abans de comparar-les.",
        "Pregunta't: quina part del total és cada tros?",
    ]),
    ("temps", "Temps i calendari", [
        "clock", "hour", "minute", "o'clock", "day", "week", "month", "year", "calendar",
        "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
        "birthday", "age ", "years old", "rellotge", "hora ", "minut", "dia ", "setmana",
        "mes ", "anys ", "calendari", "edat",
    ], [
        "Fes una línia del temps i marca-hi el que saps.",
        "Passa-ho tot a la mateixa unitat: minuts, dies o anys.",
        "Mira quant passa en una volta sencera (un dia, una setmana) i quant sobra.",
    ]),
    ("mesura", "Mesura i velocitat", [
        "cm ", "metre", "meter", "kg ", "gram", "litre", "liter", "weigh", "length",
        "distance", "speed", "km ", "tall", "heavy", "pes ", "pesa", "longitud",
        "distància", "velocitat", "alçada",
    ], [
        "Escriu què mesura cada nombre i en quina unitat.",
        "Passa totes les mides a la mateixa unitat abans de calcular.",
        "Fes un esquema amb les distàncies o els pesos.",
    ]),
    ("logica", "Lògica", [
        "true", "false", "lie ", "liar", "truth", "statement", "says ", "exactly one",
        "always", "never", "cert ", "fals", "menteix", "mentider", "veritat", "afirmaci",
        "sempre", "mai ",
    ], [
        "Suposa que una afirmació és certa i mira si porta a una contradicció.",
        "Fes una taula amb totes les possibilitats i ves descartant.",
        "Comença per la dada que deixa menys opcions.",
    ]),
    ("probabilitat", "Probabilitat", [
        "probability", "chance", "dice", "die ", "coin", "random", "probabilitat",
        "dau", "moneda", "atzar",
    ], [
        "Compta tots els casos possibles i quants t'interessen.",
        "Fes una llista o un arbre amb tots els resultats.",
    ]),
    ("patrons", "Patrons i àlgebra", [
        "sequence", "pattern", "equation", "unknown", "expression", "next number",
        "rule ", "term ", "seqüència", "patró", "equaci", "incògnita", "expressi", "terme ",
    ], [
        "Posa un nom al que no saps i escriu què en diu l'enunciat.",
        "Calcula els primers casos i busca la regla.",
        "Prova de treballar cap enrere, des del final fins a l'inici.",
    ]),
    ("aritmetica", "Càlcul i problemes amb nombres", [
        "sum ", "total ", "altogether", "costs", "price", "euro", "calculate", "value of",
        "product", "difference", "suma", "preu", "calcula", "valor", "producte", "diferència",
    ], [
        "Escriu què saps i què et demanen abans de calcular.",
        "Fes el càlcul per parts i comprova cada pas.",
        "Estima primer el resultat: quines opcions no poden ser?",
    ]),
]

DEFAULT = "aritmetica"
NAMES = {key: name for key, name, _words, _hints in TOPICS}
HINTS = {key: hints for key, _name, _words, hints in TOPICS}
_PATTERNS = [(key, [re.compile((r"" if word[0] in "%" else r"\b") + re.escape(word.strip()))
                    for word in words]) for key, _name, words, _hints in TOPICS]


def classify(text):
    """Return the topic key with the most keyword hits. Ties go to the first topic."""
    lowered = (text or "").lower()
    best, best_score = DEFAULT, 0
    for key, patterns in _PATTERNS:
        score = sum(len(pattern.findall(lowered)) for pattern in patterns)
        if score > best_score:
            best, best_score = key, score
    return best


def name(key):
    return NAMES.get(key, NAMES[DEFAULT])


def method_hint(key, n=0):
    hints = HINTS.get(key, HINTS[DEFAULT])
    return hints[n % len(hints)]
