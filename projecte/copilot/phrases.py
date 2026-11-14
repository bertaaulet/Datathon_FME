"""Everything the Kangaroo and the tutor say, for the six languages of the language bridge.

    phrase("correcte", "fra")
    phrase("solucio", "esp", label="C", value="10")

The Kangaroo never writes its own sentences: they are these templates. The Catalan text
is the reference, written by the team, and it lives here. The other five languages
(eng, esp, fra, arb, zho) are machine translations of it, made on the laptop by
prep/translate_phrases.py with OPUS-MT and kept in phrases_mt.json, next to this file.
Nobody has reviewed them: no native speaker, and no back-translation. They are the
team's own text, with nothing from M3Kang, so the file can be published.

On the board nothing is translated: this module only reads the JSON (standard library).
A translation that is missing, or that lost one of the {markers} of its Catalan
template, is not used: the student reads that phrase in Catalan only.

AFTER_SOLVING lists the phrases that name an answer letter. The tutor only says them once
the student has solved the problem or asked for the solution (tests check both).
"""
import json
import os
import string

from . import leak, topics

LANGS = ("cat", "eng", "esp", "fra", "arb", "zho")
REFERENCE = "cat"
MT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "phrases_mt.json")

# Always on screen while a student works on a problem from outside the bank (CLAUDE.md)
EXTERNAL_WARNING = ("No podem assegurar les respostes per a problemes externs. "
                    "Confirma la solució en fonts oficials o amb el teu professor.")

# The Catalan templates: {key: text}
CATALAN = {
    # --- the Kangaroo --------------------------------------------------------------------
    "hola":
        ("Hola! Soc el Cangur. Resolem problemes junts? Aviso: jo m'equivoco força, "
        "potser m'hauràs d'ajudar!"),
    "mira_problema": "Mira aquest problema! Jo també l'estic pensant… 🤔",
    "tambe_be": "Jo també he dit la {label}! Aquesta ens ha sortit bé a tots dos. 🎉",
    "jo_he_dit":
        ("Doncs jo he dit la {answer}… (n'estic un {sure} % segur). M'ajudes? Dona'm una"
        " pista, però no em diguis la resposta!"),
    "ara_ho_veig": "Aaah, ara ho veig! Llavors és la {label}.",
    "gracies": "Gràcies!",
    "gracies_companys": "Gràcies! La teva pista ajudarà altres companys.",
    "espes": "Avui estic espès… Deixem-ho aquí. Gràcies per provar-ho!",
    "repensant":
        ("Mmm, m'ho estic repensant, però encara no ho veig clar. M'ho expliques d'una "
        "altra manera?"),
    "no_entes": "No t'he entès… M'ho pots explicar d'una altra manera?",
    "ja_al_banc": "Aquest problema ja el tinc al meu banc! Fem-lo junts.",
    "extern_obert":
        ("Aquest problema no és al meu banc. Sembla de «{topic}». Calculo la resposta "
        "mentre el llegeixes, i després el fem com els altres."),
    "extern_obert_nivell":
        ("Aquest problema no és al meu banc. Sembla de «{topic}» (nivell aproximat: "
        "{level}). Calculo la resposta mentre el llegeixes, i després el fem com els "
        "altres."),
    "extern_sense_opcions":
        ("No he pogut llegir les cinc opcions, A) … E), o sigui que no et puc corregir "
        "la resposta. Sembla un problema de «{topic}»."),
    # --- the language bridge -------------------------------------------------------------
    "etapa2":
        ("Ho fas molt bé! A partir d'ara veuràs els problemes en català, amb un botó per"
        " veure'ls en la teva llengua."),
    "etapa3": "Ja no et cal el botó: ara els problemes són en català.",
    "etapa1_torna": "Tornem a posar les dues llengües de costat una estona.",
    "no_traduit": "Aquest problema encara no està traduït a la teva llengua.",
    "no_queden_origen": "Ja no queden problemes en {llengua}. Continuem en català.",
    # --- the bank ------------------------------------------------------------------------
    "no_queden_llengua":
        "No queden problemes en {llengua}. Cal preparar el banc en aquesta llengua.",
    "banc_acabat": "No queden problemes per fer. Has acabat el banc!",
    # --- answering -----------------------------------------------------------------------
    "jo_dic": "Jo dic la {letter}.",
    "no_es_aquesta": "No és aquesta. Pots demanar una pista i tornar-ho a provar.",
    "no_coincideix":
        ("No coincideix amb la resposta que hem calculat. Pots demanar una pista i "
        "tornar-ho a provar."),
    "correcte": "Correcte!",
    "cangur_no_pensa": "El Cangur no ha pogut pensar-hi (el model no respon).",
    "cangur_no_respon": "El Cangur no respon ara mateix. Torna-ho a provar.",
    # --- the help ladder -----------------------------------------------------------------
    "semblant_facil": "Mira aquest problema semblant i més fàcil:",
    "exemple_resposta": "Resposta: {label}) {value}",
    "es_un_problema_de": "És un problema de «{topic}».",
    "pista_company": "Una pista d'un company: «{text}»",
    "pista": "Una pista: «{text}»",
    "pista_semblant": "Una pista d'un problema semblant: «{text}»",
    "solucio": "La resposta és la {label}) {value}.",
    "solucio_extern": "Segons els nostres càlculs, la resposta és la {label}) {value}.",
    # --- problems from outside the bank --------------------------------------------------
    "avis_extern": EXTERNAL_WARNING,
    "extern_no_calcul":
        ("No he pogut calcular la resposta d'aquest problema (el model no respon). "
        "Prova'n un altre o tornem als problemes del banc."),
    "semblants_practicar": "Aquí tens problemes semblants del banc per practicar.",
    # --- the leak filter's answers to a student's hint: the Catalan is leak.MESSAGES ------
    **{"fuita_" + reason: text for reason, text in leak.MESSAGES.items()},
}

# Phrases that name an answer letter: never before the student has solved the problem or
# asked for the solution. "jo_dic" is the student's own answer, in the student's voice.
AFTER_SOLVING = frozenset({"tambe_be", "jo_he_dit", "ara_ho_veig", "solucio", "solucio_extern"})
STUDENT_VOICE = frozenset({"jo_dic"})
OTHER_PROBLEM = frozenset({"exemple_resposta"})     # the answer of a similar problem, shown as an example


def fields(template):
    """The {markers} of a template."""
    return {name for _text, name, _spec, _conversion in string.Formatter().parse(template) if name}


def load(path=MT_PATH):
    """Read the machine translations: ({key: {lang: text}}, {topic: {lang: name}}).

    Only what can be used: a known key, a bridge language, some text, and the same
    {markers} as the Catalan template. No file, or a broken one, gives nothing.
    """
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}, {}
    if not isinstance(data, dict):
        return {}, {}

    def usable(table, reference):
        out = {}
        for key, by_lang in (table or {}).items():
            if key not in reference or not isinstance(by_lang, dict):
                continue
            for lang, text in by_lang.items():
                if lang in LANGS and lang != REFERENCE and isinstance(text, str) and text.strip() \
                        and fields(text) == fields(reference[key]):
                    out.setdefault(key, {})[lang] = text.strip()
        return out
    return usable(data.get("phrases"), CATALAN), usable(data.get("topics"), topics.NAMES)


_translated, TOPIC_NAMES = load()
# PHRASES[key][lang]: Catalan always, the other languages where a translation exists
PHRASES = {key: {REFERENCE: text, **_translated.get(key, {})} for key, text in CATALAN.items()}


def phrase(key, lang=REFERENCE, **data):
    """The phrase in one language. Falls back to Catalan when the language, or a value
    the translation needs, is missing: a student never sees a broken template."""
    by_lang = PHRASES[key]
    for template in (by_lang.get(lang), by_lang[REFERENCE]):
        if template:
            try:
                return template.format(**data)
            except (KeyError, IndexError):
                continue
    return by_lang[REFERENCE]


def topic_name(key, lang=REFERENCE):
    """A topic's name in one language, or in Catalan."""
    return TOPIC_NAMES.get(key, {}).get(lang) or topics.name(key)
