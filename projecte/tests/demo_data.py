#!/usr/bin/env python3
"""Invented problems in the M3Kang format, to try the code without M3Kang.

    python3 tests/demo_data.py --out data/demo

They are written by the team from simple templates, in English, Catalan and
Spanish. They are NOT Kangaroo problems and not part of M3Kang, so they can be
published, and no result measured on them says anything about M3Kang.
"""
import argparse
import json
import math
import os
import random

LANGS = ("eng", "cat", "esp")
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
               f"¿Cuántas manzanas quedan?"}


def square(r, level):
    side = r.randint(2, 6 + 2 * level)
    return side * side, " cm²", {
        "eng": f"A square has a perimeter of {4 * side} cm. What is its area?",
        "cat": f"Un quadrat té un perímetre de {4 * side} cm. Quina és la seva àrea?",
        "esp": f"Un cuadrado tiene un perímetro de {4 * side} cm. ¿Cuál es su área?"}


def digits(r, level):
    total = r.randint(3, 9)
    return total, "", {
        "eng": f"How many two-digit numbers have digits that add up to {total}?",
        "cat": f"Quants nombres de dues xifres tenen xifres que sumen {total}?",
        "esp": f"¿Cuántos números de dos cifras tienen cifras que suman {total}?"}


def film(r, level):
    hour, minutes = r.randint(3, 8), r.randint(70, 110)
    return minutes - 60, "", {
        "eng": f"A film starts at {hour} o'clock and lasts {minutes} minutes. "
               f"How many minutes after {hour + 1} o'clock does it end?",
        "cat": f"Una pel·lícula comença a les {hour} i dura {minutes} minuts. "
               f"Quants minuts després de les {hour + 1} acaba?",
        "esp": f"Una película empieza a las {hour} y dura {minutes} minutos. "
               f"¿Cuántos minutos después de las {hour + 1} termina?"}


def line(r, level):
    friends = r.randint(3, 4 + min(level, 2))
    return math.factorial(friends), "", {
        "eng": f"In how many different ways can {friends} friends stand in a line?",
        "cat": f"De quantes maneres diferents es poden posar en fila {friends} amics?",
        "esp": f"¿De cuántas maneras diferentes pueden ponerse en fila {friends} amigos?"}


def half(r, level):
    third = r.randint(2, 6 + 2 * level)
    return 2 * third, "", {
        "eng": f"Half of a number is {3 * third}. What is a third of the number?",
        "cat": f"La meitat d'un nombre és {3 * third}. Quin és un terç del nombre?",
        "esp": f"La mitad de un número es {3 * third}. ¿Cuál es un tercio del número?"}


def sequence(r, level):
    first, step, n = r.randint(1, 9), r.randint(2, 4 + level), r.randint(5, 9)
    return first + step * (n - 1), "", {
        "eng": f"A sequence starts at {first} and each term adds {step}. What is term number {n}?",
        "cat": f"Una seqüència comença en {first} i cada terme suma {step}. Quin és el terme número {n}?",
        "esp": f"Una secuencia empieza en {first} y cada término suma {step}. ¿Cuál es el término número {n}?"}


TEMPLATES = [bags, square, digits, film, line, half, sequence]


def make(count=120, seed=7, levels=4, val_every=6):
    """Return (train, val): lists of problems, one row per language, the same id across languages."""
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
        for lang in LANGS:
            target.append({"id": f"lvl-{level}_{year}_{number[(level, year)]}", "language": lang,
                           "level": level, "year": year, "text_only": True,
                           "text": f"{number[(level, year)]}. {texts[lang]}",
                           "options": options, "label": label})
        made += 1
    return train, val


def write(folder, count=120, seed=7):
    os.makedirs(folder, exist_ok=True)
    train, val = make(count, seed)
    for name, rows in (("train.jsonl", train), ("val.jsonl", val)):
        with open(os.path.join(folder, name), "w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return train, val


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", default="data/demo")
    p.add_argument("--count", type=int, default=120)
    args = p.parse_args()
    train, val = write(args.out, args.count)
    print(f"Wrote {len(train)} training rows and {len(val)} validation rows to {args.out}/ "
          f"({len(LANGS)} languages). Invented problems: not M3Kang.")


if __name__ == "__main__":
    main()
