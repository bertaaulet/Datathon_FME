#!/usr/bin/env python3
"""Second OCR pass over M3Kang options, on your laptop.

The first pass (prepare_m3kang.py) reads the options A to E from the whole
image. It misses some and misreads others. Every problem is in the data in
two languages, and the options are mostly numbers that are not translated,
so the two readings of one problem should match. This pass uses that:

Targets:
  * text-only rows with no options,
  * rows with no options whose other language has them,
  * both rows of a problem whose two languages disagree,
  * "recheck": problems already read and matching. The first pass sometimes
    glued stray text from the problem onto an option ("1 17" for "17") in
    both languages alike, so matching is not proof. They are only re-read
    with the bottom strip, and only replaced when the new readings of both
    languages match each other.

For each target: OCR the bottom strip; if that does not give five options,
the bottom strip enlarged x2; then the whole image enlarged x2. (Enlarging
the strip first was worse: it turned "90" into "06".) Numbers stacked one above the other
inside an option are joined as a fraction ("1" over "2" -> "1/2").

Nothing in data/train.jsonl or data/val.jsonl changes. The result goes to
data/_pass2/ (train.jsonl, val.jsonl, report.json, review.csv) for review.
After the review, --apply copies it over, keeping a backup.

Usage (from projecte/):
    python3 laptop/ocr_pass2.py --parquet <high_quality-00000-of-00004.parquet>
    python3 laptop/ocr_pass2.py --parquet ... --review-images   # PNGs for the review sample
    python3 laptop/ocr_pass2.py --apply
"""
import argparse
import csv
import json
import os
import random
import re
import shutil
import sys
import time
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from prepare_m3kang import LETTERS, MARKER, parse_options  # noqa: E402

NUMBER = re.compile(r"^[-−+]?\d+([.,]\d+)?$")
SPLITS = ("train", "val")


# --- Pure helpers (tested in tests/test_all.py) ------------------------------

def norm_value(value):
    """Compare readings, not typography: decimal comma, spaces, case, minus sign."""
    s = re.sub(r"\s+", "", str(value)).lower().replace(",", ".").replace("−", "-")
    return s.replace("×", "x").replace("·", "x")


def is_full(options):
    return bool(options) and all(str(options.get(k, "")).strip() for k in LETTERS)


def same_options(a, b):
    return is_full(a) and is_full(b) and all(norm_value(a[k]) == norm_value(b[k]) for k in LETTERS)


def has_duplicates(options):
    values = [norm_value(v) for v in (options or {}).values() if str(v).strip()]
    return len(values) != len(set(values))


def _geometry(box):
    xs = [p[0] for p in box]
    ys = [p[1] for p in box]
    return min(xs), max(xs), min(ys), max(ys)


def merge_fractions(boxes):
    """Join a number box directly above another into one "top/bottom" box.

    A fraction such as 1 over 2 comes out of OCR as two boxes, and the first
    pass glued them into "12". Two number boxes are a fraction when they overlap
    horizontally, the gap between them is small, and no option marker (A..E)
    sits on the same line as either of them: the marker of a fraction is
    centred between numerator and denominator, while in options laid out in
    two rows each number has its own marker beside it.
    """
    items = []
    for box, text, score in boxes:
        x0, x1, y0, y1 = _geometry(box)
        items.append({"box": box, "text": text.strip(), "score": score,
                      "x0": x0, "x1": x1, "y0": y0, "y1": y1,
                      "yc": (y0 + y1) / 2, "h": max(y1 - y0, 1e-6)})
    markers = [it for it in items if MARKER.match(it["text"]) and len(it["text"]) <= 3]

    def has_marker_on_line(it):
        return any(abs(m["yc"] - it["yc"]) < 0.35 * max(m["h"], it["h"]) and m["x1"] <= it["x0"] + 1
                   for m in markers)

    used, out = set(), []
    numbers = [i for i, it in enumerate(items) if NUMBER.match(it["text"])]
    for i in numbers:
        if i in used:
            continue
        top = items[i]
        best = None
        for j in numbers:
            if j == i or j in used:
                continue
            bot = items[j]
            gap = bot["y0"] - top["y1"]
            h = max(top["h"], bot["h"])
            overlap = min(top["x1"], bot["x1"]) - max(top["x0"], bot["x0"])
            width = min(top["x1"] - top["x0"], bot["x1"] - bot["x0"])
            if (-0.2 * h <= gap <= 0.6 * h and overlap >= 0.5 * width
                    and 0.6 <= top["h"] / bot["h"] <= 1.6
                    and not has_marker_on_line(top) and not has_marker_on_line(bot)):
                if best is None or gap < best[1]:
                    best = (j, gap)
        if best:
            bot = items[best[0]]
            used.update({i, best[0]})
            x0, x1 = min(top["x0"], bot["x0"]), max(top["x1"], bot["x1"])
            y0, y1 = top["y0"], bot["y1"]
            out.append(([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], f"{top['text']}/{bot['text']}",
                        min(top["score"], bot["score"])))
    for i, it in enumerate(items):
        if i not in used:
            out.append((it["box"], it["text"], it["score"]))
    return out


def crop_bottom(image, fraction=0.4):
    """Bottom `fraction` of an image array (the options are usually the last line)."""
    h = image.shape[0]
    return image[int(h * (1 - fraction)):]


def classify_targets(rows):
    """Which rows the pass looks at, and why. rows: {(id, lang): row}."""
    by_id = defaultdict(dict)
    for (pid, lang), r in rows.items():
        by_id[pid][lang] = r
    targets = {}
    for pid, langs in by_id.items():
        full = {lang: is_full(r["options"]) for lang, r in langs.items()}
        if len(langs) > 1 and all(full.values()):
            values = list(langs.values())
            agree = all(same_options(values[0]["options"], v["options"]) for v in values[1:])
            for lang in langs:
                targets[(pid, lang)] = "recheck" if agree else "disagree"
            continue
        for lang, r in langs.items():
            if full[lang]:
                continue
            if any(full[o] for o in langs if o != lang):
                targets[(pid, lang)] = "other_has"
            elif r["text_only"]:
                targets[(pid, lang)] = "text_only_empty"
    return targets


def decide(rows, targets, new):
    """Merge the pass-2 readings into the rows.

    new: {(id, lang): (options, method)} with method "ocr_crop", "ocr_full2x"
    or "none". Returns the updated rows, each with "options_source" and
    "options_check" (agree, disagree, single, none).
    """
    out = {k: dict(r) for k, r in rows.items()}
    for k, r in out.items():
        r["options_source"] = "ocr" if is_full(r["options"]) else "none"
    by_id = defaultdict(list)
    for (pid, lang) in out:
        by_id[pid].append(lang)

    # 1) Problems read in every language (disagree, recheck): take the new
    #    readings only if they agree with each other.
    for pid, langs in by_id.items():
        keys = [(pid, lang) for lang in langs]
        group = {targets.get(k) for k in keys}
        if not group & {"disagree", "recheck"}:
            continue
        cands = [new.get(k, ({}, "none")) for k in keys]
        if all(is_full(o) for o, _ in cands) and all(same_options(cands[0][0], o) for o, _ in cands[1:]):
            for k, (o, m) in zip(keys, cands):
                if not same_options(o, out[k]["options"]):
                    out[k]["options"], out[k]["options_source"] = o, m
            continue
        if "recheck" in group:
            continue
        # Otherwise: does one new reading match the other language's old one?
        for k, (o, m) in zip(keys, cands):
            others = [out[x]["options"] for x in keys if x != k]
            if is_full(o) and any(same_options(o, x) for x in others):
                out[k]["options"], out[k]["options_source"] = o, m

    # 2) Empty rows: new reading, else copy from the other language.
    for k, why in targets.items():
        if why in ("disagree", "recheck"):
            continue
        o, m = new.get(k, ({}, "none"))
        if is_full(o):
            out[k]["options"], out[k]["options_source"] = o, m
    for k, why in targets.items():
        if why in ("disagree", "recheck") or is_full(out[k]["options"]):
            continue
        pid, lang = k
        donors = [(l2, out[(pid, l2)]["options"]) for l2 in by_id[pid]
                  if l2 != lang and is_full(out[(pid, l2)]["options"])]
        if donors:
            l2, o = donors[0]
            out[k]["options"], out[k]["options_source"] = dict(o), f"copied_{l2}"

    # 3) Checks.
    for pid, langs in by_id.items():
        keys = [(pid, lang) for lang in langs]
        full = [k for k in keys if is_full(out[k]["options"])]
        for k in keys:
            r = out[k]
            if not is_full(r["options"]):
                r["options_check"] = "none"
            elif r["options_source"].startswith("copied_"):
                r["options_check"] = "single"
            elif len(full) < 2:
                r["options_check"] = "single"
            elif all(same_options(r["options"], out[x]["options"]) for x in full if x != k):
                r["options_check"] = "agree"
            else:
                r["options_check"] = "disagree"
            r["options_suspect"] = r["options_check"] == "disagree" or has_duplicates(r["options"])
    return out


# --- I/O -----------------------------------------------------------------------

def load_rows(data):
    rows, split_of = {}, {}
    for split in SPLITS:
        with open(os.path.join(data, f"{split}.jsonl"), encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                k = (r["id"], r["language"])
                rows[k], split_of[k] = r, split
    return rows, split_of


def read_images(parquet, keys, folder=None):
    """Image bytes by (id, lang), from the parquet or from a folder of <id>_<lang>.png."""
    if folder:
        out = {}
        for k in keys:
            path = os.path.join(folder, f"{k[0]}_{k[1]}.png")
            if os.path.exists(path):
                with open(path, "rb") as f:
                    out[k] = f.read()
        return out
    import pyarrow.parquet as pq
    meta = pq.read_table(parquet, columns=["id", "language"])
    wanted = set(keys)
    idx = [i for i, k in enumerate(zip(meta.column(0).to_pylist(), meta.column(1).to_pylist())) if k in wanted]
    sub = pq.read_table(parquet, columns=["id", "language", "image"]).take(idx)
    return {(sub.column(0)[i].as_py(), sub.column(1)[i].as_py()): sub.column(2)[i].as_py()["bytes"]
            for i in range(sub.num_rows)}


def run_ocr(args, keys, images, quick=()):
    """quick: keys re-read with the bottom strip only (the recheck group)."""
    import cv2
    import numpy as np
    from rapidocr_onnxruntime import RapidOCR
    threads = {"intra_op_num_threads": args.ocr_threads, "inter_op_num_threads": 1}
    ocr = RapidOCR(**threads) if args.ocr_threads else RapidOCR()

    cache_path = os.path.join(args.out, ".ocr_cache.jsonl")
    cache = {}
    if os.path.exists(cache_path):
        with open(cache_path, encoding="utf-8") as f:
            for line in f:
                row = json.loads(line)
                cache[row["key"]] = (row["options"], row["method"])
    cache_file = open(cache_path, "a", encoding="utf-8", buffering=1)

    def read(img):
        boxes, _ = ocr(img)
        return parse_options(merge_fractions(boxes or []))

    new, t0, done = {}, time.time(), 0
    for k in keys:
        ck = f"{k[0]}|{k[1]}"
        if ck in cache:
            new[k] = tuple(cache[ck])
            continue
        if k not in images:
            continue
        image = cv2.imdecode(np.frombuffer(images[k], np.uint8), cv2.IMREAD_COLOR)
        big = lambda a: cv2.resize(a, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)  # noqa: E731
        options, method = read(crop_bottom(image)), "ocr_crop"
        if not is_full(options) and k not in quick:
            options, method = read(big(crop_bottom(image))), "ocr_crop2x"
        if not is_full(options) and k not in quick:
            options, method = read(big(image)), "ocr_full2x"
        if not is_full(options):
            options, method = {}, "none"
        new[k] = (options, method)
        cache_file.write(json.dumps({"key": ck, "options": options, "method": method}, ensure_ascii=False) + "\n")
        done += 1
        if done % 100 == 0:
            print(f"  {done} images, {done / (time.time() - t0):.2f} images/s", flush=True)
    cache_file.close()
    return new


def stats(rows):
    full = [r for r in rows.values() if is_full(r["options"])]
    text_only = [r for r in rows.values() if r["text_only"]]
    by_id = defaultdict(list)
    for (pid, _), r in rows.items():
        by_id[pid].append(r)
    both = [l for l in by_id.values() if len(l) > 1 and all(is_full(r["options"]) for r in l)]
    agree = sum(1 for l in both if all(same_options(l[0]["options"], r["options"]) for r in l[1:]))
    return {"rows": len(rows), "with_options": len(full),
            "text_only": len(text_only), "text_only_with_options": sum(1 for r in text_only if is_full(r["options"])),
            "problems_both_languages_read": len(both), "problems_languages_agree": agree,
            "rows_with_duplicate_options": sum(1 for r in full if has_duplicates(r["options"]))}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--parquet", help="local high_quality-00000-of-00004.parquet (Hugging Face cache)")
    p.add_argument("--images", help="folder of <id>_<lang>.png to use instead of the parquet")
    p.add_argument("--extract-only", action="store_true", help="write the target images to --images and stop")
    p.add_argument("--data", default="data")
    p.add_argument("--out", default=os.path.join("data", "_pass2"))
    p.add_argument("--ocr-threads", type=int, default=0)
    p.add_argument("--limit", type=int, default=0, help="only the first N targets (to time it)")
    p.add_argument("--review", type=int, default=40, help="rows in review.csv")
    p.add_argument("--review-images", action="store_true", help="save PNGs of the review rows")
    p.add_argument("--apply", action="store_true", help="copy data/_pass2 over data/, with a backup")
    args = p.parse_args()

    if args.apply:
        backup = os.path.join(args.data, "_pass1_backup")
        os.makedirs(backup, exist_ok=True)
        for split in SPLITS:
            shutil.copy2(os.path.join(args.data, f"{split}.jsonl"), os.path.join(backup, f"{split}.jsonl"))
            shutil.copy2(os.path.join(args.out, f"{split}.jsonl"), os.path.join(args.data, f"{split}.jsonl"))
        print(f"Applied. The first-pass files are in {backup}/")
        return
    if not args.parquet and not args.images:
        sys.exit("--parquet or --images is required")

    os.makedirs(args.out, exist_ok=True)
    rows, split_of = load_rows(args.data)
    targets = classify_targets(rows)
    keys = sorted(targets)
    if args.limit:
        keys = keys[:args.limit]
        targets = {k: targets[k] for k in keys}
    print(f"Targets: {len(keys)} rows {dict(Counter(targets.values()))}", flush=True)

    if args.extract_only:
        os.makedirs(args.images, exist_ok=True)
        for k, data in read_images(args.parquet, keys).items():
            with open(os.path.join(args.images, f"{k[0]}_{k[1]}.png"), "wb") as f:
                f.write(data)
        print(f"Wrote the target images to {args.images}/")
        return
    images = read_images(args.parquet, keys, args.images if args.parquet is None else None)
    quick = {k for k in keys if targets[k] == "recheck"}
    new = run_ocr(args, keys, images, quick)

    out = decide(rows, targets, {k: new[k] for k in keys if k in new})
    for split in SPLITS:
        with open(os.path.join(args.out, f"{split}.jsonl"), "w", encoding="utf-8") as f:
            for k, r in out.items():
                if split_of[k] == split:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")

    changed = Counter()
    for k in keys:
        before, after = rows[k]["options"], out[k]["options"]
        if not is_full(before) and is_full(after):
            changed["filled_" + out[k]["options_source"]] += 1
        elif is_full(before) and not same_options(before, after):
            changed[f"replaced_{targets[k]}_" + out[k]["options_source"]] += 1
        else:
            changed["unchanged"] += 1
    report = {"before": stats(rows), "after": stats(out), "targets": dict(Counter(targets.values())),
              "changes": dict(changed),
              "methods": dict(Counter(new[k][1] for k in keys if k in new)),
              "checks_after": dict(Counter(r["options_check"] for r in out.values()))}
    with open(os.path.join(args.out, "report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(json.dumps(report, indent=2))

    # Review sample, from the rows the pass changed: filled (were empty),
    # replaced in disagreeing problems, replaced in problems that already matched.
    rnd = random.Random(42)
    changed_rows = {"filled": [], "disagree": [], "recheck": []}
    for k in keys:
        before, after = rows[k]["options"], out[k]["options"]
        if not is_full(before) and is_full(after):
            changed_rows["filled"].append(k)
        elif is_full(before) and not same_options(before, after):
            changed_rows[targets[k]].append(k)
    n = args.review
    quota = {"filled": n * 3 // 8, "disagree": n * 3 // 8}
    quota["recheck"] = n - quota["filled"] - quota["disagree"]
    sample = [(g, k) for g, ks in changed_rows.items() for k in rnd.sample(ks, min(len(ks), quota[g]))]
    with open(os.path.join(args.out, "review.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["image", "group", "options_before", "options_after", "source", "check", "correct? (yes/no)"])
        for g, k in sample:
            w.writerow([f"{k[0]}_{k[1]}.png", g, json.dumps(rows[k]["options"], ensure_ascii=False),
                        json.dumps(out[k]["options"], ensure_ascii=False), out[k]["options_source"],
                        out[k]["options_check"], ""])
    if args.review_images:
        folder = os.path.join(args.out, "review_images")
        os.makedirs(folder, exist_ok=True)
        for _, k in sample:
            with open(os.path.join(folder, f"{k[0]}_{k[1]}.png"), "wb") as f:
                f.write(images[k])
    print(f"Wrote {args.out}/train.jsonl, val.jsonl, report.json and review.csv")


if __name__ == "__main__":
    main()
