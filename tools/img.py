#!/usr/bin/env python3
"""img — quick image operations for slide pictures (result folder + log like every tool).

  python tools/img.py info photo.jpg pics/                    # size, aspect, dpi at a given slide width
  python tools/img.py crop photo.jpg --box 10%,0,90%,100%      # left,top,right,bottom (px or %)
  python tools/img.py cover photo.jpg --size 1920x1080 --focus 0.5,0.3   # fill a frame (16:9 slide) from a focus point
  python tools/img.py fit photo.jpg --size 1600x1600           # shrink into a box keeping proportions
  python tools/img.py optimize pics/ --max 2400 --webp         # lighter files for pptx/html (quality 88)
  python tools/img.py sheet pics/ --cols 5                     # contact sheet of a folder
  python tools/img.py diff a.png b.png                         # changed pixels + red highlight image
  python tools/img.py contrast "#FFFFFF" "#C8553D"             # WCAG contrast ratio of two colours

Outputs go to checks/runs/<time>-img-<name>/ (mirrored to checks/latest/), originals are never modified.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import _boot  # noqa: F401

from PIL import Image

from pptkit import imaging
from pptkit.report import Run


def _size(s):
    w, h = s.lower().split("x")
    return int(w), int(h)


def _frac_box(spec: str, w: int, h: int):
    vals = []
    for i, v in enumerate(spec.split(",")):
        v = v.strip()
        full = w if i % 2 == 0 else h
        vals.append(int(round(float(v[:-1]) / 100 * full)) if v.endswith("%") else int(float(v)))
    return tuple(vals)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["info", "crop", "cover", "fit", "optimize", "sheet", "diff", "contrast"])
    ap.add_argument("items", nargs="+")
    ap.add_argument("--box", help="crop: left,top,right,bottom (px или %)")
    ap.add_argument("--size", help="WxH для cover/fit")
    ap.add_argument("--focus", default="0.5,0.5", help="точка интереса для cover (доли 0..1)")
    ap.add_argument("--max", type=int, default=2400, help="optimize: максимальная сторона")
    ap.add_argument("--webp", action="store_true", help="optimize: сохранить в WebP")
    ap.add_argument("--quality", type=int, default=88)
    ap.add_argument("--cols", type=int)
    ap.add_argument("--slide-width-in", type=float, default=13.333, help="info: ширина слайда в дюймах для расчёта dpi")
    ap.add_argument("-o", "--out")
    ap.add_argument("-q", "--quiet", action="store_true")
    a = ap.parse_args(argv)

    if a.cmd == "contrast":
        def rgb(c):
            c = c.lstrip("#")
            return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))
        r = imaging.contrast_ratio(rgb(a.items[0]), rgb(a.items[1]))
        verdict = "✔ AA для любого текста" if r >= 4.5 else "≈ только крупный текст (≥ 24pt)" if r >= 3 else "✖ плохо читается"
        print(f"контраст {a.items[0]} / {a.items[1]} = {r:.2f}:1  {verdict}")
        return 0

    files = imaging.collect([Path(p) for p in a.items]) if a.cmd not in ("diff",) else [Path(p) for p in a.items]
    run = Run("img", a.cmd + "-" + Path(a.items[0]).stem, a.out, quiet=a.quiet)
    outs, md = [], []
    with run.step(f"{a.cmd}: {len(files)} файл(ов)"):
        if a.cmd == "info":
            md.append("| файл | размер | пропорции | KB | dpi на всю ширину слайда | dpi на половину |\n|---|---|---|---|---|---|")
            for f in files:
                i = imaging.info(f)
                d_full, d_half = i["w"] / a.slide_width_in, i["w"] / (a.slide_width_in / 2)
                md.append(f"| {f.name} | {i['w']}×{i['h']} | {i['aspect']} | {i['kb']} | {d_full:.0f}"
                          f"{' ⚠' if d_full < 96 else ''} | {d_half:.0f} |")
            outs = files
        elif a.cmd == "diff":
            r = imaging.diff(files[0], files[1], run.path("diff.png"))
            md.append(f"Изменено **{r['changed_pct']}%** пикселей, область {r['bbox']}")
            outs = [files[0], files[1], run.path("diff.png")]
        elif a.cmd == "sheet":
            outs = [imaging.contact_sheet(files, run.path("contact_sheet.png"), cols=a.cols, title=f"{len(files)} изображений")]
        else:
            for f in files:
                im = imaging.open_image(f)
                if a.cmd == "crop":
                    res = im.crop(_frac_box(a.box, im.width, im.height))
                elif a.cmd == "cover":
                    fx, fy = (float(v) for v in a.focus.split(","))
                    res = imaging.cover(im, _size(a.size), focus=(fx, fy))
                elif a.cmd == "fit":
                    res = im.copy()
                    res.thumbnail(_size(a.size), Image.LANCZOS)
                else:  # optimize
                    res = im.copy()
                    if max(res.size) > a.max:
                        res.thumbnail((a.max, a.max), Image.LANCZOS)
                ext = ".webp" if a.webp else (".png" if res.mode == "RGBA" else ".jpg")
                dst = run.path(f"{f.stem}{ext}")
                if ext == ".jpg":
                    res.convert("RGB").save(dst, quality=a.quality, optimize=True, progressive=True)
                elif ext == ".webp":
                    res.save(dst, quality=a.quality, method=5)
                else:
                    res.save(dst, optimize=True)
                kb0, kb1 = f.stat().st_size / 1024, dst.stat().st_size / 1024
                md.append(f"- {f.name} {im.width}×{im.height} ({kb0:.0f} KB) → {dst.name} {res.width}×{res.height} ({kb1:.0f} KB)")
                outs.append(dst)
    if len(outs) > 1 and a.cmd not in ("sheet",):
        with run.step("контакт-лист"):
            imaging.contact_sheet(outs, run.path("contact_sheet.png"), cols=a.cols)
        md.append("\n![sheet](contact_sheet.png)")
    run.add_md("\n".join(md))
    print(run.finish())
    return 0


if __name__ == "__main__":
    sys.exit(main())
