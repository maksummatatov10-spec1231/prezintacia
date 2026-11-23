#!/usr/bin/env python3
"""fonts — fonts of a presentation: what is used, what is missing, what is embedded; install fonts from Google Fonts.

  python tools/fonts.py check deck.pptx         # used fonts → installed? (real/metric analog/missing), embedded?
  python tools/fonts.py add Montserrat "Open Sans" Roboto   # download from github.com/google/fonts (sparse) + install
  python tools/fonts.py list [фильтр]           # installed families
  python tools/fonts.py find "Nunito" --bold     # path of a concrete face
  python tools/fonts.py embed deck.pptx -o out.pptx --family "Nunito" [--family "Comfortaa"]   # embed into PPTX

Why it matters: LibreOffice renders (our screenshots) and line breaks are only exact when the deck's fonts are
installed. Missing → a metric-compatible analog is used (Arial→Arimo, Calibri→Carlito …) or a visible fallback.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

import _boot  # noqa: F401

from pptkit import fonts as F
from pptkit.env import CACHE, FONTS_DIR, font_dirs

GF = F.GFONTS


def _slug(family: str) -> str:
    return re.sub(r"[^a-z0-9]", "", family.lower())


def _families() -> dict[str, list[Path]]:
    fams: dict[str, list[Path]] = {}
    for d in font_dirs():
        for p in Path(d).rglob("*"):
            if p.suffix.lower() in (".ttf", ".otf", ".ttc"):
                try:
                    fam, _ = F.family_of(p)
                except Exception:  # noqa: BLE001
                    continue
                fams.setdefault(fam, []).append(p)
    return fams


def cmd_list(args):
    fams = _families()
    flt = (args.filter or "").lower()
    rows = sorted(f for f in fams if flt in f.lower())
    for f in rows:
        print(f"{f:34s} {len(fams[f]):3d} файл(ов)")
    print(f"— всего семейств: {len(rows)} (папки: {', '.join(str(d) for d in font_dirs())})")


def cmd_find(args):
    p = F.find_font(args.family, bold=args.bold, italic=args.italic)
    print(p or f"✖ «{args.family}» не найден → python tools/fonts.py add \"{args.family}\"")
    return 0 if p else 1


def _git(*a, cwd=None):
    return subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True, text=True)


def cmd_add(args):
    """Sparse-checkout ofl/<slug> (or apache/, ufl/) from google/fonts, then install statics."""
    t0 = time.time()
    if not (GF / ".git").exists():
        GF.parent.mkdir(parents=True, exist_ok=True)
        print("· клонирую github.com/google/fonts (sparse, без файлов) …")
        _git("clone", "-q", "--depth", "1", "--filter=blob:none", "--sparse", "https://github.com/google/fonts", str(GF))
        _git("sparse-checkout", "set", "--no-cone", "/ofl/nunito/*.ttf", cwd=GF)
    cur = _git("sparse-checkout", "list", cwd=GF).stdout.split()
    want = []
    for fam in args.families:
        s = _slug(fam)
        for lic in ("ofl", "apache", "ufl"):
            want += [f"/{lic}/{s}/*.ttf", f"/{lic}/{s}/static/*.ttf"]
    _git("sparse-checkout", "set", "--no-cone", *sorted(set(cur + want)), cwd=GF)
    found = {fam: sorted(p for lic in ("ofl", "apache", "ufl") for p in (GF / lic / _slug(fam)).rglob("*.ttf"))
             for fam in args.families}
    for fam, files in found.items():
        print(f"  {'✔' if files else '✖'} {fam}: {len(files)} файл(ов)" + ("" if files else
              "  (нет в Google Fonts — положите .ttf в папку и задайте PPTKIT_FONT_DIRS=путь)"))
    res = F.install_toolkit_fonts(verbose=False)
    F.find_font.cache_clear()
    print(f"готово за {time.time() - t0:.1f} с: скопировано {res.get('copied', 0)}, новых статических начертаний "
          f"{res.get('instanced', 0)}, всего {res.get('total_static')} → {FONTS_DIR}")
    # LibreOffice render cache depends on fonts → invalidate
    rc = CACHE / "renders"
    if rc.exists():
        for p in rc.rglob("fonts.json"):
            p.unlink()
    return 0 if all(found.values()) else 1


def cmd_check(args):
    from pptkit.inspect import inspect_deck
    info = inspect_deck(args.deck)
    used = sorted(set(info.get("fonts_used") or []))
    emb = {e.get("family") or e.get("typeface") for e in (info.get("embedded_fonts") or [])}
    print(f"Шрифты в {Path(args.deck).name}:")
    bad = 0
    for fam in used:
        clean = fam.replace(" (theme)", "")
        p = F.find_font(clean)
        analogs = next((row[1:] for row in F.METRIC_FALLBACKS if row[0].lower() == clean.lower()), [])
        analog = next((a for a in analogs if F.find_font(a)), None)
        if p:
            st = f"✔ установлен ({Path(p).name})"
        elif analog:
            st = f"≈ метрический аналог {analog} (переносы строк совпадут)"
        else:
            st = "✖ НЕТ — рендер подставит другой шрифт"
            bad += 1
        print(f"  {fam:32s} {st}{'  · встроен в pptx' if clean in emb else ''}")
    if bad:
        print("\nУстановить: python tools/fonts.py add " + " ".join(f'"{f.replace(" (theme)", "")}"' for f in used
                                                                if not F.find_font(f.replace(' (theme)', ''))))
    return 0


def cmd_embed(args):
    from pptx import Presentation
    prs = Presentation(args.deck)
    faces = {}
    for fam in args.family:
        reg, bold = F.find_font(fam), F.find_font(fam, bold=True)
        if not reg:
            print(f"✖ {fam} не установлен → tools/fonts.py add \"{fam}\"")
            return 1
        faces[fam] = {"regular": reg, **({"bold": bold} if bold and bold != reg else {})}
    res = F.embed_fonts(prs, faces)
    out = args.out or str(Path(args.deck).with_name(Path(args.deck).stem + "_fonts.pptx"))
    prs.save(out)
    for r in res:
        print(f"  ✔ {r}")
    print(out)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("list"); p.add_argument("filter", nargs="?"); p.set_defaults(fn=cmd_list)
    p = sub.add_parser("find"); p.add_argument("family"); p.add_argument("--bold", action="store_true")
    p.add_argument("--italic", action="store_true"); p.set_defaults(fn=cmd_find)
    p = sub.add_parser("add"); p.add_argument("families", nargs="+"); p.set_defaults(fn=cmd_add)
    p = sub.add_parser("check"); p.add_argument("deck"); p.set_defaults(fn=cmd_check)
    p = sub.add_parser("embed"); p.add_argument("deck"); p.add_argument("-o", "--out")
    p.add_argument("--family", action="append", required=True); p.set_defaults(fn=cmd_embed)
    args = ap.parse_args(argv)
    return args.fn(args) or 0


if __name__ == "__main__":
    sys.exit(main())
