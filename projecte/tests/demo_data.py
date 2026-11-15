#!/usr/bin/env python3
"""Invented problems in the M3Kang format, to try the code without M3Kang.

    python3 tests/demo_data.py --out data/demo
    python3 tests/demo_data.py --out data/demo --bridge   # also French, Arabic and Chinese

They are written by the team from simple templates, in English, Catalan and
Spanish. They are NOT Kangaroo problems and not part of M3Kang, so they can be
published, and no result measured on them says anything about M3Kang.

--bridge also writes bridge.jsonl: the same problems in French, Arabic and Chinese, in
the format prep/import_translations.py reads, to try the language bridge (and to take
screenshots) without any M3Kang text. Those three were written without a native speaker.
"""
import argparse
import json
import math
import os
import random

LANGS = ("eng", "cat", "esp")
BRIDGE = ("fra", "arb", "zho")     # only for the language bridge's demo: see --bridge
NAMES = ["Anna", "Pau", "Laia", "Marc", "Aina", "Jan", "Noa", "Biel"]


def bags(r, level):
    a, b, c = r.randint(2, 4 + level), r.randint(3, 6 + level), r.randint(1, 5)
    name = r.choice(NAMES)
    return a * b - c, "", {
        "eng": f"{name} has {a} bags with {b} apples in each bag and eats {c} apples. "
               f"How many apples are left?",
        "cat": f"{name} té {a} bosses amb {b} pomes a cada bossa i es menja {c} pomes. "
               f"Quantes pomes queden?",
        "esp": f"{name} tiene {a} bolsas con {b} manzanas en cada bolsa y se come {c} manzanas. "
               f"¿Cuántas manzanas quedan?",
        "fra": f"{name} a {a} sacs avec {b} pommes dans chaque sac et mange {c} pommes. "
               f"Combien de pommes reste-t-il ?",
        "arb": f"عند {name} {a} أكياس، وفي كل كيس {b} تفاحات، ثم أكل {c} تفاحات. كم تفاحة بقيت؟",
        "zho": f"{name}有{a}个袋子，每个袋子里有{b}个苹果，吃掉了{c}个苹果。还剩多少个苹果？"}


def square(r, level):
    side = r.randint(2, 6 + 2 * level)
    return side * side, " cm²", {
        "eng": f"A square has a perimeter of {4 * side} cm. What is its area?",
        "cat": f"Un quadrat té un perímetre de {4 * side} cm. Quina és la seva àrea?",
        "esp": f"Un cuadrado tiene un perímetro de {4 * side} cm. ¿Cuál es su área?",
        "fra": f"Un carré a un périmètre de {4 * side} cm. Quelle est son aire ?",
        "arb": f"مربع محيطه {4 * side} cm. ما مساحته؟",
        "zho": f"一个正方形的周长是 {4 * side} cm。它的面积是多少？"}


def digits(r, level):
    total = r.randint(3, 9)
    return total, "", {
        "eng": f"How many two-digit numbers have digits that add up to {total}?",
        "cat": f"Quants nombres de dues xifres tenen xifres que sumen {total}?",
        "esp": f"¿Cuántos números de dos cifras tienen cifras que suman {total}?",
        "fra": f"Combien de nombres à deux chiffres ont des chiffres dont la somme est {total} ?",
        "arb": f"كم عدداً مكوّناً من رقمين مجموع رقميه {total}؟",
        "zho": f"有多少个两位数，它的两个数字之和是 {total}？"}


def film(r, level):
    hour, minutes = r.randint(3, 8), r.randint(70, 110)
    return minutes - 60, "", {
        "eng": f"A film starts at {hour} o'clock and lasts {minutes} minutes. "
               f"How many minutes after {hour + 1} o'clock does it end?",
        "cat": f"Una pel·lícula comença a les {hour} i dura {minutes} minuts. "
               f"Quants minuts després de les {hour + 1} acaba?",
        "esp": f"Una película empieza a las {hour} y dura {minutes} minutos. "
               f"¿Cuántos minutos después de las {hour + 1} termina?",
        "fra": f"Un film commence à {hour} heures et dure {minutes} minutes. "
               f"Combien de minutes après {hour + 1} heures se termine-t-il ?",
        "arb": f"يبدأ فيلم في الساعة {hour} ويستمر {minutes} دقيقة. "
               f"بعد كم دقيقة من الساعة {hour + 1} ينتهي؟",
        "zho": f"一部电影 {hour} 点开始，放映 {minutes} 分钟。它在 {hour + 1} 点之后多少分钟结束？"}


def line(r, level):
    friends = r.randint(3, 4 + min(level, 2))
    return math.factorial(friends), "", {
        "eng": f"In how many different ways can {friends} friends stand in a line?",
        "cat": f"De quantes maneres diferents es poden posar en fila {friends} amics?",
        "esp": f"¿De cuántas maneras diferentes pueden ponerse en fila {friends} amigos?",
        "fra": f"De combien de façons différentes {friends} amis peuvent-ils se mettre en file ?",
        "arb": f"بكم طريقة مختلفة يمكن أن يقف {friends} أصدقاء في صف واحد؟",
        "zho": f"{friends} 个朋友排成一排，有多少种不同的排法？"}


def half(r, level):
    third = r.randint(2, 6 + 2 * level)
    return 2 * third, "", {
        "eng": f"Half of a number is {3 * third}. What is a third of the number?",
        "cat": f"La meitat d'un nombre és {3 * third}. Quin és un terç del nombre?",
        "esp": f"La mitad de un número es {3 * third}. ¿Cuál es un tercio del número?",
        "fra": f"La moitié d'un nombre est {3 * third}. Quel est le tiers de ce nombre ?",
        "arb": f"نصف عدد هو {3 * third}. ما ثلث هذا العدد؟",
        "zho": f"一个数的一半是 {3 * third}。这个数的三分之一是多少？"}


def sequence(r, level):
    first, step, n = r.randint(1, 9), r.randint(2, 4 + level), r.randint(5, 9)
    return first + step * (n - 1), "", {
        "eng": f"A sequence starts at {first} and each term adds {step}. What is term number {n}?",
        "cat": f"Una seqüència comença en {first} i cada terme suma {step}. Quin és el terme número {n}?",
        "esp": f"Una secuencia empieza en {first} y cada término suma {step}. ¿Cuál es el término número {n}?",
        "fra": f"Une suite commence à {first} et chaque terme ajoute {step}. Quel est le terme numéro {n} ?",
        "arb": f"متتالية تبدأ بالعدد {first} ويزيد كل حد بمقدار {step}. ما الحد رقم {n}؟",
        "zho": f"一个数列从 {first} 开始，每一项加 {step}。第 {n} 项是多少？"}


TEMPLATES = [bags, square, digits, film, line, half, sequence]


def make(count=120, seed=7, levels=4, val_every=6, langs=LANGS):
    """Return (train, val): lists of problems, one row per language, the same id across languages.

    The problems are the same whatever languages are asked for.
    """
    r = random.Random(seed)
    train, val, seen = [], [], set()
    number = {}
    made = 0
    while made < count:
        level = made % levels
        template = TEMPLATES[r.randrange(len(TEMPLATES))]
        answer, unit, texts = template(r, level)
        if texts["eng"] in seen:
            continue
        seen.add(texts["eng"])
        year = 2030 + r.randrange(3)
        number[(level, year)] = number.get((level, year), 0) + 1
        offsets = r.sample([-6, -4, -3, -2, -1, 1, 2, 3, 4, 6, 10], 10)
        values = [answer]
        for offset in offsets:
            if answer + offset > 0 and answer + offset not in values and len(values) < 5:
                values.append(answer + offset)
        while len(values) < 5:
            values.append(max(values) + 5)
        r.shuffle(values)
        options = {letter: f"{value}{unit}" for letter, value in zip("ABCDE", values)}
        label = "ABCDE"[values.index(answer)]
        target = val if made % val_every == val_every - 1 else train
        for lang in langs:
            target.append({"id": f"lvl-{level}_{year}_{number[(level, year)]}", "language": lang,
                           "level": level, "year": year, "text_only": True,
                           "text": f"{number[(level, year)]}. {texts[lang]}",
                           "options": options, "label": label})
        made += 1
    return train, val


def write(folder, count=120, seed=7, bridge=False):
    os.makedirs(folder, exist_ok=True)
    train, val = make(count, seed)
    files = [("train.jsonl", train), ("val.jsonl", val)]
    if bridge:      # as a translator would leave them: one row per problem and language
        extra_train, extra_val = make(count, seed, langs=BRIDGE)
        files.append(("bridge.jsonl", [dict(row, translation_source="demo")
                                       for row in extra_train + extra_val]))
    for name, rows in files:
        with open(os.path.join(folder, name), "w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return train, val


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", default="data/demo")
    p.add_argument("--count", type=int, default=120)
    p.add_argument("--bridge", action="store_true",
                   help="also write bridge.jsonl (French, Arabic, Chinese) for import_translations.py")
    args = p.parse_args()
    train, val = write(args.out, args.count, bridge=args.bridge)
    print(f"Wrote {len(train)} training rows and {len(val)} validation rows to {args.out}/ "
          f"({len(LANGS)} languages). Invented problems: not M3Kang.")
    if args.bridge:
        print(f"Wrote {args.out}/bridge.jsonl ({', '.join(BRIDGE)}). Add it to the database with "
              f"prep/import_translations.py {args.out}/bridge.jsonl --db <the demo database>.")


if __name__ == "__main__":
    main()
