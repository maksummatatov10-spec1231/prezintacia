#!/usr/bin/env python3
"""Build «Как появилась Древняя Греция» → presentations/drevnyaya-gretsiya.pptx + .html, then check.

  python deck/greece/build.py              # assets (if missing) + PPTX + HTML + full check with screenshots
  python deck/greece/build.py --pptx       # only PPTX
  python deck/greece/build.py --html       # only HTML
  python deck/greece/build.py --no-check   # skip the screenshot check
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import slides as S  # noqa: E402  (also sets up sys.path + deck fonts)

ROOT = S.ROOT
OUT = ROOT / "presentations"
PPTX = OUT / "drevnyaya-gretsiya.pptx"
HTML = OUT / "drevnyaya-gretsiya.html"


def main(argv):
    t0 = time.time()
    only_pptx, only_html = "--pptx" in argv, "--html" in argv
    if not (S.A / "maps" / "aegean.png").exists():
        import assets
        assets.main()
    model = S.build_slides()
    print(f"model: {len(model)} slides ({time.time() - t0:.2f}s)")
    if not only_html:
        import render_pptx
        st = render_pptx.render(model, PPTX)
        print(f"PPTX → {PPTX}  {st['kb']} KB · shapes {st['shapes']} · animations {st['animations']} · "
              f"triggers {st['triggers']} ({time.time() - t0:.2f}s)")
    if not only_pptx:
        import render_html
        st = render_html.render(model, HTML)
        print(f"HTML → {HTML}  {st['kb']} KB ({time.time() - t0:.2f}s)")
    if "--no-check" not in argv:
        sys.path.insert(0, str(ROOT / "tools"))
        import check
        targets = [str(p) for p in ((PPTX,) if only_pptx else (HTML,) if only_html else (PPTX, HTML))]
        check.main(targets + ["-q", "--min-pt", "14"])
    print(f"done in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main(sys.argv[1:])
