#!/usr/bin/env python3
"""analyze — millisecond structural analysis of a .pptx (no rendering).

  python tools/analyze.py deck.pptx            # prints the markdown report, writes folder
  python tools/analyze.py deck.pptx --json     # JSON to stdout
  python tools/analyze.py deck.pptx --slide 3  # only one slide
"""
from __future__ import annotations

import argparse
import json
import sys

import _boot  # noqa: F401

from pptkit import inspect as insp
from pptkit import lint
from pptkit.report import Run


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("deck")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--slide", type=int)
    ap.add_argument("--out")
    ap.add_argument("-q", "--quiet", action="store_true")
    args = ap.parse_args(argv)
    run = Run("analyze", args.deck, args.out, quiet=True)
    with run.step("inspect"):
        info = insp.inspect_deck(args.deck)
    if args.slide:
        info["slides"] = [info["slides"][args.slide - 1]]
    with run.step("lint"):
        issues = lint.lint(info)
    md = insp.to_markdown(info) + "\n" + lint.to_markdown(issues)
    run.write("analysis.md", md)
    run.write_json("analysis.json", info)
    run.write_json("lint.json", issues)
    run.write("text.txt", insp.text_dump(info))
    run.add_md(md)
    d = run.finish()
    if args.json:
        print(json.dumps(info, ensure_ascii=False, indent=1, default=str))
    elif not args.quiet:
        print(md)
    print(f"→ {d}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
