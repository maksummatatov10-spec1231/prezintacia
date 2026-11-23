"""High-level slide building helpers on top of python-pptx (inches everywhere).

    from pptkit.build import Builder
    b = Builder(fonts_dir="deck/fonts")            # 13.333×7.5 in, blank layout
    s = b.slide(bg="#FFF4E2")
    b.picture(s, "art.jpg", 0, 0, b.W, b.H, focus=(0.6, 0.5))        # object-fit: cover
    b.rect(s, 0.6, 0.6, 6, 5, fill="#FFFAF1", alpha=0.94, radius=0.25, shadow=True)
    b.text(s, 0.9, 0.9, 5.4, 1.2, "Заголовок **жирным**", font="Nunito Black", size=40, color="#0E2A47")
    b.chip(s, 0.9, 0.5, "1600 г. до н. э.", fill="#C8553D")
    b.bubble(s, 8, 5.5, 4, 1.2, "Совёнок говорит…", tail=(-0.6, 0.2))
    b.save("deck.pptx")

Text markup: **bold**, __accent__ (accent colour + bold), line breaks with \\n (new paragraph).
"""
from __future__ import annotations

import re
from pathlib import Path

from lxml import etree
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.lang import MSO_LANGUAGE_ID
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

from .imaging import cover_crop_fractions

EMU = 914400


def rgb(c) -> RGBColor:
    c = str(c).lstrip("#")
    return RGBColor.from_string(c.upper())


def _E(tag, **attrs):
    el = etree.SubElement(etree.Element("dummy"), qn(tag))
    el = etree.Element(qn(tag))
    for k, v in attrs.items():
        el.set(k, str(v))
    return el


def _spPr(shape):
    return shape._element.spPr


def set_alpha(shape, alpha: float):
    """Fill opacity 0..1 for a solid fill."""
    srgb = _spPr(shape).find(qn("a:solidFill") + "/" + qn("a:srgbClr"))
    if srgb is not None:
        for a in srgb.findall(qn("a:alpha")):
            srgb.remove(a)
        a = etree.SubElement(srgb, qn("a:alpha"))
        a.set("val", str(int(alpha * 100000)))


def no_line(shape):
    shape.line.fill.background()


def effect_list(shape, shadow: dict | None = None):
    """Explicit effect list (overrides theme effects). shadow=dict(blur=0.18, dist=0.05, alpha=0.3, color='000000')"""
    sp = _spPr(shape)
    for e in sp.findall(qn("a:effectLst")):
        sp.remove(e)
    el = etree.Element(qn("a:effectLst"))
    if shadow:
        sh = etree.SubElement(el, qn("a:outerShdw"))
        sh.set("blurRad", str(int(shadow.get("blur", 0.18) * EMU)))
        sh.set("dist", str(int(shadow.get("dist", 0.05) * EMU)))
        sh.set("dir", str(int(shadow.get("dir", 90) * 60000)))
        sh.set("algn", "t")
        sh.set("rotWithShape", "0")
        c = etree.SubElement(sh, qn("a:srgbClr"))
        c.set("val", shadow.get("color", "000000"))
        a = etree.SubElement(c, qn("a:alpha"))
        a.set("val", str(int(shadow.get("alpha", 0.3) * 100000)))
    # schema order inside spPr: xfrm, geom, fill, ln, effectLst, ...
    ln = sp.find(qn("a:ln"))
    if ln is not None:
        ln.addnext(el)
    else:
        fills = [sp.find(qn(t)) for t in ("a:solidFill", "a:gradFill", "a:noFill", "a:blipFill", "a:pattFill")]
        fills = [f for f in fills if f is not None]
        if fills:
            fills[-1].addnext(el)
        else:
            geom = sp.find(qn("a:prstGeom"))
            if geom is None:
                geom = sp.find(qn("a:custGeom"))
            (geom if geom is not None else sp.find(qn("a:xfrm"))).addnext(el)
    return el


def gradient_fill(shape, stops: list[tuple[float, str, float]], angle: float = 0):
    """stops: [(pos 0..1, '#RRGGBB', alpha 0..1)], angle in degrees (0 = left→right, 90 = top→bottom)."""
    sp = _spPr(shape)
    for t in ("a:solidFill", "a:gradFill", "a:noFill", "a:blipFill", "a:pattFill"):
        for e in sp.findall(qn(t)):
            sp.remove(e)
    g = etree.Element(qn("a:gradFill"))
    g.set("rotWithShape", "1")
    lst = etree.SubElement(g, qn("a:gsLst"))
    for pos, col, alpha in stops:
        gs = etree.SubElement(lst, qn("a:gs"))
        gs.set("pos", str(int(pos * 100000)))
        c = etree.SubElement(gs, qn("a:srgbClr"))
        c.set("val", col.lstrip("#").upper())
        if alpha < 1:
            a = etree.SubElement(c, qn("a:alpha"))
            a.set("val", str(int(alpha * 100000)))
    lin = etree.SubElement(g, qn("a:lin"))
    lin.set("ang", str(int(angle * 60000)))
    lin.set("scaled", "0")
    geom = sp.find(qn("a:prstGeom"))
    geom.addnext(g)


def round_picture(pic, radius_in: float):
    geom = _spPr(pic).find(qn("a:prstGeom"))
    geom.set("prst", "roundRect")
    av = geom.find(qn("a:avLst"))
    if av is None:
        av = etree.SubElement(geom, qn("a:avLst"))
    for g in list(av):
        av.remove(g)
    gd = etree.SubElement(av, qn("a:gd"))
    short = min(pic.width, pic.height) / EMU
    gd.set("name", "adj")
    gd.set("fmla", f"val {int(min(50000, radius_in / short * 100000))}")


_MARK = re.compile(r"(\*\*.+?\*\*|__.+?__)")


class Builder:
    def __init__(self, width_in: float = 13.333, height_in: float = 7.5, template: str | None = None,
                 fonts_dir: str | Path | None = None, lang=MSO_LANGUAGE_ID.RUSSIAN, accent: str = "#C8553D"):
        self.prs = Presentation(template) if template else Presentation()
        if not template:
            self.prs.slide_width = Emu(int(width_in * EMU))
            self.prs.slide_height = Emu(int(height_in * EMU))
        self.W = self.prs.slide_width / EMU
        self.H = self.prs.slide_height / EMU
        self.blank = self.prs.slide_layouts[6]
        self.lang = lang
        self.accent = accent
        self.fonts_dir = Path(fonts_dir) if fonts_dir else None

    # ------------------------------------------------------------------ slides
    def slide(self, bg: str | None = None, notes: str | None = None):
        s = self.prs.slides.add_slide(self.blank)
        if bg:
            f = s.background.fill
            f.solid()
            f.fore_color.rgb = rgb(bg)
        if notes:
            s.notes_slide.notes_text_frame.text = notes
        return s

    # ------------------------------------------------------------------ shapes
    def rect(self, s, x, y, w, h, fill=None, alpha: float | None = None, radius: float | None = None, line=None,
             line_w: float = 1.5, shadow=None, name=None, shape=None, gradient=None, angle=0):
        kind = shape or (MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE)
        sh = s.shapes.add_shape(kind, Inches(x), Inches(y), Inches(w), Inches(h))
        if radius and kind == MSO_SHAPE.ROUNDED_RECTANGLE:
            sh.adjustments[0] = min(0.5, radius / min(w, h))
        if gradient:
            gradient_fill(sh, gradient, angle)
        elif fill:
            sh.fill.solid()
            sh.fill.fore_color.rgb = rgb(fill)
            if alpha is not None and alpha < 1:
                set_alpha(sh, alpha)
        else:
            sh.fill.background()
        if line:
            sh.line.color.rgb = rgb(line)
            sh.line.width = Pt(line_w)
        else:
            no_line(sh)
        effect_list(sh, shadow if isinstance(shadow, dict) else ({} if shadow else None))
        if name:
            sh.name = name
        # remove the theme text style colour (white) for safety
        return sh

    def ellipse(self, s, x, y, d, fill, line=None, line_w=2, shadow=None, name=None):
        return self.rect(s, x, y, d, d, fill=fill, shape=MSO_SHAPE.OVAL, line=line, line_w=line_w, shadow=shadow,
                         name=name)

    def picture(self, s, path, x, y, w, h, focus=(0.5, 0.5), zoom: float = 1.0, radius: float | None = None,
                border: str | None = None, border_w: float = 4, shadow=None, name=None, alt: str | None = None,
                fit: str = "cover"):
        from PIL import Image
        with Image.open(path) as im:
            pw, ph = im.size
        if fit == "contain":
            ar = pw / ph
            if w / h > ar:
                nw = h * ar
                x, w = x + (w - nw) / 2, nw
            else:
                nh = w / ar
                y, h = y + (h - nh) / 2, nh
        pic = s.shapes.add_picture(str(path), Inches(x), Inches(y), Inches(w), Inches(h))
        if fit == "cover":
            l, t, r, b = cover_crop_fractions(pw, ph, w, h, focus, zoom)
            pic.crop_left, pic.crop_top, pic.crop_right, pic.crop_bottom = l, t, r, b
        if radius:
            round_picture(pic, radius)
        if border:
            pic.line.color.rgb = rgb(border)
            pic.line.width = Pt(border_w)
        if shadow:
            effect_list(pic, shadow if isinstance(shadow, dict) else {})
        if name:
            pic.name = name
        if alt:
            pic._element.nvPicPr.cNvPr.set("descr", alt)
        return pic

    # ------------------------------------------------------------------ text
    def _runs(self, p, text, font, size, color, bold, accent, italic=False):
        parts = _MARK.split(text)
        for part in parts:
            if not part:
                continue
            r = p.add_run()
            b, col = bold, color
            if part.startswith("**") and part.endswith("**"):
                part, b = part[2:-2], True
            elif part.startswith("__") and part.endswith("__"):
                part, b, col = part[2:-2], True, accent or self.accent
            r.text = part
            f = r.font
            f.name = font
            f.size = Pt(size)
            f.bold = b
            f.italic = italic
            f.color.rgb = rgb(col)
            f.language_id = self.lang
            rpr = r._r.get_or_add_rPr()
            for tag in ("a:latin", "a:ea", "a:cs"):
                el = rpr.find(qn(tag))
                if el is None:
                    el = etree.SubElement(rpr, qn(tag))
                el.set("typeface", font)
        return p

    def text(self, s, x, y, w, h, text, font="Nunito", size=20, color="#1D2433", bold=False, align="left",
             anchor="top", line_spacing: float = 1.0, space_after: float = 0, accent: str | None = None,
             italic=False, name=None, inset=(0.04, 0.02), shape=None, wrap=True):
        """Text box. `text` may be a str (\\n = new paragraph) or a list of paragraphs, each either a str
        or a dict(text=..., size=, font=, color=, bold=, align=, space_after=)."""
        if shape is not None:
            sh = shape
        else:
            sh = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
        tf = sh.text_frame
        tf.word_wrap = wrap
        tf.auto_size = MSO_AUTO_SIZE.NONE
        tf.margin_left = tf.margin_right = Inches(inset[0])
        tf.margin_top = tf.margin_bottom = Inches(inset[1])
        tf.vertical_anchor = {"top": MSO_ANCHOR.TOP, "middle": MSO_ANCHOR.MIDDLE, "bottom": MSO_ANCHOR.BOTTOM}[anchor]
        paras = text if isinstance(text, list) else str(text).split("\n")
        first = True
        for para in paras:
            spec = para if isinstance(para, dict) else {"text": para}
            p = tf.paragraphs[0] if first else tf.add_paragraph()
            first = False
            p.alignment = {"left": PP_ALIGN.LEFT, "center": PP_ALIGN.CENTER, "right": PP_ALIGN.RIGHT,
                           "justify": PP_ALIGN.JUSTIFY}[spec.get("align", align)]
            p.line_spacing = spec.get("line_spacing", line_spacing)
            sa = spec.get("space_after", space_after)
            if sa:
                p.space_after = Pt(sa)
            self._runs(p, spec["text"], spec.get("font", font), spec.get("size", size), spec.get("color", color),
                       spec.get("bold", bold), spec.get("accent", accent), spec.get("italic", italic))
            # end paragraph props so empty lines keep size
            end = p._p.find(qn("a:endParaRPr"))
            if end is None:
                end = etree.SubElement(p._p, qn("a:endParaRPr"))
            end.set("lang", "ru-RU")
            end.set("sz", str(int(spec.get("size", size) * 100)))
        if name:
            sh.name = name
        return sh

    def measure(self, text: str, size: float, width_in: float, font: str = "Nunito", bold: bool = False,
                line_spacing: float = 1.0, inset=(0.04, 0.02), space_after: float = 0) -> float:
        """Estimated height (in) of wrapped text — uses the real font metrics."""
        from .lint import estimate_text_height
        clean = _MARK.sub(lambda m: m.group(0)[2:-2], text)
        paras = clean.split("\n")
        h = estimate_text_height([(p, size, font, bold) for p in paras], int((width_in - 2 * inset[0]) * EMU),
                                 line_spacing)
        return h / EMU + 2 * inset[1] + space_after / 72 * max(0, len(paras) - 1)

    def text_width(self, text: str, size: float, font: str = "Nunito", bold: bool = False) -> float:
        from .lint import _font_path, _pil_font
        clean = _MARK.sub(lambda m: m.group(0)[2:-2], text)
        f = _pil_font(_font_path(font, bold), int(size * 4))
        return f.getlength(clean) / 4 / 72

    def chip(self, s, x, y, text, fill="#C8553D", color="#FFFFFF", size=15, font="Nunito ExtraBold", h=None,
             pad=0.18, align="left", name=None, shadow=None, alpha=None):
        w = self.text_width(text, size, font) + 2 * pad + 0.04
        h = h or size / 72 * 1.75
        if align == "right":
            x = x - w
        elif align == "center":
            x = x - w / 2
        sh = self.rect(s, x, y, w, h, fill=fill, radius=h / 2, shadow=shadow, name=name, alpha=alpha)
        self.text(s, 0, 0, 0, 0, text, font=font, size=size, color=color, align="center", anchor="middle",
                  inset=(0.02, 0), shape=sh, wrap=False)
        return sh

    def bubble(self, s, x, y, w, h, text, tail=(-0.62, 0.25), fill="#FFFFFF", color="#0E2A47", size=16,
               font="Nunito", bold=False, shadow=True, name=None, line=None):
        sh = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGULAR_CALLOUT, Inches(x), Inches(y), Inches(w), Inches(h))
        sh.adjustments[0] = tail[0]
        sh.adjustments[1] = tail[1]
        sh.adjustments[2] = min(0.5, 0.22 / min(w, h)) if len(sh.adjustments) > 2 else None
        sh.fill.solid()
        sh.fill.fore_color.rgb = rgb(fill)
        if line:
            sh.line.color.rgb = rgb(line)
            sh.line.width = Pt(2)
        else:
            no_line(sh)
        effect_list(sh, {"blur": 0.14, "dist": 0.04, "alpha": 0.22} if shadow else None)
        self.text(s, 0, 0, 0, 0, text, font=font, size=size, color=color, bold=bold, anchor="middle",
                  inset=(0.16, 0.08), shape=sh, line_spacing=1.0)
        if name:
            sh.name = name
        return sh

    def save(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.prs.save(str(path))
        return path


def set_theme(prs, major: str | None = None, minor: str | None = None, colors: dict | None = None, name: str | None = None):
    """Theme fonts (headings/body) and colour scheme — what PowerPoint offers by default when the user adds new text
    or picks colours. colors keys: dk1 lt1 dk2 lt2 accent1..accent6 hlink folHlink (hex 'RRGGBB')."""
    from lxml import etree
    from pptx.opc.constants import RELATIONSHIP_TYPE as RT
    ns = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
    master = prs.slide_masters[0]
    theme_part = master.part.part_related_by(RT.THEME)
    root = etree.fromstring(theme_part.blob)
    if name:
        root.set("name", name)
    for tag, face in (("majorFont", major), ("minorFont", minor)):
        if face:
            el = root.find(f".//a:fontScheme/a:{tag}/a:latin", ns)
            if el is not None:
                el.set("typeface", face)
                for k in ("panose", "pitchFamily", "charset"):
                    el.attrib.pop(k, None)
            cs = root.find(f".//a:fontScheme/a:{tag}/a:cs", ns)
    for key, hexv in (colors or {}).items():
        slot = root.find(f".//a:clrScheme/a:{key}", ns)
        if slot is None:
            continue
        for ch in list(slot):
            slot.remove(ch)
        etree.SubElement(slot, f"{{{ns['a']}}}srgbClr", val=hexv.lstrip("#").upper())
    theme_part._blob = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
