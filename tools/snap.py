#!/usr/bin/env python3
"""snap — instant screenshot of ANYTHING → a folder with PNGs, contact sheet, summary.md, log.txt.

  python tools/snap.py deck.pptx                      # every slide (LibreOffice-WASM, cached)
  python tools/snap.py deck.pptx --slides 2,5-7 --dpi 200
  python tools/snap.py report.docx table.xlsx doc.pdf
  python tools/snap.py deck.html --viewport phone --viewport desktop   # pptkit HTML deck: every slide
  python tools/snap.py https://example.com --full
  python tools/snap.py page.html --selector "#chart"
  python tools/snap.py logo.svg --viewport 800x800
  python tools/snap.py --html "<h1 style='font:64px Nunito'>Привет</h1>" --viewport 800x300
  python tools/snap.py photos/ --sheet               # contact sheet of a folder of images

Options: -o DIR (default checks/runs/<time>-snap-<name>, mirrored to checks/latest)
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import _boot  # noqa: F401  (sys.path + venv)
from _boot import parse_pages, parse_viewport

from pptkit import imaging
from pptkit.report import Run

OFFICE = {".pptx", ".ppt", ".pptm", ".potx", ".odp", ".pps", ".ppsx", ".docx", ".doc", ".odt", ".rtf",
          ".xlsx", ".xls", ".ods", ".csv"}
WEB = {".html", ".htm", ".svg", ".xhtml", ".mhtml"}


def snap_office(run, target, args, chrome=None):
    from pptkit import office
    pages = parse_pages(args.slides)
    with run.step(f"render {Path(target).name} ({'кэш' if not args.no_cache else 'без кэша'})") as st:
        res = office.render_slides(target, dpi=args.dpi, pages=pages, use_cache=not args.no_cache)
        st["cached"] = res["cached"]
    out = []
    for i, p in enumerate(res["images"]):
        n = pages[i] if pages else i + 1
        dst = run.path(f"{Path(target).stem}/slide-{n:02d}.png")
        shutil.copy2(p, dst)
        out.append(dst)
    sub, really = office.split_missing(res.get("missingFonts") or [])
    run.log(f"{len(out)} изображ.; перерисовано {len(res.get('rendered', out))}, из кэша "
            f"{len(out) - len(res.get('rendered', out))}; аналоги шрифтов: {sub or '—'}; нет шрифтов: {really or '—'}")
    run.data.setdefault("targets", []).append({"target": str(target), "type": "office", "cached": res["cached"],
                                              "missingFonts": res.get("missingFonts"), "images": [str(p) for p in out]})
    return out


def snap_pdf(run, target, args, chrome=None):
    from pptkit import office
    with run.step(f"pdf → png {Path(target).name}"):
        out = office.pdf_to_png(target, run.path(Path(target).stem), dpi=args.dpi, pages=parse_pages(args.slides))
    run.data.setdefault("targets", []).append({"target": str(target), "type": "pdf", "images": [str(p) for p in out]})
    return out


def snap_web(run, target, args, chrome):
    vps = [parse_viewport(v) for v in (args.viewport or ["desktop"])]
    name = Path(str(target)).stem if not str(target).startswith("http") else "page"
    out = []
    is_deck = False
    if not str(target).startswith(("http://", "https://")) and Path(target).suffix.lower() in (".html", ".htm"):
        txt = Path(target).read_text(encoding="utf-8", errors="ignore")
        is_deck = 'name="generator" content="pptkit-deck"' in txt[:5000] or "window.DECK" in txt
    if is_deck and not args.selector and not args.full:
        with run.step(f"html-презентация {Path(target).name}: {', '.join(v[0] for v in vps)}"):
            res = chrome.deck_shots(target, run.path(name), viewports=dict(vps), slides=parse_pages(args.slides),
                                    static=not args.animated)
        for vp, d in res["viewports"].items():
            out += d["files"]
            if d["audit"]:
                run.log(f"⚠ {vp}: переполнение/выход за экран: {d['audit']}")
        if res["page_errors"] or res["console"]:
            run.log(f"⚠ ошибки страницы: {res['page_errors'] + res['console']}")
        run.data.setdefault("targets", []).append({"target": str(target), "type": "html-deck",
                                                  "audit": {k: v["audit"] for k, v in res["viewports"].items()},
                                                  "errors": res["page_errors"] + res["console"],
                                                  "images": [str(p) for p in out]})
        return out
    for vname, (w, h) in vps:
        dst = run.path(f"{name}/{vname}.png")
        with run.step(f"screenshot {target} @ {vname} {w}×{h}"):
            chrome.shot(target, dst, width=w, height=h, full_page=args.full, selector=args.selector,
                        wait_ms=args.wait, scale=args.scale)
        out.append(dst)
    run.data.setdefault("targets", []).append({"target": str(target), "type": "web", "images": [str(p) for p in out]})
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("targets", nargs="*", help="файлы / папки / URL")
    ap.add_argument("--html", help="HTML-строка для мгновенного рендера")
    ap.add_argument("-o", "--out", help="папка результата")
    ap.add_argument("--slides", help="номера слайдов/страниц: 1,3,5-7")
    ap.add_argument("--dpi", type=int, default=144, help="для pptx/pdf (144 ≈ 1920px ширина слайда)")
    ap.add_argument("--viewport", action="append", help="desktop|laptop|fullhd|tablet|phone|android|WxH (можно несколько)")
    ap.add_argument("--full", action="store_true", help="вся страница целиком (web)")
    ap.add_argument("--selector", help="CSS-селектор элемента (web)")
    ap.add_argument("--wait", type=int, default=0, help="подождать N мс перед снимком (web)")
    ap.add_argument("--scale", type=float, default=1, help="device scale factor (web), 2 = retina")
    ap.add_argument("--animated", action="store_true", help="html-презентация: не завершать анимации мгновенно")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--sheet", action="store_true", help="всегда делать контакт-лист")
    ap.add_argument("-q", "--quiet", action="store_true")
    args = ap.parse_args(argv)
    if not args.targets and not args.html:
        ap.print_help()
        return 2
    first = args.targets[0] if args.targets else "html"
    run = Run("snap", first, args.out, quiet=args.quiet)
    images: list[Path] = []
    failed: list[str] = []
    chrome = None
    try:
        needs_chrome = bool(args.html) or any(
            str(t).startswith(("http://", "https://")) or Path(t).suffix.lower() in WEB for t in args.targets)
        if needs_chrome:
            from pptkit.browser import Chrome
            with run.step("запуск Chromium"):
                chrome = Chrome().start()
        if args.html:
            vname, (w, h) = parse_viewport((args.viewport or ["800x450"])[0])
            dst = run.path("html.png")
            with run.step("render html string"):
                chrome.shot(None, dst, width=w, height=h, html=args.html, full_page=args.full, scale=args.scale)
            images.append(dst)
        for t in args.targets:
          p = Path(t)
          try:
            if str(t).startswith(("http://", "https://")) or p.suffix.lower() in WEB:
                images += snap_web(run, t, args, chrome)
            elif p.is_dir():
                imgs = imaging.collect([p])
                run.log(f"папка {p}: {len(imgs)} изображений")
                images += imgs
                args.sheet = True
            elif p.suffix.lower() in OFFICE:
                images += snap_office(run, p, args)
            elif p.suffix.lower() == ".pdf":
                images += snap_pdf(run, p, args)
            elif p.suffix.lower() in imaging.IMG_EXT:
                dst = run.path(p.name)
                shutil.copy2(p, dst)
                images.append(dst)
            else:
                raise ValueError(f"неизвестный тип файла: {t}")
          except Exception as e:  # noqa: BLE001 — report and continue with the other targets
            failed.append(str(t))
            msg = str(e).splitlines()[0][:300]
            run.log(f"✖ {t}: {msg}")
            run.add_md(f"### ✖ {t}\n\n{msg}\n")
        if len(images) > 1 or args.sheet:
            with run.step("контакт-лист"):
                sheet = imaging.contact_sheet(images, run.path("contact_sheet.png"),
                                              title=f"{Path(first).name} — {len(images)} шт.",
                                              labels=[f"{Path(i).parent.name}/{Path(i).name}" for i in images])
            run.add_md(f"![contact sheet](contact_sheet.png)\n")
        run.add_md("## Файлы\n" + "\n".join(f"- `{Path(i).relative_to(run.dir) if run.dir in Path(i).parents else i}`"
                                           for i in images))
        run.data["images"] = [str(i) for i in images]
    finally:
        if chrome:
            chrome.close()
    out = run.finish(ok=not failed)
    print(out)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
