#!/usr/bin/env python3
"""Copy only the images a vision experiment needs, to send them to the board.

    python3 prep/pick_images.py --images data/_imgs/images --out data/images \
        data/dev50.jsonl data/dev100.jsonl data/val.jsonl

For every problem in the given files that has a figure (text_only false), it copies
<id>_<language>.png from --images to --out, and says how many were missing. With
--all it copies every problem's image, figure or not.

The images are M3Kang: never commit them (.gitignore excludes data/).
"""
import argparse
import json
import os
import shutil


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("inputs", nargs="+", help="JSONL files with the problems")
    p.add_argument("--images", required=True, help="folder written by prepare_m3kang.py --save-images")
    p.add_argument("--out", default="data/images")
    p.add_argument("--all", action="store_true", help="every problem, not only the ones with a figure")
    args = p.parse_args()

    wanted = set()
    for path in args.inputs:
        with open(path, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                problem = json.loads(line)
                if args.all or problem.get("text_only") is False:
                    wanted.add(f"{problem['id']}_{problem['language']}.png")
    os.makedirs(args.out, exist_ok=True)
    copied = present = 0
    missing = []
    total_bytes = 0
    for name in sorted(wanted):
        source, target = os.path.join(args.images, name), os.path.join(args.out, name)
        if os.path.exists(target):
            present += 1
            total_bytes += os.path.getsize(target)
        elif os.path.exists(source):
            shutil.copyfile(source, target)
            copied += 1
            total_bytes += os.path.getsize(target)
        else:
            missing.append(name)
    print(f"{len(wanted)} images wanted: {copied} copied, {present} already there, "
          f"{len(missing)} missing; {total_bytes / 1e6:.1f} MB in {args.out}")
    if missing:
        print("Missing (run prepare_m3kang.py --save-images with the same --shards): "
              + ", ".join(missing[:10]) + (" ..." if len(missing) > 10 else ""))


if __name__ == "__main__":
    main()
