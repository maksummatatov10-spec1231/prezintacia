#!/usr/bin/env python3
"""bench — measures how fast every toolkit step is on a given deck (proof of "milliseconds").

  python tools/bench.py presentations/drevnyaya-gretsiya.pptx [--html presentations/drevnyaya-gretsiya.html]

Writes checks/runs/<time>-bench-<deck>/summary.md with a table (step → ms).
"""
from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
import time
from pathlib import Path

import _boot  # noqa: F401

from pptkit.report import Run


def timed(fn):
    t = time.perf_counter()
    r = fn()
    return (time.perf_counter() - t) * 1000, r


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("deck")
    ap.add_argument("--html")
    ap.add_argument("-q", "--quiet", action="store_true")
    a = ap.parse_args(argv)
    deck = Path(a.deck)
    run = Run("bench", deck.stem, quiet=a.quiet)
    rows = []

    from pptkit import imaging, lint, office
    from pptkit.edit import Deck, apply_ops
    from pptkit.inspect import inspect_deck

    ms, info = timed(lambda: inspect_deck(deck))
    rows.append(("анализ структуры (inspect)", ms, f"{info['slide_count']} слайдов"))
    ms, issues = timed(lambda: lint.lint(info, None, {}))
    rows.append(("проверка качества (lint, без рендеров)", ms, f"{len(issues)} замечаний"))
    ms, _ = timed(lambda: office.slide_hashes(deck))
    rows.append(("хэши слайдов (для инкрементального рендера)", ms, ""))
    ms, r = timed(lambda: office.render_slides(deck, dpi=110))
    rows.append(("рендер всех слайдов (кэш)", ms, f"перерисовано {len(r.get('rendered', []))}"))
    tmp = Path(tempfile.mkdtemp())
    ms, d = timed(lambda: Deck(deck))
    rows.append(("открыть pptx для правки", ms, ""))
    ms, _ = timed(lambda: apply_ops(d, [{"op": "move", "slide": 1, "shape": "picture:1", "dx": "0.1cm"}]))
    rows.append(("операция move", ms, ""))
    out = tmp / "bench.pptx"
    ms, _ = timed(lambda: d.save(out))
    rows.append(("сохранить pptx", ms, f"{out.stat().st_size // 1024} KB"))
    ms, r = timed(lambda: office.render_slides(out, dpi=110))
    rows.append(("рендер после правки (только изменённый слайд)", ms, f"перерисовано {len(r.get('rendered', []))}"))
    imgs = r["images"]
    ms, _ = timed(lambda: imaging.contact_sheet(imgs, tmp / "sheet.png", thumb_w=360))
    rows.append(("контакт-лист всех слайдов", ms, ""))
    if a.html:
        from pptkit.browser import Chrome
        ms, c = timed(lambda: Chrome().start())
        rows.append(("запуск Chromium (холодный)", ms, ""))
        pg = c.page(390, 844)
        ms, _ = timed(lambda: pg.goto(Path(a.html).resolve().as_uri() + "?static=1", wait_until="load"))
        rows.append(("загрузка HTML-презентации", ms, f"{Path(a.html).stat().st_size // 1024} KB"))
        ms, _ = timed(lambda: (pg.evaluate("DECK.go(4,{instant:true})"), Chrome.capture(pg, tmp / "s.jpg")))
        rows.append(("скриншот слайда (телефон, тёплый браузер)", ms, ""))
        ms, _ = timed(lambda: c.shot(None, tmp / "h.png", width=600, height=200, html="<h1>Привет</h1>"))
        rows.append(("скриншот HTML-строки", ms, ""))
        c.close()
    shutil.rmtree(tmp, ignore_errors=True)
    md = ["| шаг | время | примечание |", "|---|---:|---|"] + [f"| {n} | **{m:.0f} ms** | {x} |" for n, m, x in rows]
    run.add_md("## Скорость\n\n" + "\n".join(md))
    for n, m, x in rows:
        run.log(f"{m:9.1f} ms  {n}  {x}")
    print(run.finish())
    return 0


if __name__ == "__main__":
    sys.exit(main())
