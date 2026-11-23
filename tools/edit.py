#!/usr/bin/env python3
"""edit — instant precise operations on a .pptx + automatic before/after screenshots.

  # one or several operations (each --do is "op key=value ...")
  python tools/edit.py deck.pptx -o deck_v2.pptx \
      --do "move slide=2 shape='Picture 3' x=2cm y=10%" \
      --do "resize slide=2 shape=id:5 w=12cm keep_aspect=true" \
      --do "zoom slide=4 shape=picture:1 factor=1.4 focus=0.35,0.5" \
      --do "crop slide=4 shape=picture:1 left=10% right=5%" \
      --do "fit slide=5 shape='Рисунок 2' mode=cover focus=0.5,0.3" \
      --do "replace_text old='2023' new='2024'" \
      --do "font slide=1 shape=title size=48 bold=true color=#1F4E79" \
      --do "align slide=3 shapes='Picture 1,Picture 2' how=top" \
      --do "z slide=3 shape='Picture 1' where=back" \
      --do "move_slide src=7 dst=2" --do "delete_slide slide=9"

  python tools/edit.py deck.pptx --ops changes.yaml -o deck_v2.pptx   # list of ops in YAML/JSON
  python tools/edit.py deck.pptx --list 3          # show shapes of slide 3 (ids, names, boxes) and exit
  python tools/edit.py deck.pptx --ops ops.yaml --fast   # no renders (pure edit, milliseconds)

Shape selectors: id:7 | 'Name' | text:фрагмент | picture:1 | title | idx:0
Units: cm mm in pt px % (of slide width for x/w, height for y/h) or EMU
Result folder: ops.json, log, before/after PNGs of touched slides, compare-XX.png (side by side + diff)
"""
from __future__ import annotations

import argparse
import shlex
import shutil
import sys
from pathlib import Path

import _boot  # noqa: F401

from pptkit import imaging
from pptkit.edit import OPS, Deck, apply_ops, load_ops
from pptkit.report import Run


def _auto(v: str):
    lv = v.lower()
    if lv in ("true", "yes", "on"):
        return True
    if lv in ("false", "no", "off"):
        return False
    if lv in ("none", "null"):
        return None
    try:
        if "." in v:
            return float(v)
        return int(v)
    except ValueError:
        return v


def parse_do(s: str) -> dict:
    parts = shlex.split(s)
    op = {"op": parts[0]}
    for kv in parts[1:]:
        k, _, v = kv.partition("=")
        if k in ("shapes",):
            op[k] = [x.strip() for x in v.split(",")]
        elif k == "focus":
            op[k] = [float(x) for x in v.split(",")]
        elif k in ("shape", "old", "new", "text", "image", "color", "x", "y", "w", "h", "dx", "dy", "cx", "cy",
                   "left", "top", "right", "bottom", "name"):
            op[k] = v
        else:
            op[k] = _auto(v)
    return op


def list_shapes(path, slide):
    from pptkit.inspect import inspect_deck, _walk
    info = inspect_deck(path)
    s = info["slides"][slide - 1]
    print(f"Слайд {slide}: {s['title']}  (макет {s['layout']})")
    for sh in _walk(s["shapes"]):
        extra = ""
        if sh.get("text") and sh["text"]["text"].strip():
            extra = "«" + sh["text"]["text"].replace("\n", " ⏎ ")[:60] + "»"
        if sh.get("picture"):
            p = sh["picture"]
            extra += f" 🖼 {p.get('px')} dpi≈{p.get('effective_dpi')} crop={p.get('crop')}"
        print(f"  id:{sh['id']:<4} {sh['name'][:28]:<28} {sh['kind']:<22} x,y,w,h(см)={sh['cm']}  {extra}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("deck")
    ap.add_argument("-o", "--output", help="куда сохранить (по умолчанию <имя>_edited.pptx рядом)")
    ap.add_argument("--do", action="append", default=[], help='операция: "op key=value ..."')
    ap.add_argument("--ops", help="файл YAML/JSON со списком операций (или JSON-строка)")
    ap.add_argument("--list", type=int, metavar="SLIDE", help="показать фигуры слайда и выйти")
    ap.add_argument("--fast", action="store_true", help="без рендера до/после")
    ap.add_argument("--inplace", action="store_true", help="перезаписать исходный файл")
    ap.add_argument("--dpi", type=int, default=110)
    ap.add_argument("--out", help="папка результата")
    ap.add_argument("-q", "--quiet", action="store_true")
    args = ap.parse_args(argv)
    src = Path(args.deck)
    if args.list:
        list_shapes(src, args.list)
        return 0
    ops = [parse_do(s) for s in args.do]
    if args.ops:
        ops += load_ops(args.ops)
    if not ops:
        print("Нет операций. Доступно:", ", ".join(OPS))
        return 2
    out = src if args.inplace else Path(args.output or src.with_name(src.stem + "_edited" + src.suffix))
    run = Run("edit", src, args.out, quiet=args.quiet)
    before_imgs = {}
    # 1) apply the operations first (milliseconds) — a typo fails fast, before any rendering
    from pptkit.edit import EditError
    try:
        with run.step(f"применение {len(ops)} операций"):
            deck = Deck(src)
            results = apply_ops(deck, ops)
            saved = deck.save(out)
    except (EditError, ValueError, KeyError, TypeError) as e:
        run.log(f"✖ ОШИБКА: {e}")
        run.add_md(f"## ✖ Ошибка\n\n{e}\n\nПодсказка: `python tools/edit.py {src} --list N` покажет фигуры слайда N.")
        run.finish(ok=False)
        print(f"✖ {e}", file=sys.stderr)
        return 2
    # 2) renders before/after (incremental cache: only changed slides are re-rendered)
    if not args.fast:
        from pptkit import office
        with run.step("рендер ДО (кэш)"):
            rb = office.render_slides(src, dpi=args.dpi)
        before_imgs = {i + 1: p for i, p in enumerate(rb["images"])}
    for r in results:
        run.log(f"  ✔ {r['op']} {r.get('shape', '')} ({r['ms']} ms) {r.get('after', '')}")
    run.write_json("ops.json", results)
    run.add_md("## Операции\n" + "\n".join(
        f"{r['i']}. `{r['op']}` слайд {r.get('slide') or '—'} {r.get('shape', '')} — {r['ms']} ms"
        + (f"<br>до: {r['before']}<br>после: {r['after']}" if 'after' in r else "") for r in results))
    run.add_md(f"\nСохранено: `{saved}`")
    if not args.fast:
        from pptkit import office
        with run.step("рендер ПОСЛЕ"):
            ra = office.render_slides(saved, dpi=args.dpi)
        after_imgs = {i + 1: p for i, p in enumerate(ra["images"])}
        touched = sorted(deck.touched) or sorted(after_imgs)
        comps = []
        structural = any(r["op"] in ("move_slide", "delete_slide", "duplicate_slide") for r in results)
        for n in touched:
            if n not in after_imgs:
                continue
            a = run.path(f"after/slide-{n:02d}.png")
            shutil.copy2(after_imgs[n], a)
            if n in before_imgs and not structural:
                b = run.path(f"before/slide-{n:02d}.png")
                shutil.copy2(before_imgs[n], b)
                d = imaging.diff(b, a, run.path(f"diff/slide-{n:02d}.png"))
                c = imaging.contact_sheet([b, a, run.path(f"diff/slide-{n:02d}.png")], run.path(f"compare-{n:02d}.png"),
                                          cols=3, thumb_w=520, labels=["ДО", "ПОСЛЕ", f"разница {d['changed_pct']}%"],
                                          title=f"Слайд {n}")
                comps.append(c)
                run.log(f"слайд {n}: изменено {d['changed_pct']}% пикселей, область {d['bbox']}")
            else:
                comps.append(a)
        run.add_md("\n## До / после\n" + "\n".join(f"![{Path(c).name}]({Path(c).relative_to(run.dir)})" for c in comps))
    d = run.finish()
    print(saved)
    print(d / "summary.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
