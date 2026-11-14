"""A topic for every problem, from keywords. M3Kang has no topic field.

The classifier is a plain keyword count, so it's fast, the same every time,
and easy to explain in the write-up. It's also rough: check it by hand on 50
problems (prep/build_tutor_db.py --show-topics) before you trust a table by topic.

Each topic has a Catalan name and three method hints written by the team:
actionable, in the second person, under 120 characters, and never pointing at a
value or an option. They are general problem-solving advice, not derived from any M3Kang
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
        "possibilit", "choose", "different ways", "de quantes maneres",
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
        "Descompon els nombres en factors primers i compara'ls.",
    ]),
    ("fraccions", "Fraccions, percentatges i proporcions", [
        "fraction", "percent", "%", "half ", "third ", "quarter", "ratio", "proportion",
        "twice", "fracci", "per cent", "meitat", "terç", "quart ", "doble", "proporci",
    ], [
        "Si no et diuen el total, inventa't un total fàcil i calcula amb aquest.",
        "Escriu totes les parts amb la mateixa unitat abans de comparar-les.",
        "Pregunta't quina part del total és cada tros.",
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
        "cert ", "fals", "menteix", "mentider", "veritat", "afirmaci",
    ], [
        "Suposa que una afirmació és certa i mira si porta a una contradicció.",
        "Fes una taula amb totes les possibilitats i ves descartant.",
        "Comença per la dada que deixa menys possibilitats.",
    ]),
    ("probabilitat", "Probabilitat", [
        "probability", "chance", "dice", "die ", "coin", "random", "probabilitat",
        "dau", "moneda", "atzar",
    ], [
        "Compta tots els casos possibles i quants t'interessen.",
        "Fes una llista o un arbre amb tots els resultats.",
        "Comprova que tots els casos que comptes tenen la mateixa probabilitat.",
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
        "sum ", "total ", "altogether", "costs", "price", "euro",
        "product", "difference", "suma", "preu", "producte", "diferència",
    ], [
        "Escriu què saps i què et demanen abans de calcular.",
        "Fes el càlcul per parts i comprova cada pas.",
        "Abans de calcular, estima més o menys quant ha de sortir.",
    ]),
]

# The same method hints in the other languages of the plan (M3Kang codes), for the
# language bridge: same order as the Catalan list, one translation per hint.
# Checked by back-translation into Catalan; no native speaker has reviewed them,
# least of all arb (Modern Standard Arabic) and zho (Simplified Chinese).
TRANSLATIONS = {
    "geometria": {
        "eng": ["Make a drawing and write on it every measurement you know.",
                "See if you can split the figure into simpler pieces.",
                "Look for what stays the same: equal sides, equal angles or symmetries."],
        "esp": ["Haz un dibujo y escribe en él todas las medidas que conoces.",
                "Mira si puedes dividir la figura en trozos más sencillos.",
                "Busca lo que se mantiene igual: lados iguales, ángulos iguales o simetrías."],
        "fra": ["Fais un dessin et écris-y toutes les mesures que tu connais.",
                "Regarde si tu peux découper la figure en morceaux plus simples.",
                "Cherche ce qui reste pareil : côtés égaux, angles égaux ou symétries."],
        "arb": ["ارسم شكلاً واكتب عليه كل القياسات التي تعرفها.",
                "انظر إن كان بإمكانك تقسيم الشكل إلى أجزاء أبسط.",
                "ابحث عمّا يبقى ثابتاً: أضلاع متساوية أو زوايا متساوية أو تماثل."],
        "zho": ["画一张图，把你知道的所有尺寸都标上去。",
                "看看能不能把图形分成几个更简单的部分。",
                "找找哪些东西保持不变：相等的边、相等的角或对称。"],
    },
    "comptar": {
        "eng": ["Make an ordered list of all the cases, without skipping any.",
                "Start with a smaller case and see how it grows.",
                "Be careful not to count the same case twice."],
        "esp": ["Haz una lista ordenada de todos los casos, sin saltarte ninguno.",
                "Empieza con un caso más pequeño y mira cómo crece.",
                "Ten cuidado de no contar el mismo caso dos veces."],
        "fra": ["Fais une liste ordonnée de tous les cas, sans en oublier aucun.",
                "Commence par un cas plus petit et regarde comment il grandit.",
                "Fais attention à ne pas compter deux fois le même cas."],
        "arb": ["اكتب قائمة مرتبة بكل الحالات دون أن تنسى أيّاً منها.",
                "ابدأ بحالة أصغر ولاحظ كيف تكبر.",
                "انتبه ألا تعدّ الحالة نفسها مرتين."],
        "zho": ["按顺序列出所有情况，一个也不要漏掉。",
                "先从一个更小的情况开始，看看数量怎样增长。",
                "注意不要把同一种情况数两次。"],
    },
    "nombres": {
        "eng": ["Try small examples and look for what they have in common.",
                "Look at the last digit, or at whether the number is even or odd.",
                "Break the numbers into prime factors and compare them."],
        "esp": ["Prueba con ejemplos pequeños y busca qué tienen en común.",
                "Fíjate en la última cifra o en si el número es par o impar.",
                "Descompón los números en factores primos y compáralos."],
        "fra": ["Essaie avec de petits exemples et cherche ce qu'ils ont en commun.",
                "Regarde le dernier chiffre, ou si le nombre est pair ou impair.",
                "Décompose les nombres en facteurs premiers et compare-les."],
        "arb": ["جرّب أمثلة صغيرة وابحث عمّا يجمع بينها.",
                "انظر إلى الرقم الأخير، أو إلى كون العدد زوجياً أو فردياً.",
                "حلّل الأعداد إلى عوامل أولية وقارن بينها."],
        "zho": ["试几个小例子，找找它们有什么共同点。",
                "看看最后一位数字，或者这个数是奇数还是偶数。",
                "把这些数分解成质因数，再比较一下。"],
    },
    "fraccions": {
        "eng": ["If the total isn't given, pick an easy total and work with it.",
                "Write all the parts in the same unit before comparing them.",
                "Ask yourself what part of the whole each piece is."],
        "esp": ["Si no te dan el total, invéntate un total fácil y calcula con él.",
                "Escribe todas las partes con la misma unidad antes de compararlas.",
                "Pregúntate qué parte del total es cada trozo."],
        "fra": ["Si on ne te donne pas le total, choisis un total facile et calcule avec ce total.",
                "Écris toutes les parts dans la même unité avant de les comparer.",
                "Demande-toi quelle part du total représente chaque morceau."],
        "arb": ["إذا لم تُذكر الكمية الكلية، فاختر كمية سهلة واحسب بها.",
                "اكتب كل الأجزاء بالوحدة نفسها قبل أن تقارن بينها.",
                "اسأل نفسك: ما الجزء الذي يمثله كل قسم من الكل؟"],
        "zho": ["如果题目没给总数，就自己选一个好算的总数来算。",
                "先把所有部分换成同一种单位，再比较。",
                "问问自己：每一块是整体的几分之几？"],
    },
    "temps": {
        "eng": ["Draw a timeline and mark on it what you know.",
                "Change everything to the same unit: minutes, days or years.",
                "See how long one full cycle is (a day, a week) and how much is left over."],
        "esp": ["Haz una línea del tiempo y marca en ella lo que sabes.",
                "Pásalo todo a la misma unidad: minutos, días o años.",
                "Mira cuánto dura una vuelta entera (un día, una semana) y cuánto sobra."],
        "fra": ["Trace une ligne du temps et marques-y ce que tu sais.",
                "Convertis tout dans la même unité : minutes, jours ou années.",
                "Regarde combien dure un cycle complet (un jour, une semaine) et ce qui reste."],
        "arb": ["ارسم خطاً زمنياً وضع عليه ما تعرفه.",
                "حوّل كل شيء إلى الوحدة نفسها: دقائق أو أيام أو سنوات.",
                "انظر كم تستغرق دورة كاملة (يوم أو أسبوع) وكم يتبقى."],
        "zho": ["画一条时间线，把你知道的标上去。",
                "把所有时间换成同一种单位：分钟、天或年。",
                "看看一整圈（一天、一周）是多少，还剩下多少。"],
    },
    "mesura": {
        "eng": ["Write down what each number measures and in which unit.",
                "Change all the measurements to the same unit before calculating.",
                "Draw a diagram with the distances or the weights."],
        "esp": ["Escribe qué mide cada número y en qué unidad.",
                "Pasa todas las medidas a la misma unidad antes de calcular.",
                "Haz un esquema con las distancias o los pesos."],
        "fra": ["Écris ce que mesure chaque nombre et dans quelle unité.",
                "Convertis toutes les mesures dans la même unité avant de calculer.",
                "Fais un schéma avec les distances ou les poids."],
        "arb": ["اكتب ماذا يقيس كل عدد وبأي وحدة.",
                "حوّل كل القياسات إلى الوحدة نفسها قبل الحساب.",
                "ارسم مخططاً للمسافات أو الأوزان."],
        "zho": ["写下每个数表示什么，单位是什么。",
                "计算之前，先把所有量换成同一种单位。",
                "画一张示意图，标出距离或重量。"],
    },
    "logica": {
        "eng": ["Assume one statement is true and check whether it leads to a contradiction.",
                "Make a table with every possibility and rule out the ones that don't work.",
                "Start with the clue that leaves the fewest possibilities."],
        "esp": ["Supón que una afirmación es cierta y mira si lleva a una contradicción.",
                "Haz una tabla con todas las posibilidades y ve descartando.",
                "Empieza por el dato que deja menos posibilidades."],
        "fra": ["Suppose qu'une affirmation est vraie et vérifie si cela mène à une contradiction.",
                "Fais un tableau avec toutes les possibilités et élimine celles qui ne marchent pas.",
                "Commence par l'indice qui laisse le moins de possibilités."],
        "arb": ["افترض أن إحدى العبارات صحيحة وتحقق إن كان ذلك يؤدي إلى تناقض.",
                "ارسم جدولاً بكل الاحتمالات واستبعد ما لا يصح منها.",
                "ابدأ بالمعلومة التي تترك أقل عدد من الاحتمالات."],
        "zho": ["假设某一句话是真的，看看会不会推出矛盾。",
                "列一张表写出所有可能，再把不可能的一个一个排除。",
                "从留下可能性最少的那条线索开始。"],
    },
    "probabilitat": {
        "eng": ["Count all the possible cases and how many of them you want.",
                "Make a list or a tree with all the outcomes.",
                "Check that all the cases you count are equally likely."],
        "esp": ["Cuenta todos los casos posibles y cuántos te interesan.",
                "Haz una lista o un árbol con todos los resultados.",
                "Comprueba que todos los casos que cuentas tienen la misma probabilidad."],
        "fra": ["Compte tous les cas possibles et combien t'intéressent.",
                "Fais une liste ou un arbre avec tous les résultats.",
                "Vérifie que tous les cas que tu comptes ont la même probabilité."],
        "arb": ["عُدّ كل الحالات الممكنة وكم منها يهمك.",
                "اكتب قائمة أو ارسم شجرة بكل النتائج.",
                "تأكد أن كل الحالات التي تعدّها لها الاحتمال نفسه."],
        "zho": ["数出所有可能的情况，以及其中有几种是你要的。",
                "用列表或树状图写出所有结果。",
                "检查一下你数的每种情况是不是可能性相同。"],
    },
    "patrons": {
        "eng": ["Give a name to what you don't know and write what the problem says about it.",
                "Work out the first few cases and look for the rule.",
                "Try working backwards, from the end to the start."],
        "esp": ["Ponle un nombre a lo que no sabes y escribe lo que dice el enunciado sobre eso.",
                "Calcula los primeros casos y busca la regla.",
                "Prueba a trabajar hacia atrás, desde el final hasta el principio."],
        "fra": ["Donne un nom à ce que tu ne connais pas et écris ce que l'énoncé en dit.",
                "Calcule les premiers cas et cherche la règle.",
                "Essaie de raisonner à l'envers, de la fin vers le début."],
        "arb": ["سمِّ المجهول برمز واكتب ما تقوله المسألة عنه.",
                "احسب الحالات الأولى وابحث عن القاعدة.",
                "جرّب أن تعمل بالعكس، من النهاية إلى البداية."],
        "zho": ["给不知道的量起个名字，写下题目关于它说了什么。",
                "先算出前几种情况，找找规律。",
                "试着倒过来想，从最后推回开头。"],
    },
    "aritmetica": {
        "eng": ["Write down what you know and what you are asked before calculating.",
                "Do the calculation in parts and check each step.",
                "Before calculating, estimate roughly how big the result should be."],
        "esp": ["Escribe qué sabes y qué te piden antes de calcular.",
                "Haz el cálculo por partes y comprueba cada paso.",
                "Antes de calcular, estima más o menos cuánto tiene que salir."],
        "fra": ["Écris ce que tu sais et ce qu'on te demande avant de calculer.",
                "Fais le calcul par étapes et vérifie chaque étape.",
                "Avant de calculer, estime à peu près combien tu dois trouver."],
        "arb": ["اكتب ما تعرفه وما هو مطلوب منك قبل أن تحسب.",
                "قسّم الحساب إلى خطوات وتحقق من كل خطوة.",
                "قبل الحساب، قدّر تقريباً كم يجب أن تكون النتيجة."],
        "zho": ["计算之前，先写下你知道什么、题目问什么。",
                "分步计算，每一步都检查一下。",
                "计算之前，先估计一下结果大概是多少。"],
    },
}

DEFAULT = "aritmetica"
HINT_LANG = "cat"    # the classroom language: every topic has it, and it is the fallback
HINT_LANGS = ("cat", "eng", "esp", "fra", "arb", "zho")
NAMES = {key: name for key, name, _words, _hints in TOPICS}
# HINTS[key][lang]: the method hints of one topic in one language.
HINTS = {key: {HINT_LANG: hints, **TRANSLATIONS.get(key, {})}
         for key, _name, _words, hints in TOPICS}
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


def method_hint(key, n=0, lang=HINT_LANG):
    """The n-th method hint of a topic in a language, or in Catalan if it isn't there."""
    by_lang = HINTS.get(key, HINTS[DEFAULT])
    hints = by_lang.get(lang) or by_lang[HINT_LANG]
    return hints[n % len(hints)]
