"""Full structural analysis of a .pptx: every slide, every shape, geometry, text, fonts,
pictures (pixel size, effective DPI, crop), media, notes, transitions & animations.

    info = inspect_deck("deck.pptx")      # dict (JSON-serialisable)
    md = to_markdown(info)                # human readable report
"""
from __future__ import annotations

import hashlib
import io
from collections import Counter
from pathlib import Path

from lxml import etree
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE, PP_PLACEHOLDER
from pptx.util import Emu

from . import anim
from .units import EMU_PER_IN, emu_to

A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def _geom(sh, sw, shh):
    try:
        x, y, w, h = sh.left or 0, sh.top or 0, sh.width or 0, sh.height or 0
    except Exception:
        x = y = w = h = 0
    return {"x": x, "y": y, "w": w, "h": h,
            "cm": [emu_to(x), emu_to(y), emu_to(w), emu_to(h)],
            "pct": [round(100 * x / sw, 1), round(100 * y / shh, 1), round(100 * w / sw, 1), round(100 * h / shh, 1)],
            "rot": round(getattr(sh, "rotation", 0) or 0, 1)}


def _kind(sh) -> str:
    try:
        st = sh.shape_type
    except Exception:
        st = None
    if sh.is_placeholder:
        try:
            return f"placeholder:{PP_PLACEHOLDER(sh.placeholder_format.type).name.lower()}"
        except Exception:
            return "placeholder"
    names = {MSO_SHAPE_TYPE.PICTURE: "picture", MSO_SHAPE_TYPE.GROUP: "group", MSO_SHAPE_TYPE.TABLE: "table",
             MSO_SHAPE_TYPE.CHART: "chart", MSO_SHAPE_TYPE.TEXT_BOX: "textbox", MSO_SHAPE_TYPE.AUTO_SHAPE: "autoshape",
             MSO_SHAPE_TYPE.LINE: "line", MSO_SHAPE_TYPE.MEDIA: "media", MSO_SHAPE_TYPE.FREEFORM: "freeform",
             MSO_SHAPE_TYPE.EMBEDDED_OLE_OBJECT: "ole", MSO_SHAPE_TYPE.LINKED_PICTURE: "linked-picture"}
    if st in names:
        return names[st]
    tag = etree.QName(sh._element).localname
    if tag == "graphicFrame" and sh._element.find(".//{http://schemas.openxmlformats.org/drawingml/2006/diagram}relIds") is not None:
        return "smartart"
    if tag == "cxnSp":
        return "connector"
    return tag


def _text_info(sh):
    if not getattr(sh, "has_text_frame", False) or not sh.has_text_frame:
        return None
    tf = sh.text_frame
    sizes, fonts, colors, paras = Counter(), Counter(), Counter(), []
    for p in tf.paragraphs:
        txt = "".join(r.text for r in p.runs) or p.text
        paras.append({"text": txt, "level": p.level})
        for r in p.runs:
            f = r.font
            if f.size:
                sizes[round(f.size.pt, 1)] += len(r.text)
            if f.name:
                fonts[f.name] += len(r.text)
            try:
                if f.color and f.color.type is not None and f.color.rgb is not None:
                    colors[str(f.color.rgb)] += len(r.text)
            except Exception:
                pass
        # paragraph default run props
        dr = p._p.find(f"{A}pPr/{A}defRPr")
        if dr is not None and dr.get("sz"):
            sizes[int(dr.get("sz")) / 100] += 0
    bodyPr = tf._txBody.find(f"{A}bodyPr")
    autofit = None
    if bodyPr is not None:
        if bodyPr.find(f"{A}normAutofit") is not None:
            na = bodyPr.find(f"{A}normAutofit")
            autofit = f"shrink(fontScale={na.get('fontScale', '100%')})"
        elif bodyPr.find(f"{A}spAutoFit") is not None:
            autofit = "resize-shape"
        elif bodyPr.find(f"{A}noAutofit") is not None:
            autofit = "none"
    text = tf.text
    ins = {}
    if bodyPr is not None:
        for k, d in (("lIns", 91440), ("rIns", 91440), ("tIns", 45720), ("bIns", 45720)):
            ins[k] = int(bodyPr.get(k, d))
    lns = []
    for p in tf.paragraphs:
        sp = p._p.find(f"{A}pPr/{A}lnSpc/{A}spcPct")
        if sp is not None:
            lns.append(int(sp.get("val")) / 100000)
    return {"text": text, "chars": len(text), "words": len(text.split()), "paragraphs": paras,
            "insets": ins, "line_spacing": (sum(lns) / len(lns)) if lns else 1.0,
            "sizes_pt": dict(sizes), "fonts": dict(fonts), "colors": dict(colors), "autofit": autofit,
            "wrap": bodyPr.get("wrap") if bodyPr is not None else None,
            "anchor": bodyPr.get("anchor") if bodyPr is not None else None}


def _picture_info(sh):
    try:
        img = sh.image
    except Exception:
        return {"error": "no embedded image (linked?)"}
    blob = img.blob
    px = None
    try:
        from PIL import Image
        with Image.open(io.BytesIO(blob)) as im:
            px = im.size
    except Exception:
        pass
    crop = {k: round(getattr(sh, f"crop_{k}"), 4) for k in ("left", "top", "right", "bottom")}
    info = {"format": img.ext, "kb": round(len(blob) / 1024, 1), "px": px,
            "sha1": hashlib.sha1(blob).hexdigest()[:12], "crop": crop, "partname": str(img.filename or "")}
    if px and sh.width and sh.height:
        vis_w = px[0] * (1 - crop["left"] - crop["right"])
        vis_h = px[1] * (1 - crop["top"] - crop["bottom"])
        dpi = min(vis_w / (sh.width / EMU_PER_IN), vis_h / (sh.height / EMU_PER_IN))
        info["effective_dpi"] = int(dpi)
        # aspect distortion: displayed aspect vs visible pixel aspect
        if vis_h and sh.height:
            info["distortion"] = round((sh.width / sh.height) / (vis_w / vis_h), 3)
    descr = sh._element.find(f".//{P}cNvPr")
    info["alt"] = descr.get("descr") if descr is not None else None
    return info


def _fill_info(sh):
    try:
        f = sh.fill
        if f.type is None:
            return None
        t = str(f.type).split(".")[-1].split(" ")[0].lower()
        if t.startswith("solid"):
            try:
                return {"type": "solid", "rgb": str(f.fore_color.rgb)}
            except Exception:
                return {"type": "solid", "theme": str(getattr(f.fore_color, "theme_color", ""))}
        return {"type": t}
    except Exception:
        return None


def _shape(sh, sw, shh, z):
    d = {"id": sh.shape_id, "name": sh.name, "kind": _kind(sh), "z": z, **_geom(sh, sw, shh)}
    t = _text_info(sh)
    if t:
        d["text"] = t
    if d["kind"] in ("picture", "linked-picture") or (d["kind"].startswith("placeholder") and hasattr(sh, "image")):
        try:
            d["picture"] = _picture_info(sh)
        except Exception:
            pass
    fill = _fill_info(sh)
    if fill:
        d["fill"] = fill
    if d["kind"] == "group":
        d["children"] = [_shape(c, sw, shh, i) for i, c in enumerate(sh.shapes)]
    if d["kind"] == "table":
        tbl = sh.table
        d["table"] = {"rows": len(tbl.rows), "cols": len(tbl.columns),
                      "cells": [[c.text for c in r.cells] for r in tbl.rows]}
    if d["kind"] == "chart":
        try:
            ch = sh.chart
            d["chart"] = {"type": str(ch.chart_type), "series": [s.name for s in ch.plots[0].series]}
        except Exception:
            pass
    link = sh._element.find(f".//{A}hlinkClick")
    if link is not None:
        d["hyperlink"] = link.get("action") or link.get(R + "id")
    return d


def _theme(prs):
    out = {}
    try:
        master = prs.slide_masters[0]
        for rel in master.part.rels.values():
            if rel.reltype.endswith("/theme"):
                th = etree.fromstring(rel.target_part.blob)
                maj = th.find(f".//{A}majorFont/{A}latin")
                mnr = th.find(f".//{A}minorFont/{A}latin")
                out["major_font"] = maj.get("typeface") if maj is not None else None
                out["minor_font"] = mnr.get("typeface") if mnr is not None else None
                cs = th.find(f".//{A}clrScheme")
                if cs is not None:
                    cols = {}
                    for c in cs:
                        v = c[0]
                        cols[etree.QName(c).localname] = v.get("val") or v.get("lastClr")
                    out["colors"] = cols
    except Exception as e:
        out["error"] = str(e)
    return out


def _embedded_fonts(prs):
    el = prs.part._element.find(f"{P}embeddedFontLst")
    if el is None:
        return []
    return [{"typeface": f.find(f"{P}font").get("typeface"),
             "styles": [etree.QName(s).localname for s in f if etree.QName(s).localname != "font"]} for f in el]


def inspect_deck(path) -> dict:
    path = Path(path)
    prs = Presentation(str(path))
    sw, shh = prs.slide_width, prs.slide_height
    slides = []
    all_fonts, pics, media = Counter(), {}, []
    for i, slide in enumerate(prs.slides, 1):
        shapes = [_shape(sh, sw, shh, z) for z, sh in enumerate(slide.shapes)]

        def walk(lst):
            for s in lst:
                yield s
                yield from walk(s.get("children", []))

        for s in walk(shapes):
            for f, n in (s.get("text", {}) or {}).get("fonts", {}).items():
                all_fonts[f] += n
            if "picture" in s and "sha1" in s["picture"]:
                pics.setdefault(s["picture"]["sha1"], []).append(i)
            if s["kind"] == "media":
                media.append({"slide": i, "name": s["name"]})
        title = None
        try:
            if slide.shapes.title is not None:
                title = slide.shapes.title.text_frame.text
        except Exception:
            pass
        if not title:
            texts = [s for s in shapes if s.get("text") and s["text"]["text"].strip()]
            named = [s for s in texts if s["name"].lower().startswith(("title", "заголовок"))]
            if named:
                title = named[0]["text"]["text"].replace("\n", " ")[:80]
            elif texts:
                big = max(texts, key=lambda s: (max(s["text"]["sizes_pt"] or {0: 0}) * (len(s["text"]["text"]) > 2), -s["y"]))
                title = big["text"]["text"].replace("\n", " ")[:80]
        notes = ""
        if slide.has_notes_slide:
            notes = slide.notes_slide.notes_text_frame.text if slide.notes_slide.notes_text_frame else ""
        bg = None
        bgel = slide._element.find(f"{P}cSld/{P}bg")
        if bgel is not None:
            clr = bgel.find(f".//{A}srgbClr")
            bg = {"rgb": clr.get("val")} if clr is not None else {"custom": True}
        words = sum(s["text"]["words"] for s in walk(shapes) if s.get("text"))
        slides.append({"index": i, "id": slide.slide_id, "layout": slide.slide_layout.name, "title": title,
                       "hidden": slide._element.get("show") == "0", "background": bg, "words": words,
                       "shapes": shapes, "notes": notes, "anim": anim.summary(slide),
                       "partname": str(slide.part.partname)})
    layouts = Counter(s["layout"] for s in slides)
    theme = _theme(prs)
    for k in ("major_font", "minor_font"):
        if theme.get(k):
            all_fonts[theme[k] + " (theme)"] += 0
    return {
        "file": str(path), "kb": round(path.stat().st_size / 1024, 1),
        "slide_size": {"w": sw, "h": shh, "cm": [emu_to(sw), emu_to(shh)], "in": [emu_to(sw, 'in'), emu_to(shh, 'in')],
                       "aspect": round(sw / shh, 3)},
        "slide_count": len(slides), "layouts_used": dict(layouts),
        "masters": [m.name if hasattr(m, "name") else str(k) for k, m in enumerate(prs.slide_masters)],
        "theme": theme, "fonts_used": dict(all_fonts), "embedded_fonts": _embedded_fonts(prs),
        "images": {"unique": len(pics), "reused": {k: v for k, v in pics.items() if len(v) > 1}},
        "media": media, "core": {"title": prs.core_properties.title, "author": prs.core_properties.author,
                                 "modified": str(prs.core_properties.modified)},
        "slides": slides,
    }


def _walk(shapes):
    for s in shapes:
        yield s
        yield from _walk(s.get("children", []))


def to_markdown(info: dict, max_text: int = 160) -> str:
    L = []
    ss = info["slide_size"]
    L.append(f"# Анализ презентации: `{Path(info['file']).name}`\n")
    L.append(f"- Размер файла: **{info['kb']} KB**; слайдов: **{info['slide_count']}**; "
             f"формат: {ss['cm'][0]}×{ss['cm'][1]} см ({ss['aspect']}:1)")
    th = info.get("theme", {})
    L.append(f"- Шрифты темы: заголовки `{th.get('major_font')}`, текст `{th.get('minor_font')}`")
    L.append(f"- Использованные шрифты: " + ", ".join(f"`{k}`" for k in info["fonts_used"]) if info["fonts_used"] else "- Шрифты: только из темы")
    L.append(f"- Встроенные шрифты: " + (", ".join(f"`{f['typeface']}` ({'/'.join(f['styles'])})" for f in info['embedded_fonts']) or "нет"))
    L.append(f"- Макеты: " + ", ".join(f"{k} ×{v}" for k, v in info["layouts_used"].items()))
    L.append(f"- Уникальных картинок: {info['images']['unique']}; медиа: {len(info['media'])}\n")
    L.append("| # | Заголовок | Макет | Фигур | Слов | Переход | Анимаций |")
    L.append("|---|---|---|---|---|---|---|")
    for s in info["slides"]:
        tr = (s["anim"]["transition"] or {}).get("type", "—") if s["anim"]["transition"] else "—"
        L.append(f"| {s['index']}{' (скрыт)' if s['hidden'] else ''} | {(s['title'] or '').replace('|', '/')[:60]} | "
                 f"{s['layout']} | {len(s['shapes'])} | {s['words']} | {tr} | {len(s['anim']['effects'])} |")
    for s in info["slides"]:
        L.append(f"\n## Слайд {s['index']}: {s['title'] or '(без заголовка)'}\n")
        L.append(f"Макет `{s['layout']}` · фигур {len(s['shapes'])} · слов {s['words']}"
                 + (f" · фон {s['background']}" if s['background'] else ""))
        L.append("\n| id | имя | тип | x, y, w, h (см) | % слайда | детали |")
        L.append("|---|---|---|---|---|---|")
        for sh in _walk(s["shapes"]):
            det = []
            if sh.get("text") and sh["text"]["text"].strip():
                t = sh["text"]["text"].replace("\n", " ⏎ ").replace("|", "/")
                det.append(f"«{t[:max_text]}{'…' if len(t) > max_text else ''}»")
                if sh["text"]["sizes_pt"]:
                    det.append("pt " + "/".join(str(k) for k in sorted(sh["text"]["sizes_pt"])))
                if sh["text"]["fonts"]:
                    det.append(", ".join(sh["text"]["fonts"]))
            if sh.get("picture"):
                p = sh["picture"]
                det.append(f"🖼 {p.get('px')} {p.get('format')} {p.get('kb')}KB dpi≈{p.get('effective_dpi')}"
                           + (f" crop {p['crop']}" if any(p.get('crop', {}).values()) else ""))
            if sh.get("fill"):
                det.append(f"заливка {sh['fill']}")
            if sh["rot"]:
                det.append(f"поворот {sh['rot']}°")
            L.append(f"| {sh['id']} | {sh['name']} | {sh['kind']} | {', '.join(map(str, sh['cm']))} | "
                     f"{', '.join(map(str, sh['pct']))} | {' · '.join(det)} |")
        a = s["anim"]
        if a["transition"] or a["effects"]:
            L.append(f"\nПереход: {a['transition']}; эффектов: {len(a['effects'])}; триггеров: {a['triggers']}")
        if s["notes"].strip():
            L.append(f"\n> Заметки: {s['notes'].strip()[:500]}")
    return "\n".join(L) + "\n"


def text_dump(info: dict) -> str:
    out = []
    for s in info["slides"]:
        out.append(f"===== Слайд {s['index']} — {s['title'] or ''}")
        for sh in _walk(s["shapes"]):
            if sh.get("text") and sh["text"]["text"].strip():
                out.append(f"[{sh['id']} {sh['name']}] {sh['text']['text']}")
        if s["notes"].strip():
            out.append(f"[заметки] {s['notes']}")
        out.append("")
    return "\n".join(out)
