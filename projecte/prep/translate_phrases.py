#!/usr/bin/env python3
"""Translate the Kangaroo's phrases with OPUS-MT, on the laptop (never on the board).

    python prep/translate_phrases.py                 # writes copilot/phrases_mt.json
    python prep/translate_phrases.py --device cuda

The Catalan text of copilot/phrases.py is the reference, written by the team. This
script translates it with the Helsinki-NLP OPUS-MT models: Catalan to Spanish, French
and English directly, and English to Chinese and Arabic (there is no direct model from
Catalan). It needs torch and transformers, so it runs on the laptop only; the board
reads the JSON file it writes, with the standard library.

Each {marker} of a template is swapped for a stand-in the models copy as it is (a
number, a capital letter, an invented word) and put back afterwards. A translation
that lost a stand-in is not kept: it is listed under "failed", and the tutor says that
phrase in Catalan. Nobody has reviewed the result: it is machine translation.
"""
import argparse
import json
import os
import re
import sys

import common  # noqa: F401  (puts the repository on sys.path)
from copilot import phrases, topics
from copilot.config import ROOT

# marker -> stand-ins to try, in order
STAND_INS = {
    "label": ["Z", "(Z)"], "answer": ["Z", "(Z)"], "letter": ["Z", "(Z)"],
    "sure": ["73"], "level": ["8642"], "value": ["7391"],
    "topic": ["Zorblax", "XQZ"], "llengua": ["Zorblax", "XQZ"], "text": ["Zorblax", "XQZ"],
}
ROUTES = {"esp": [("ca", "es")], "fra": [("ca", "fr")], "eng": [("ca", "en")],
          "zho": [("ca", "en"), ("en", "zh")], "arb": [("ca", "en"), ("en", "ar")]}
PREFIX = {"zh": ">>cmn_Hans<< ", "ar": ">>ara<< "}
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿]")
SENTENCE = re.compile(r"(?<=[.!?…:])\s+")
MARKER = re.compile(r"\{(\w+)\}")


class Model:
    def __init__(self, source, target, device):
        import torch
        from transformers import MarianMTModel, MarianTokenizer
        name = f"Helsinki-NLP/opus-mt-{source}-{target}"
        self.torch, self.device, self.prefix = torch, device, PREFIX.get(target, "")
        self.tokenizer = MarianTokenizer.from_pretrained(name)
        self.model = MarianMTModel.from_pretrained(name).to(device).eval()

    def run(self, texts):
        out = []
        with self.torch.inference_mode():
            for start in range(0, len(texts), 16):
                batch = [self.prefix + text for text in texts[start:start + 16]]
                encoded = self.tokenizer(batch, return_tensors="pt", padding=True,
                                         truncation=True, max_length=256).to(self.device)
                generated = self.model.generate(**encoded, num_beams=5, max_new_tokens=256)
                out += self.tokenizer.batch_decode(generated, skip_special_tokens=True)
        return out


def protect(template, attempt):
    """The template with stand-ins for its markers, and how to put them back."""
    back = {}

    def swap(match):
        choices = STAND_INS[match.group(1)]
        stand_in = choices[min(attempt, len(choices) - 1)]
        back[stand_in] = match.group(0)
        return stand_in
    return MARKER.sub(swap, template), back


def restore(text, back):
    """Put the markers back, or None when a stand-in was lost or repeated."""
    for stand_in, marker in back.items():
        if text.count(stand_in) != 1:
            return None
        text = text.replace(stand_in, marker)
    return text


def translate(models, lang, templates, device):
    """{key: translation} for one language; a key is missing when its markers were lost."""
    done = {}
    for attempt in range(2):
        todo = [key for key in templates if key not in done]
        if not todo:
            break
        pieces, owner, backs, tails = [], [], {}, {}
        for key in todo:
            text = templates[key]
            tails[key] = "".join(EMOJI.findall(text))
            text, backs[key] = protect(EMOJI.sub("", text).strip(), attempt)
            for sentence in SENTENCE.split(text):
                pieces.append(sentence)
                owner.append(key)
        for source, target in ROUTES[lang]:
            if (source, target) not in models:
                models[(source, target)] = Model(source, target, device)
            pieces = models[(source, target)].run(pieces)
        joined = {}
        for key, piece in zip(owner, pieces):
            joined.setdefault(key, []).append(piece.strip())
        for key in todo:
            text = restore(("" if lang == "zho" else " ").join(joined[key]), backs[key])
            if text:
                done[key] = (text + " " + tails[key]).strip()
    return done


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", default=os.path.join(ROOT, "copilot", "phrases_mt.json"))
    p.add_argument("--device", default="cpu", help="cpu (default: the phrases are few) or cuda")
    args = p.parse_args(argv)

    reference = {key: by_lang["cat"] for key, by_lang in phrases.PHRASES.items()}
    names = dict(topics.NAMES)
    result = {"source": "opus-mt", "routes": {lang: ["-".join(step) for step in route]
                                             for lang, route in ROUTES.items()},
              "phrases": {key: {} for key in reference}, "topics": {key: {} for key in names},
              "failed": []}
    models = {}
    for lang in ROUTES:
        translated = translate(models, lang, reference, args.device)
        for key in reference:
            if key in translated:
                result["phrases"][key][lang] = translated[key]
            else:
                result["failed"].append([key, lang])
        for key, text in translate(models, lang, names, args.device).items():
            result["topics"][key][lang] = text
        print(f"{lang}: {len(translated)}/{len(reference)} phrases", flush=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(result, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")
    print(f"Wrote {args.out}; {len(result['failed'])} translations lost a marker and stay in Catalan")
    return 0


if __name__ == "__main__":
    sys.exit(main())
