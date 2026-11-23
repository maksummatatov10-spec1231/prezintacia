"""Render the slide model (slides.py) to a .pptx with animations, transitions, notes and embedded fonts."""
from __future__ import annotations

import re
from pathlib import Path

from lxml import etree
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

import slides as S
from pptkit import anim, fonts
from pptkit.build import Builder, effect_list, no_line, rgb, set_alpha, set_theme

SEG = re.compile(r"\*\*(.+?)\*\*|__(.+?)__|\{\{(.+?)\}\}")
MEANDER = {"terra": "meander.png", "gold": "meander_gold.png", "white": "meander_white.png"}


def segments(text):
    """'a **b** {{Γ}}' -> [(text, bold, accent, greek)]"""
    out, pos = [], 0
    for m in SEG.finditer(text):
        if m.start() > pos:
            out.append((text[pos:m.start()], False, False, False))
        if m.group(1):
            out.append((m.group(1), True, False, False))
        elif m.group(2):
            out.append((m.group(2), True, True, False))
        else:
            out.append((m.group(3), True, False, True))
        pos = m.end()
    if pos < len(text):
        out.append((text[pos:], False, False, False))
    return out


def fill_text(b: Builder, sh, text, font=S.BODY, size=18, color=S.INK, bold=False, align="left", anchor="top",
              ls=1.0, inset=(0.04, 0.02), wrap=True, accent=S.TERRA):
    tf = sh.text_frame
    tf.word_wrap = wrap
    tf.auto_size = MSO_AUTO_SIZE.NONE
    tf.margin_left = tf.margin_right = Inches(inset[0])
    tf.margin_top = tf.margin_bottom = Inches(inset[1])
    tf.vertical_anchor = {"top": MSO_ANCHOR.TOP, "middle": MSO_ANCHOR.MIDDLE, "bottom": MSO_ANCHOR.BOTTOM}[anchor]
    for i, para in enumerate(str(text).split("\n")):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = {"left": PP_ALIGN.LEFT, "center": PP_ALIGN.CENTER, "right": PP_ALIGN.RIGHT}[align]
        p.line_spacing = ls
        for seg, sb, acc, greek in segments(para) or [("", False, False, False)]:
            r = p.add_run()
            r.text = seg
            f = r.font
            fname = S.GREEK if greek else font
            f.name = fname
            f.size = Pt(size)
            f.bold = bold or sb
            f.color.rgb = rgb(accent if acc else color)
            f.language_id = b.lang
            rpr = r._r.get_or_add_rPr()
            for tag in ("a:latin", "a:ea", "a:cs"):
                el = rpr.find(qn(tag))
                if el is None:
                    el = etree.SubElement(rpr, qn(tag))
                el.set("typeface", fname)
        end = p._p.find(qn("a:endParaRPr"))
        if end is None:
            end = etree.SubElement(p._p, qn("a:endParaRPr"))
        end.set("lang", "ru-RU")
        end.set("sz", str(int(size * 100)))
    return sh


def rotate(sh, deg):
    if deg:
        sh.rotation = float(deg)


def render(slides: list, out: Path, embed: bool = True) -> dict:
    b = Builder(fonts_dir=S.A / "fonts")
    prs = b.prs
    cp = prs.core_properties
    cp.title = "Как появилась Древняя Греция"
    cp.subject = "Презентация по истории для детей"
    cp.author = "prezintacia toolkit"
    cp.language = "ru-RU"
    cp.keywords = "Древняя Греция, история, 5 класс, Крит, Микены, Олимпийские игры"
    # theme = deck fonts + palette: new text boxes / colour pickers in PowerPoint match the design
    set_theme(prs, major="Nunito Black", minor="Nunito", name="Древняя Греция",
              colors={"dk1": "1D2433", "lt1": "FFFFFF", "dk2": "0E2A47", "lt2": "FFF4E2",
                      "accent1": "C8553D", "accent2": "F2B134", "accent3": "0E8794", "accent4": "1667A8",
                      "accent5": "6E8B3D", "accent6": "2E9E5B", "hlink": "1667A8", "folHlink": "5B6475"})
    stats = {"slides": 0, "shapes": 0, "animations": 0, "triggers": 0}
    for sm in slides:
        sl = b.slide(bg=sm.bg, notes=sm.notes)
        steps, triggers, by_id = [], {}, {}
        for el in sm.els:
            t = el["type"]
            x, y, w, h = el.get("x", 0), el.get("y", 0), el.get("w", 0), el.get("h", 0)
            sh = None
            if t == "pic":
                sh = b.picture(sl, el["src"], x, y, w, h, focus=el.get("focus", (0.5, 0.5)), radius=el.get("radius"),
                               border=el.get("border"), border_w=el.get("border_w", 4), shadow=el.get("shadow"),
                               alt=el.get("alt"), fit=el.get("fit", "cover"))
                rotate(sh, el.get("rot"))
            elif t == "rect":
                sh = b.rect(sl, x, y, w, h, fill=el.get("fill"), alpha=el.get("alpha"), radius=el.get("radius"),
                            line=el.get("line"), line_w=el.get("line_w", 1.5), shadow=el.get("shadow"),
                            gradient=el.get("gradient"), angle=el.get("angle", 0))
            elif t == "text":
                sh = sl.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
                fill_text(b, sh, el["text"], font=el.get("font", S.BODY), size=el.get("size", 18),
                          color=el.get("color", S.INK), bold=el.get("bold", False), align=el.get("align", "left"),
                          anchor=el.get("anchor", "top"), ls=el.get("ls", 1.0))
            elif t == "chip":
                if el.get("align") == "right":
                    x = x - w
                sh = b.rect(sl, x, y, w, h, fill=el["fill"], radius=h / 2)
                fill_text(b, sh, el["text"], font=el.get("font", S.XB), size=el["size"], color=el["color"],
                          align="center", anchor="middle", inset=(0.02, 0), wrap=False)
            elif t == "bubble":
                sh = sl.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGULAR_CALLOUT, Inches(x), Inches(y), Inches(w), Inches(h))
                sh.adjustments[0], sh.adjustments[1] = el["tip"]
                sh.adjustments[2] = min(0.5, 0.25 / min(w, h))
                sh.fill.solid()
                sh.fill.fore_color.rgb = rgb(S.WHITE)
                no_line(sh)
                effect_list(sh, {"blur": 0.16, "dist": 0.04, "alpha": 0.25})
                fill_text(b, sh, el["text"], size=el.get("size", 16), color=S.NAVY, anchor="middle", inset=(0.16, 0.06),
                          bold=False)
            elif t == "meander":
                src = S.A / MEANDER[el["color"]]
                from PIL import Image
                with Image.open(src) as im:
                    pw, ph = im.size
                reps_total = pw / ph
                reps = w / h
                sh = sl.shapes.add_picture(str(src), Inches(x), Inches(y), Inches(w), Inches(h))
                sh.crop_right = max(0.0, 1 - reps / reps_total)
                sh._element.nvPicPr.cNvPr.set("descr", "Греческий орнамент меандр")
            elif t in ("badge", "dot"):
                sh = b.rect(sl, x, y, w, h, fill=el["fill"], shape=MSO_SHAPE.OVAL, line=el.get("line"),
                            line_w=2.5 if el.get("line") else 1.5,
                            shadow={"blur": 0.12, "dist": 0.03, "alpha": 0.35} if el.get("shadow") else None)
                if t == "badge":
                    fill_text(b, sh, el["text"], font=S.TITLE, size=el["size"], color=el["color"], align="center",
                              anchor="middle", inset=(0, 0), wrap=False)
            elif t == "arrow":
                sh = b.rect(sl, x, y, w, h, fill=el["fill"], shape=MSO_SHAPE.ISOSCELES_TRIANGLE)
                sh.rotation = 90
            elif t == "num":
                sh = sl.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
                fill_text(b, sh, el["text"], font=S.TITLE, size=el["size"], color=el["color"], align="center",
                          anchor="middle", inset=(0, 0))
            elif t == "answer":
                sh = b.rect(sl, x, y, w, h, fill=S.WHITE, radius=h / 2, line="#E2D6C3", line_w=1.5,
                            shadow={"blur": 0.16, "dist": 0.04, "alpha": 0.18})
                fill_text(b, sh, el["text"], font=S.XB, size=24, color=S.INK, anchor="middle", inset=(0.98, 0.02))
                sh.name = f"Ответ {el['letter']}"
            else:
                raise ValueError(t)
            stats["shapes"] += 1
            if el.get("id"):
                by_id[el["id"]] = sh
            if el.get("role") and sh is not None and t not in ("answer",):
                sh.name = f"{el['role']} {sh.shape_id}"
            a = el.get("anim")
            if a:
                st = {"shape": sh, "effect": a["effect"], "start": a["start"], "delay_ms": a["delay"],
                      "dur_ms": a["dur"]}
                if a.get("direction"):
                    st["direction"] = a["direction"]
                if a["start"] == "trigger":
                    triggers.setdefault(a["trigger"], []).append(st)
                else:
                    steps.append(st)
        inter = []
        for tid, tsteps in triggers.items():
            for k, st in enumerate(tsteps):
                st["start"] = "click" if k == 0 else ("after" if st["effect"] == "fade" and k == 1 else "with")
            inter.append({"trigger": by_id[tid], "steps": tsteps})
        anim.set_transition(sl, sm.transition[0], sm.transition[1])
        if steps or inter:
            anim.animate(sl, steps, inter)
        stats["slides"] += 1
        stats["animations"] += len(steps) + sum(len(i["steps"]) for i in inter)
        stats["triggers"] += len(inter)
    if embed:
        F = S.A / "fonts"
        faces = {
            "Nunito": {"regular": F / "Nunito-Regular.ttf", "bold": F / "Nunito-Bold.ttf"},
            "Nunito ExtraBold": {"regular": F / "Nunito-ExtraBold.ttf"},
            "Nunito Black": {"regular": F / "Nunito-Black.ttf"},
            "Comfortaa": {"regular": F / "Comfortaa-Bold.ttf", "bold": F / "Comfortaa-Bold.ttf"},
        }
        stats["embedded_fonts"] = fonts.embed_fonts(prs, faces)
    out.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(out))
    stats["kb"] = round(out.stat().st_size / 1024, 1)
    return stats
