#!/usr/bin/env python3
"""Add machine translations of the problems to the tutor's database, for the language bridge.

    python3 prep/import_translations.py FILE.jsonl [FILE.jsonl ...] [--db data/tutor.db]
    python3 prep/import_translations.py FILE.jsonl --dry-run        # count, write nothing
    python3 prep/import_translations.py FILE.jsonl --allow deu      # a language outside the plan

Each line is one problem in one language: {"id", "language", "text", "options"}, and
optionally "language_original", "text_original", "translation_suspect" (translate_ocr.py)
or "translation_source" (who translated it). The language is an M3Kang code (esp, fra,
arb, zho) or its two-letter form (es, fr, ar, zh).

A translation can spoil a maths problem without anyone noticing, so every row is checked
against the official text of the same problem, and refused when:

  - the numbers of the statement aren't the same ones (as a multiset);
  - an option has other numbers, or the options aren't the same letters;
  - the text is empty, or much shorter or longer than the original.

Options without words (numbers, units) are copied from the original, not translated.
When a problem comes translated more than once, one is kept: not marked suspect if
possible, then from Catalan for esp and fra, from English for arb and zho, then the
first file given. An official M3Kang text is never replaced.

Running it again changes nothing. The report has counts only, never problem text. The
translations derive from M3Kang (research licence): never commit them or the database.
"""
import argparse
import json
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict

import common  # noqa: F401  (puts the repository on sys.path)
from copilot.config import CONFIG, ROOT
from copilot.store import Store, default_path

TWO_LETTERS = {"es": "esp", "fr": "fra", "ar": "arb", "zh": "zho", "de": "deu",
               "en": "eng", "ca": "cat"}
PLANNED = ("esp", "fra", "arb", "zho")            # the bridge languages that need translating
BEST_ORIGINAL = {"esp": "cat", "fra": "cat", "arb": "eng", "zho": "eng"}
# How long a translation may be next to its original. Chinese is far shorter.
LENGTH = {"zho": (0.05, 1.5)}
LENGTH_DEFAULT = (0.4, 2.5)
NUMBER = re.compile(r"\d+")
WORD = re.compile(r"[^\W\d_]{4,}")


def numbers(text):
    """The numbers of a text as a multiset, whatever digits it is written with."""
    plain = "".join(str(unicodedata.digit(ch)) if ch.isdigit() else ch for ch in text or "")
    return Counter(NUMBER.findall(plain))


def has_words(option):
    """An option worth translating: it has a real word, not only numbers, units or names in capitals."""
    return any(not word.isupper() for word in WORD.findall(str(option)))


def language(code, allowed):
    """The M3Kang code of a row's language, or None when it isn't one we import."""
    code = (code or "").strip().lower()
    code = TWO_LETTERS.get(code, code)
    return code if code in allowed else None


def source_of(row, default):
    if row.get("translation_source"):
        return str(row["translation_source"]).strip().lower()
    return "opus-mt" if "translation_suspect" in row else default


def check(row, lang, originals):
    """Return (reason, options): reason is None when the row can be imported.

    originals: the official versions of the problem, [{"lang", "text", "options"}], the
    one the translation was made from first. A row that doesn't say what it was made
    from passes when it agrees with any of them.
    """
    text = (row.get("text") or "").strip()
    if not text:
        return "empty", None
    options = row.get("options") or {}
    reason = "numbers"
    for original in originals:
        reference = row.get("text_original") if original is originals[0] else None
        reference = reference or original["text"]
        if numbers(text) != numbers(reference):
            continue
        low, high = LENGTH.get(lang, LENGTH_DEFAULT)
        if not low <= len(text) / max(1, len(reference)) <= high:
            reason = "length"
            continue
        official = original["options"] or {}
        if set(options) != set(official):
            reason = "option_count"
            continue
        if any(numbers(str(options[k])) != numbers(str(official[k])) for k in official):
            reason = "option_value"
            continue
        kept = {k: (str(options[k]) if has_words(official[k]) and str(options[k]).strip()
                    else str(official[k])) for k in official}
        return None, kept
    return reason, None


def import_translations(store, rows, allowed=PLANNED, default_source="machine", dry_run=False):
    """Check the rows and write the good ones. Returns the report (counts only)."""
    report = {"rows": len(rows), "imported": Counter(), "rejected": Counter(),
              "skipped": Counter(), "missing": {}}
    official = defaultdict(dict)          # id -> lang -> official version
    machine = set()                       # (id, lang) already there from a translator
    for row in store.rows("SELECT id, lang, text, options, source FROM texts"):
        if (row["source"] or "official") == "official":
            official[row["id"]][row["lang"]] = {"lang": row["lang"], "text": row["text"],
                                                "options": json.loads(row["options"] or "{}")}
        else:
            machine.add((row["id"], row["lang"]))
    known = {row["id"] for row in store.rows("SELECT id FROM problems")}

    candidates = defaultdict(list)
    for order, row in enumerate(rows):
        lang = language(row.get("language"), allowed)
        if not lang:
            report["skipped"]["language_not_allowed"] += 1
        elif row.get("id") not in known or not official[row["id"]]:
            report["skipped"]["unknown_problem"] += 1
        elif lang in official[row["id"]]:
            report["skipped"]["official_exists"] += 1
        else:
            made_from = language(row.get("language_original"), TWO_LETTERS.values())
            rank = (bool(row.get("translation_suspect")), made_from != BEST_ORIGINAL.get(lang), order)
            candidates[(row["id"], lang)].append((rank, made_from, row))

    writes = []
    for (problem_id, lang), found in candidates.items():
        chosen, reasons = None, []
        for _rank, made_from, row in sorted(found, key=lambda item: item[0]):
            versions = official[problem_id]
            originals = ([versions[made_from]] if made_from in versions else
                         [versions[k] for k in (CONFIG.get("TUTOR_LANG", "cat"),
                                                CONFIG.get("MODEL_LANG", "eng")) if k in versions]
                         or list(versions.values()))
            reason, options = check(row, lang, originals)
            if reason is None:
                chosen = (row, options)
                break
            reasons.append("suspect" if row.get("translation_suspect") else reason)
        if not chosen:
            report["rejected"][f"{lang}:{reasons[0]}"] += 1
            continue
        row, options = chosen
        source = source_of(row, default_source)
        report["imported"][f"{lang}:{source}"] += 1
        writes.append((problem_id, lang, row["text"].strip(),
                       json.dumps(options, ensure_ascii=False), source))
    if writes and not dry_run:
        store.many("INSERT OR REPLACE INTO texts (id, lang, text, options, source) "
                   "VALUES (?, ?, ?, ?, ?)", writes)

    # Problems the tutor can use that still have no text in each planned language
    eligible = {row["id"] for row in store.rows("SELECT id FROM problems WHERE eligible = 1")}
    written = {(w[0], w[1]) for w in writes} | machine
    for lang in sorted(set(allowed) | {lang for _id, lang in written}):
        have = sum(1 for problem_id in eligible
                   if lang in official[problem_id] or (problem_id, lang) in written)
        report["missing"][lang] = {"eligible": len(eligible), "with_text": have,
                                   "without_text": len(eligible) - have}
    for key in ("imported", "rejected", "skipped"):
        report[key] = dict(sorted(report[key].items()))
    report["dry_run"] = bool(dry_run)
    return report


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("files", nargs="+", help="JSONL files; the first one wins a tie")
    p.add_argument("--db", default=default_path())
    p.add_argument("--allow", nargs="*", default=[], metavar="LANG",
                   help="also import these languages (the plan has esp, fra, arb, zho)")
    p.add_argument("--source", default="machine",
                   help="who translated the rows that don't say it (default: machine)")
    p.add_argument("--dry-run", action="store_true", help="check and count, write nothing")
    p.add_argument("--report", default=os.path.join(ROOT, "results", "translations-import.json"),
                   help="where to write the counts ('' for nowhere)")
    args = p.parse_args(argv)

    allowed = set(PLANNED)
    for code in args.allow:
        code = TWO_LETTERS.get(code.lower(), code.lower())
        if len(code) != 3:
            raise SystemExit(f"--allow {code}: use the M3Kang code of three letters, like deu")
        allowed.add(code)
    rows = []
    for path in args.files:
        if not os.path.exists(path):
            raise SystemExit(f"{path} not found")
        with open(path, encoding="utf-8") as f:
            try:
                rows += [json.loads(line) for line in f if line.strip()]
            except json.JSONDecodeError as error:
                raise SystemExit(f"{path} isn't JSONL ({error})")
    refused = Counter(str(row.get("language")) for row in rows if not language(row.get("language"), allowed))
    store = Store(args.db)
    try:
        report = import_translations(store, rows, allowed, args.source, args.dry_run)
    finally:
        store.close()

    did = "Would import" if args.dry_run else "Imported"
    print(f"{did} {sum(report['imported'].values())} of {report['rows']} rows into {args.db}")
    for title, key in (("by language and translator", "imported"), ("refused by the checks", "rejected"),
                       ("skipped", "skipped")):
        if report[key]:
            print(f"  {title}: " + ", ".join(f"{k} {n}" for k, n in report[key].items()))
    if refused:
        print("  languages not imported (pass --allow to import one): "
              + ", ".join(f"{k} {n}" for k, n in sorted(refused.items())))
    print("  problems the tutor can use, with a text in each language:")
    for lang, count in report["missing"].items():
        print(f"    {lang}: {count['with_text']}/{count['eligible']} ({count['without_text']} without)")
    print("  Machine translation, not reviewed by a native speaker. Never commit it.")
    if args.report:
        os.makedirs(os.path.dirname(args.report), exist_ok=True)
        with open(args.report, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
