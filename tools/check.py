#!/usr/bin/env python3
"""check — ONE command = full analysis + screenshots of a deck, in one folder.

  python tools/check.py deck.pptx                 # analysis + lint + every slide PNG + contact sheet
  python tools/check.py deck.pptx --fast          # no rendering: analysis + lint only (≈0.3 s)
  python tools/check.py deck.pptx --slides 3-5    # render only some slides
  python tools/check.py deck.html                 # HTML deck: desktop + phone screenshots + overflow audit
  python tools/check.py deck.pptx deck.html       # both

Folder (checks/runs/<time>-check-<name>/, mirrored to checks/latest/):
  summary.md      — overview + quality issues + contact sheet
  analysis.md     — every slide / shape / picture / font / animation
  analysis.json   — the same as data
  lint.md / .json — problems with severity + how to fix
  text.txt        — all slide text + speaker notes
  slides/*.png    — slide renders;  contact_sheet.jpg — all slides in one image
  log.txt         — timed log of every step
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import _boot  # noqa: F401
from _boot import parse_pages, parse_viewport

from pptkit import imaging
from pptkit.report import Run


def check_pptx(run: Run, path: Path, args) -> dict:
    from pptkit import inspect as insp
    from pptkit import lint as lint_mod
    tag = path.stem
    with run.step("анализ структуры"):
        info = insp.inspect_deck(path)
    run.write_json(f"{tag}/analysis.json", info)
    run.write(f"{tag}/analysis.md", insp.to_markdown(info))
    run.write(f"{tag}/text.txt", insp.text_dump(info))
    renders = None
    if not args.fast:
        from pptkit import office
        pages = parse_pages(args.slides)
        with run.step("рендер слайдов (LibreOffice WASM)") as st:
            res = office.render_slides(path, dpi=args.dpi, pages=pages, use_cache=not args.no_cache)
            st["cached"] = res["cached"]
        renders = []
        for i, p in enumerate(res["images"]):
            n = pages[i] if pages else i + 1
            dst = run.path(f"{tag}/slides/slide-{n:02d}.png")
            shutil.copy2(p, dst)
            renders.append(dst)
        sub, really = office.split_missing(res.get("missingFonts") or [])
        if sub:
            run.log("шрифты заменены метрическими аналогами (переносы строк как в PowerPoint): "
                    + ", ".join(f"{k}→{v}" for k, v in sub.items()))
        if really:
            run.log(f"⚠ шрифты отсутствуют (подставлен похожий, переносы могут отличаться): {really}")
        run.log(f"слайды: перерисовано {len(res.get('rendered', renders))}, из кэша "
                f"{len(renders) - len(res.get('rendered', renders))}")
        if pages:  # align list with slide numbers for contrast sampling
            full = [None] * info["slide_count"]
            for n, p in zip(pages, renders):
                full[n - 1] = p
            renders_for_lint = full
        else:
            renders_for_lint = renders
        with run.step("контакт-лист"):
            labels = [f"Слайд {Path(p).stem.split('-')[-1].lstrip('0')} · "
                      f"{(info['slides'][int(Path(p).stem.split('-')[-1]) - 1]['title'] or '')[:40]}" for p in renders]
            imaging.contact_sheet(renders, run.path(f"{tag}/contact_sheet.jpg"), cols=args.cols, thumb_w=480,
                                  title=f"{path.name} — {info['slide_count']} слайдов", labels=labels)
    else:
        renders_for_lint = None
    with run.step("проверка качества (lint)"):
        issues = lint_mod.lint(info, renders_for_lint, {"min_pt": args.min_pt, "max_words": args.max_words})
    run.write_json(f"{tag}/lint.json", issues)
    run.write(f"{tag}/lint.md", lint_mod.to_markdown(issues))
    cnt = {k: sum(1 for i in issues if i["severity"] == k) for k in ("error", "warn", "info")}
    run.add_md(f"## {path.name}\n\n- Слайдов: **{info['slide_count']}**, размер {info['slide_size']['cm'][0]}×"
               f"{info['slide_size']['cm'][1]} см, файл {info['kb']} KB\n- Шрифты: "
               + (", ".join(f"`{f}`" for f in info["fonts_used"]) or "—")
               + f"\n- Проблемы: 🛑 {cnt['error']} · ⚠️ {cnt['warn']} · ℹ️ {cnt['info']} → `{tag}/lint.md`\n"
               + (f"\n![slides]({tag}/contact_sheet.jpg)\n" if renders else "")
               + "\n" + lint_mod.to_markdown([i for i in issues if i["severity"] != "info"]))
    return {"file": str(path), "slides": info["slide_count"], "issues": cnt}


def check_html(run: Run, path: Path, args) -> dict:
    from pptkit.browser import Chrome
    vps = dict(parse_viewport(v) for v in (args.viewport or ["desktop", "phone"]))
    tag = path.stem + "_html"
    with run.step("запуск Chromium"):
        chrome = Chrome().start()
    try:
        with run.step(f"скриншоты слайдов: {', '.join(vps)}"):
            res = chrome.deck_shots(path, run.path(tag), viewports=vps, slides=parse_pages(args.slides))
        if args.frames:
            for s in parse_pages(args.frames):
                with run.step(f"кадры анимации слайда {s}"):
                    chrome.frames(path, s, out=run.path(f"{tag}/anim-slide-{s:02d}.png"))
    finally:
        chrome.close()
    md = [f"## {path.name} (HTML)\n"]
    for vp, d in res["viewports"].items():
        with run.step(f"контакт-лист {vp}"):
            land = d["size"][0] > d["size"][1]
            imaging.contact_sheet(d["files"], run.path(f"{tag}/contact_{vp}.jpg"), cols=args.cols if land else 10,
                                  thumb_w=480 if land else 300,
                                  title=f"{path.name} @ {vp} {d['size'][0]}×{d['size'][1]}",
                                  labels=[f"Слайд {i + 1}" for i in range(len(d["files"]))])
        md.append(f"### {vp} {d['size'][0]}×{d['size'][1]} — {d['count']} слайдов, {d['ms']} ms\n")
        md.append(f"![{vp}]({tag}/contact_{vp}.jpg)\n")
        if d["audit"]:
            md.append("⚠️ Переполнение / выход за экран:\n" + "\n".join(f"- {a}" for a in d["audit"]))
        else:
            md.append("✅ Ничего не выходит за экран, текст не переполнен.")
    errs = res["page_errors"] + res["console"]
    md.append("\n" + ("⚠️ Ошибки JS: " + "; ".join(errs) if errs else "✅ Ошибок JavaScript нет."))
    run.add_md("\n".join(md))
    run.write_json(f"{tag}/audit.json", {k: {"audit": v["audit"], "ms": v["ms"]} for k, v in res["viewports"].items()} |
                   {"errors": errs})
    return {"file": str(path), "audit": {k: v["audit"] for k, v in res["viewports"].items()}, "errors": errs}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("targets", nargs="+")
    ap.add_argument("-o", "--out")
    ap.add_argument("--fast", action="store_true", help="без рендера (только анализ + lint)")
    ap.add_argument("--slides", help="1,3,5-7")
    ap.add_argument("--dpi", type=int, default=144)
    ap.add_argument("--cols", type=int, default=4)
    ap.add_argument("--min-pt", type=float, default=14)
    ap.add_argument("--max-words", type=int, default=80, help="слов на слайде до предупреждения")
    ap.add_argument("--viewport", action="append", help="для HTML: desktop|phone|WxH (по умолчанию desktop+phone)")
    ap.add_argument("--frames", help="HTML: снять кадры анимации для слайдов (например 1,4)")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("-q", "--quiet", action="store_true")
    args = ap.parse_args(argv)
    run = Run("check", args.targets[0], args.out, quiet=args.quiet)
    results = []
    ok = True
    try:
        for t in args.targets:
            p = Path(t)
            if not p.exists():
                raise SystemExit(f"Нет файла {t}")
            if p.suffix.lower() in (".html", ".htm"):
                results.append(check_html(run, p, args))
            else:
                results.append(check_pptx(run, p, args))
    except Exception:
        ok = False
        raise
    finally:
        run.data["results"] = results
        out = run.finish(ok)
    print(out / "summary.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
