"""Instant, precise edits of an existing .pptx — every operation is one call (or one JSON/YAML op).

    d = Deck("deck.pptx")
    d.move(3, "Picture 4", x="2cm", y="10%")          # absolute (cm/in/pt/px/% of slide)
    d.move(3, "id:7", dx="-5mm")                         # relative nudge
    d.resize(3, "Title 1", w="60%", keep_aspect=False)
    d.scale(3, "Picture 4", 1.2, anchor="center")
    d.crop(3, "Picture 4", left=0.1, right=0.05)        # fractions of the original image
    d.zoom(3, "Picture 4", 1.5, focus=(0.3, 0.4))       # zoom INSIDE the frame (frame unchanged)
    d.fit(3, "Picture 4", "cover")                      # fill frame without distortion
    d.replace_text("Привет", "Здравствуйте")            # keeps formatting, all slides
    d.font(2, "text:Итоги", size=40, bold=True, color="#1F4E79")
    d.align(4, ["Picture 2", "Picture 3"], "top")
    d.save("deck_fixed.pptx")

Shape selectors: 7 / "id:7" | "Name" | "name:Name" | "text:фрагмент" | "idx:0" (z-order) | "title"
| "picture:1" (first picture) | "*" (all shapes).
"""
from __future__ import annotations

import copy
import json
import re
import time
from pathlib import Path

from lxml import etree
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Emu, Pt

from .imaging import cover_crop_fractions
from .units import fmt_emu, to_emu

A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


class EditError(ValueError):
    pass


def _rgb(c) -> RGBColor:
    if isinstance(c, RGBColor):
        return c
    c = str(c).lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    return RGBColor.from_string(c.upper())


class Deck:
    def __init__(self, path):
        self.path = Path(path)
        self.prs = Presentation(str(self.path))
        self.log: list[dict] = []
        self.touched: set[int] = set()

    # ------------------------------------------------------------------ lookup
    @property
    def W(self):
        return self.prs.slide_width

    @property
    def H(self):
        return self.prs.slide_height

    def slide(self, n: int):
        n = int(n)
        if not 1 <= n <= len(self.prs.slides):
            raise EditError(f"Слайда {n} нет (всего {len(self.prs.slides)})")
        return self.prs.slides[n - 1]

    def shapes(self, n: int, sel) -> list:
        sl = self.slide(n)
        shapes = list(sl.shapes)

        def walk(lst):
            for s in lst:
                yield s
                if s.shape_type == MSO_SHAPE_TYPE.GROUP:
                    yield from walk(s.shapes)

        allsh = list(walk(shapes))
        if sel == "*":
            return shapes
        if isinstance(sel, int) or (isinstance(sel, str) and sel.isdigit()):
            sel = f"id:{sel}"
        sel = str(sel).strip()
        known = ("id", "name", "text", "idx", "picture", "title", "type")
        kind, _, val = sel.partition(":") if sel.split(":", 1)[0] in known and ":" in sel else ("name", "", sel)

        def by_name(v):
            v0 = v.lower()
            return ([s for s in allsh if s.name == v] or [s for s in allsh if s.name.lower() == v0]
                    or [s for s in allsh if s.name.lower().startswith(v0)]
                    or [s for s in allsh if v0 in s.name.lower()])

        if sel == "title" or kind == "title":
            res = [sl.shapes.title] if sl.shapes.title is not None else by_name("title")
        elif kind == "id":
            res = [s for s in allsh if s.shape_id == int(val)]
        elif kind == "name":
            res = by_name(val)
        elif kind == "text":
            res = [s for s in allsh if s.has_text_frame and val.lower() in s.text_frame.text.lower()]
        elif kind == "idx":
            res = [shapes[int(val)]] if -len(shapes) <= int(val) < len(shapes) else []
        elif kind == "picture":
            pics = [s for s in allsh if s.shape_type == MSO_SHAPE_TYPE.PICTURE]
            k = int(val or 1)
            res = [pics[k - 1]] if 1 <= k <= len(pics) else []
        elif kind == "type":
            res = [s for s in allsh if str(s.shape_type).lower().find(val.lower()) >= 0]
        else:
            res = by_name(sel)
        if not res:
            names = ", ".join(f"{s.shape_id}:{s.name}" for s in allsh)
            raise EditError(f"Слайд {n}: фигура {sel!r} не найдена. Есть: {names}")
        return res

    def shape(self, n: int, sel):
        return self.shapes(n, sel)[0]

    def _rec(self, op, n, sh=None, **kw):
        self.touched.add(int(n)) if n else None
        rec = {"op": op, "slide": n, **({"shape": f"{sh.shape_id}:{sh.name}"} if sh is not None else {}), **kw}
        self.log.append(rec)
        return rec

    @staticmethod
    def _box(sh):
        return {"x": fmt_emu(sh.left), "y": fmt_emu(sh.top), "w": fmt_emu(sh.width), "h": fmt_emu(sh.height)}

    # ------------------------------------------------------------------ geometry
    def move(self, n, sel, x=None, y=None, dx=None, dy=None, cx=None, cy=None):
        """Absolute x/y (top-left), or centre cx/cy, or relative dx/dy. Units: cm/in/pt/px/%/emu."""
        for sh in self.shapes(n, sel):
            before = self._box(sh)
            if x is not None:
                sh.left = to_emu(x, self.W)
            if y is not None:
                sh.top = to_emu(y, self.H)
            if cx is not None:
                sh.left = to_emu(cx, self.W) - sh.width // 2
            if cy is not None:
                sh.top = to_emu(cy, self.H) - sh.height // 2
            if dx is not None:
                sh.left = sh.left + to_emu(dx, self.W)
            if dy is not None:
                sh.top = sh.top + to_emu(dy, self.H)
            self._rec("move", n, sh, before=before, after=self._box(sh))
        return self

    def resize(self, n, sel, w=None, h=None, keep_aspect: bool = False, anchor: str = "topleft"):
        """Set width and/or height. keep_aspect scales the other side; anchor: topleft|center|..."""
        for sh in self.shapes(n, sel):
            before = self._box(sh)
            ow, oh = sh.width, sh.height
            nw = to_emu(w, self.W) if w is not None else None
            nh = to_emu(h, self.H) if h is not None else None
            if keep_aspect:
                if nw and not nh:
                    nh = int(oh * nw / ow)
                elif nh and not nw:
                    nw = int(ow * nh / oh)
            nw, nh = nw or ow, nh or oh
            self._apply_size(sh, nw, nh, anchor)
            self._rec("resize", n, sh, before=before, after=self._box(sh))
        return self

    def scale(self, n, sel, factor: float, anchor: str = "center"):
        for sh in self.shapes(n, sel):
            before = self._box(sh)
            self._apply_size(sh, int(sh.width * factor), int(sh.height * factor), anchor)
            self._rec("scale", n, sh, factor=factor, before=before, after=self._box(sh))
        return self

    @staticmethod
    def _apply_size(sh, nw, nh, anchor):
        ow, oh, ox, oy = sh.width, sh.height, sh.left, sh.top
        fx = {"left": 0, "center": 0.5, "right": 1}
        a = anchor.lower()
        ax = 0.5 if "center" in a and not any(k in a for k in ("left", "right")) else (1 if "right" in a else 0)
        ay = 0.5 if "center" in a or a in ("middle",) else (1 if "bottom" in a else 0)
        if a == "center":
            ax = ay = 0.5
        sh.width, sh.height = int(nw), int(nh)
        sh.left = int(ox + (ow - nw) * ax)
        sh.top = int(oy + (oh - nh) * ay)

    def set_box(self, n, sel, x=None, y=None, w=None, h=None):
        for sh in self.shapes(n, sel):
            before = self._box(sh)
            if x is not None:
                sh.left = to_emu(x, self.W)
            if y is not None:
                sh.top = to_emu(y, self.H)
            if w is not None:
                sh.width = to_emu(w, self.W)
            if h is not None:
                sh.height = to_emu(h, self.H)
            self._rec("set_box", n, sh, before=before, after=self._box(sh))
        return self

    def rotate(self, n, sel, deg: float):
        for sh in self.shapes(n, sel):
            sh.rotation = float(deg)
            self._rec("rotate", n, sh, deg=deg)
        return self

    def align(self, n, sels, how: str, to: str = "selection"):
        """how: left|center|right|top|middle|bottom; to: selection|slide."""
        shs = [s for sel in (sels if isinstance(sels, (list, tuple)) else [sels]) for s in self.shapes(n, sel)]
        if to == "slide":
            L, T, Rr, B = 0, 0, self.W, self.H
        else:
            L = min(s.left for s in shs)
            T = min(s.top for s in shs)
            Rr = max(s.left + s.width for s in shs)
            B = max(s.top + s.height for s in shs)
        for s in shs:
            if how == "left":
                s.left = L
            elif how == "right":
                s.left = Rr - s.width
            elif how == "center":
                s.left = (L + Rr) // 2 - s.width // 2
            elif how == "top":
                s.top = T
            elif how == "bottom":
                s.top = B - s.height
            elif how == "middle":
                s.top = (T + B) // 2 - s.height // 2
            else:
                raise EditError("align: left|center|right|top|middle|bottom")
        self._rec("align", n, None, how=how, to=to, shapes=[s.name for s in shs])
        return self

    def distribute(self, n, sels, axis: str = "h"):
        shs = [s for sel in sels for s in self.shapes(n, sel)]
        if len(shs) < 3:
            return self
        key = (lambda s: s.left) if axis == "h" else (lambda s: s.top)
        shs.sort(key=key)
        if axis == "h":
            total = sum(s.width for s in shs)
            span = shs[-1].left + shs[-1].width - shs[0].left
            gap = (span - total) / (len(shs) - 1)
            x = shs[0].left
            for s in shs:
                s.left = int(x)
                x += s.width + gap
        else:
            total = sum(s.height for s in shs)
            span = shs[-1].top + shs[-1].height - shs[0].top
            gap = (span - total) / (len(shs) - 1)
            y = shs[0].top
            for s in shs:
                s.top = int(y)
                y += s.height + gap
        self._rec("distribute", n, None, axis=axis, shapes=[s.name for s in shs])
        return self

    def z(self, n, sel, where: str = "front"):
        """front|back|forward|backward"""
        for sh in self.shapes(n, sel):
            el = sh._element
            tree = el.getparent()
            items = [c for c in tree if etree.QName(c).localname in ("sp", "pic", "grpSp", "graphicFrame", "cxnSp")]
            i = items.index(el)
            if where == "front":
                items[-1].addnext(el)
            elif where == "back":
                items[0].addprevious(el)
            elif where == "forward" and i < len(items) - 1:
                items[i + 1].addnext(el)
            elif where == "backward" and i > 0:
                items[i - 1].addprevious(el)
            self._rec("z", n, sh, where=where)
        return self

    def delete(self, n, sel):
        for sh in self.shapes(n, sel):
            sh._element.getparent().remove(sh._element)
            self._rec("delete", n, sh)
        return self

    def duplicate_shape(self, n, sel, dx="0.5cm", dy="0.5cm"):
        sh = self.shape(n, sel)
        el = copy.deepcopy(sh._element)
        sh._element.addnext(el)
        new = self.slide(n).shapes[-1]
        for s in self.slide(n).shapes:
            if s._element is el:
                new = s
        ids = [s.shape_id for s in self.slide(n).shapes]
        el.find(".//" + P + "cNvPr").set("id", str(max(ids) + 1))
        new.left += to_emu(dx, self.W)
        new.top += to_emu(dy, self.H)
        self._rec("duplicate_shape", n, sh, new_id=max(ids) + 1)
        return new

    # ------------------------------------------------------------------ pictures
    def _pic(self, n, sel):
        sh = self.shape(n, sel)
        if not hasattr(sh, "crop_left"):
            raise EditError(f"Фигура {sh.name} — не картинка")
        return sh

    def _img_px(self, sh):
        from PIL import Image
        import io
        with Image.open(io.BytesIO(sh.image.blob)) as im:
            return im.size

    def crop(self, n, sel, left=None, top=None, right=None, bottom=None, keep_frame: bool = True):
        """Crop fractions (0..1) or percents ('10%') of the ORIGINAL image on each side."""
        def frac(v):
            if v is None:
                return None
            s = str(v)
            return float(s[:-1]) / 100 if s.endswith("%") else float(v)
        sh = self._pic(n, sel)
        before = {k: round(getattr(sh, f"crop_{k}"), 4) for k in ("left", "top", "right", "bottom")}
        for k, v in (("left", left), ("top", top), ("right", right), ("bottom", bottom)):
            if v is not None:
                setattr(sh, f"crop_{k}", frac(v))
        if not keep_frame:  # shrink the frame so the picture is not stretched
            pass
        self._rec("crop", n, sh, before=before,
                  after={k: round(getattr(sh, f"crop_{k}"), 4) for k in ("left", "top", "right", "bottom")})
        return self

    def fit(self, n, sel, mode: str = "cover", focus=(0.5, 0.5), zoom: float = 1.0):
        """cover = fill the frame (crop overflow, no distortion); contain = whole image visible
        (frame shrinks to the image aspect, centred in the old frame)."""
        sh = self._pic(n, sel)
        pw, ph = self._img_px(sh)
        if mode == "cover":
            l, t, r, b = cover_crop_fractions(pw, ph, sh.width, sh.height, tuple(focus), zoom)
            sh.crop_left, sh.crop_top, sh.crop_right, sh.crop_bottom = l, t, r, b
        elif mode == "contain":
            sh.crop_left = sh.crop_top = sh.crop_right = sh.crop_bottom = 0
            fw, fh = sh.width, sh.height
            ar = pw / ph
            if fw / fh > ar:
                nw, nh = int(fh * ar), fh
            else:
                nw, nh = fw, int(fw / ar)
            self._apply_size(sh, nw, nh, "center")
        else:
            raise EditError("fit mode: cover|contain")
        self._rec("fit", n, sh, mode=mode, focus=list(focus), zoom=zoom)
        return self

    def zoom(self, n, sel, factor: float, focus=None):
        """Zoom inside the frame (like the PowerPoint crop handle): factor>1 zooms in, <1 out
        (zoom out never goes below 'cover'). focus=(fx, fy) in 0..1 of the image; default keeps centre."""
        sh = self._pic(n, sel)
        pw, ph = self._img_px(sh)
        l, t, r, b = sh.crop_left, sh.crop_top, sh.crop_right, sh.crop_bottom
        vis_w, vis_h = 1 - l - r, 1 - t - b
        if focus is None:
            focus = (l + vis_w / 2, t + vis_h / 2)
        # current zoom relative to 'cover'
        cl, ct, cr, cb = cover_crop_fractions(pw, ph, sh.width, sh.height, (0.5, 0.5), 1.0)
        cover_w = 1 - cl - cr
        cur_zoom = cover_w / vis_w if vis_w else 1
        new_zoom = max(1.0, cur_zoom * float(factor))
        nl, nt, nr, nb = cover_crop_fractions(pw, ph, sh.width, sh.height, tuple(focus), new_zoom)
        sh.crop_left, sh.crop_top, sh.crop_right, sh.crop_bottom = nl, nt, nr, nb
        self._rec("zoom", n, sh, factor=factor, zoom=round(new_zoom, 3), focus=[round(f, 3) for f in focus])
        return self

    def pan(self, n, sel, fx=None, fy=None):
        """Move the visible window of a cropped picture to focus (fx, fy) without changing zoom."""
        sh = self._pic(n, sel)
        l, t, r, b = sh.crop_left, sh.crop_top, sh.crop_right, sh.crop_bottom
        vw, vh = 1 - l - r, 1 - t - b
        cx = fx if fx is not None else l + vw / 2
        cy = fy if fy is not None else t + vh / 2
        nl = min(max(cx - vw / 2, 0), 1 - vw)
        nt = min(max(cy - vh / 2, 0), 1 - vh)
        sh.crop_left, sh.crop_right = nl, 1 - vw - nl
        sh.crop_top, sh.crop_bottom = nt, 1 - vh - nt
        self._rec("pan", n, sh, focus=[round(cx, 3), round(cy, 3)])
        return self

    def replace_image(self, n, sel, image_path, mode: str = "cover", focus=(0.5, 0.5)):
        """Swap the picture inside an existing frame (keeps position, size, animations)."""
        sh = self._pic(n, sel)
        sl = self.slide(n)
        image_part, rId = sl.part.get_or_add_image_part(str(image_path))
        blip = sh._element.find(".//" + A + "blip")
        blip.set(R + "embed", rId)
        sh.crop_left = sh.crop_top = sh.crop_right = sh.crop_bottom = 0
        self._rec("replace_image", n, sh, image=str(image_path))
        if mode:
            self.fit(n, f"id:{sh.shape_id}", mode, focus)
        return self

    def add_image(self, n, image_path, x="0", y="0", w=None, h=None, name=None, mode="cover", focus=(0.5, 0.5)):
        sl = self.slide(n)
        kw = {}
        if w is not None:
            kw["width"] = to_emu(w, self.W)
        if h is not None:
            kw["height"] = to_emu(h, self.H)
        pic = sl.shapes.add_picture(str(image_path), to_emu(x, self.W), to_emu(y, self.H), **kw)
        if name:
            pic.name = name
        self._rec("add_image", n, pic, image=str(image_path), box=self._box(pic))
        if w is not None and h is not None and mode:
            self.fit(n, f"id:{pic.shape_id}", mode, focus)
        return pic

    # ------------------------------------------------------------------ text
    def replace_text(self, old: str, new: str, slides=None, regex: bool = False, notes: bool = False) -> int:
        """Replace text everywhere (or on `slides`), preserving run formatting, also when the match
        spans several runs. Returns the number of replacements."""
        count = 0
        idx = slides or range(1, len(self.prs.slides) + 1)
        pat = re.compile(old if regex else re.escape(old))
        for n in idx:
            sl = self.slide(n)
            frames = []
            for sh in sl.shapes:
                frames += self._frames(sh)
            if notes and sl.has_notes_slide:
                frames.append(sl.notes_slide.notes_text_frame)
            for tf in frames:
                for p in tf.paragraphs:
                    c = self._replace_in_paragraph(p, pat, new)
                    if c:
                        count += c
                        self.touched.add(n)
        self._rec("replace_text", None, None, old=old, new=new, count=count)
        return count

    def _frames(self, sh):
        out = []
        if sh.shape_type == MSO_SHAPE_TYPE.GROUP:
            for c in sh.shapes:
                out += self._frames(c)
        elif sh.has_text_frame:
            out.append(sh.text_frame)
        elif getattr(sh, "has_table", False) and sh.has_table:
            for row in sh.table.rows:
                for cell in row.cells:
                    out.append(cell.text_frame)
        return out

    @staticmethod
    def _replace_in_paragraph(p, pat, new) -> int:
        runs = p.runs
        if not runs:
            return 0
        full = "".join(r.text for r in runs)
        matches = list(pat.finditer(full))
        if not matches:
            return 0
        # map char offsets -> run index
        bounds, pos = [], 0
        for r in runs:
            bounds.append((pos, pos + len(r.text)))
            pos += len(r.text)
        for m in reversed(matches):
            s, e = m.span()
            rep = m.expand(new) if pat.groups else new
            first = next(i for i, (a, b) in enumerate(bounds) if a <= s < b or (s == b and i == len(bounds) - 1))
            last = next(i for i, (a, b) in enumerate(bounds) if a < e <= b) if e > s else first
            for i in range(first, last + 1):
                a, b = bounds[i]
                t = runs[i].text
                ls, le = max(s, a) - a, min(e, b) - a
                if i == first:
                    runs[i].text = t[:ls] + rep + (t[le:] if i == last else "")
                elif i == last:
                    runs[i].text = t[le:]
                else:
                    runs[i].text = ""
            pos = 0
            bounds = []
            for r in runs:
                bounds.append((pos, pos + len(r.text)))
                pos += len(r.text)
        return len(matches)

    def set_text(self, n, sel, text: str, keep_format: bool = True):
        """Replace the whole text of a shape. Lines separated by \\n become paragraphs; formatting
        of the first run of each existing paragraph is reused."""
        sh = self.shape(n, sel)
        tf = sh.text_frame
        lines = str(text).split("\n")
        paras = list(tf.paragraphs)
        tmpl_p = [copy.deepcopy(p._p) for p in paras]
        txBody = tf._txBody
        for p in paras:
            txBody.remove(p._p)
        for i, line in enumerate(lines):
            src = tmpl_p[min(i, len(tmpl_p) - 1)] if tmpl_p else None
            if src is not None and keep_format:
                newp = copy.deepcopy(src)
                rs = newp.findall(A + "r")
                for extra in rs[1:]:
                    newp.remove(extra)
                for br in newp.findall(A + "br"):
                    newp.remove(br)
                for fld in newp.findall(A + "fld"):
                    newp.remove(fld)
                if rs:
                    rs[0].find(A + "t").text = line
                else:
                    r = etree.SubElement(newp, A + "r")
                    etree.SubElement(r, A + "t").text = line
                    end = newp.find(A + "endParaRPr")
                    if end is not None:
                        newp.remove(end)
                        newp.append(end)
                txBody.append(newp)
            else:
                p = etree.SubElement(txBody, A + "p")
                r = etree.SubElement(p, A + "r")
                etree.SubElement(r, A + "t").text = line
        self._rec("set_text", n, sh, text=text[:120])
        return self

    def font(self, n, sel, size=None, bold=None, italic=None, color=None, name=None, align=None,
             line_spacing=None, autofit=None):
        """Format all runs of the shape(s). align: left|center|right|justify;
        autofit: none|shrink|resize."""
        for sh in self.shapes(n, sel):
            if not sh.has_text_frame:
                continue
            tf = sh.text_frame
            for p in tf.paragraphs:
                if align:
                    p.alignment = {"left": PP_ALIGN.LEFT, "center": PP_ALIGN.CENTER, "right": PP_ALIGN.RIGHT,
                                   "justify": PP_ALIGN.JUSTIFY}[align]
                if line_spacing:
                    p.line_spacing = float(line_spacing)
                runs = p.runs or []
                for r in runs:
                    f = r.font
                    if size:
                        f.size = Pt(float(size))
                    if bold is not None:
                        f.bold = bool(bold)
                    if italic is not None:
                        f.italic = bool(italic)
                    if color:
                        f.color.rgb = _rgb(color)
                    if name:
                        f.name = name
                        rpr = r._r.get_or_add_rPr()
                        for tag in ("ea", "cs"):
                            el = rpr.find(A + tag)
                            if el is None:
                                el = etree.SubElement(rpr, A + tag)
                            el.set("typeface", name)
            if autofit:
                bp = tf._txBody.find(A + "bodyPr")
                for t in ("noAutofit", "normAutofit", "spAutoFit"):
                    for e in bp.findall(A + t):
                        bp.remove(e)
                etree.SubElement(bp, A + {"none": "noAutofit", "shrink": "normAutofit", "resize": "spAutoFit"}[autofit])
            self._rec("font", n, sh, size=size, bold=bold, italic=italic, color=color, name=name, align=align)
        return self

    def fill(self, n, sel, color=None, transparency: float | None = None, none: bool = False):
        for sh in self.shapes(n, sel):
            if none:
                sh.fill.background()
            elif color:
                sh.fill.solid()
                sh.fill.fore_color.rgb = _rgb(color)
                if transparency is not None:
                    srgb = sh._element.find(".//" + A + "solidFill/" + A + "srgbClr")
                    for a in srgb.findall(A + "alpha"):
                        srgb.remove(a)
                    etree.SubElement(srgb, A + "alpha").set("val", str(int((1 - transparency) * 100000)))
            self._rec("fill", n, sh, color=color, transparency=transparency, none=none)
        return self

    def notes(self, n, text: str):
        sl = self.slide(n)
        sl.notes_slide.notes_text_frame.text = text
        self._rec("notes", n, None, text=text[:80])
        return self

    # ------------------------------------------------------------------ slides
    def _sldIdLst(self):
        return self.prs.slides._sldIdLst

    def move_slide(self, src: int, dst: int):
        lst = self._sldIdLst()
        items = list(lst)
        el = items[src - 1]
        lst.remove(el)
        lst.insert(dst - 1, el)
        self._rec("move_slide", None, None, src=src, dst=dst)
        return self

    def delete_slide(self, n: int):
        lst = self._sldIdLst()
        el = list(lst)[n - 1]
        rid = el.get(R + "id")
        self.prs.part.drop_rel(rid)
        lst.remove(el)
        self._rec("delete_slide", n, None)
        return self

    def duplicate_slide(self, n: int, to: int | None = None):
        src = self.slide(n)
        new = self.prs.slides.add_slide(src.slide_layout)
        for sh in list(new.shapes):
            sh._element.getparent().remove(sh._element)
        for el in src.shapes._spTree:
            if etree.QName(el).localname in ("nvGrpSpPr", "grpSpPr"):
                continue
            new.shapes._spTree.append(copy.deepcopy(el))
        # copy relationships used by pictures/media/links
        for rel in src.part.rels.values():
            if "notesSlide" in rel.reltype or "slideLayout" in rel.reltype:
                continue
            new_rid = new.part.rels.get_or_add(rel.reltype, rel._target) if not rel.is_external else \
                new.part.rels.get_or_add_ext_rel(rel.reltype, rel.target_ref)
            if new_rid != rel.rId:
                for e in new.shapes._spTree.iter():
                    for k, v in e.attrib.items():
                        if v == rel.rId and k.startswith(R):
                            e.set(k, new_rid)
        # background + transition + timing
        bg = src._element.find(f"{P}cSld/{P}bg")
        if bg is not None:
            new._element.find(f"{P}cSld").insert(0, copy.deepcopy(bg))
        for child in src._element:
            ln = etree.QName(child).localname
            if ln in ("transition", "timing", "AlternateContent"):
                new._element.append(copy.deepcopy(child))
        if to:
            self.move_slide(len(self.prs.slides), to)
        self._rec("duplicate_slide", n, None, to=to or len(self.prs.slides))
        return new

    def hide_slide(self, n: int, hidden: bool = True):
        sl = self.slide(n)
        if hidden:
            sl._element.set("show", "0")
        elif "show" in sl._element.attrib:
            del sl._element.attrib["show"]
        self._rec("hide_slide", n, None, hidden=hidden)
        return self

    def transition(self, n, kind="fade", dur_ms=700, direction=None):
        from . import anim
        for i in ([n] if n != "*" else range(1, len(self.prs.slides) + 1)):
            anim.set_transition(self.slide(i), kind, dur_ms, direction)
            self.touched.add(i)
        self._rec("transition", n, None, kind=kind, dur_ms=dur_ms)
        return self

    def background(self, n, color):
        sl = self.slide(n)
        fill = sl.background.fill
        fill.solid()
        fill.fore_color.rgb = _rgb(color)
        self._rec("background", n, None, color=color)
        return self

    # ------------------------------------------------------------------ io
    def save(self, out=None):
        out = Path(out or self.path)
        out.parent.mkdir(parents=True, exist_ok=True)
        self.prs.save(str(out))
        return out


# ---------------------------------------------------------------------- batch ops (JSON / YAML / CLI)
OPS = {
    "move": ("slide", "shape"), "resize": ("slide", "shape"), "scale": ("slide", "shape", "factor"),
    "set_box": ("slide", "shape"), "rotate": ("slide", "shape", "deg"), "align": ("slide", "shapes", "how"),
    "distribute": ("slide", "shapes"), "z": ("slide", "shape"), "delete": ("slide", "shape"),
    "duplicate_shape": ("slide", "shape"), "crop": ("slide", "shape"), "fit": ("slide", "shape"),
    "zoom": ("slide", "shape", "factor"), "pan": ("slide", "shape"), "replace_image": ("slide", "shape", "image"),
    "add_image": ("slide", "image"), "replace_text": ("old", "new"), "set_text": ("slide", "shape", "text"),
    "font": ("slide", "shape"), "fill": ("slide", "shape"), "notes": ("slide", "text"),
    "move_slide": ("src", "dst"), "delete_slide": ("slide",), "duplicate_slide": ("slide",),
    "hide_slide": ("slide",), "transition": ("slide",), "background": ("slide", "color"),
}
ALIASES = {"slide": "n", "shape": "sel", "shapes": "sels", "image": "image_path", "src": "src", "dst": "dst"}


def apply_ops(deck: Deck, ops: list[dict]) -> list[dict]:
    results = []
    for i, op in enumerate(ops, 1):
        op = dict(op)
        name = op.pop("op")
        if name not in OPS:
            raise EditError(f"Неизвестная операция {name!r}. Доступно: {', '.join(OPS)}")
        fn = getattr(deck, name)
        kwargs = {}
        for k, v in op.items():
            kwargs[ALIASES.get(k, k)] = v
        if name in ("move_slide",):
            kwargs = {"src": int(op["src"]), "dst": int(op["dst"])}
        if name in ("delete_slide", "duplicate_slide", "hide_slide"):
            kwargs = {"n": int(op["slide"]), **{k: v for k, v in op.items() if k not in ("slide",)}}
        if "focus" in kwargs and isinstance(kwargs["focus"], str):
            kwargs["focus"] = tuple(float(x) for x in kwargs["focus"].split(","))
        t = time.perf_counter()
        fn(**kwargs)
        results.append({"i": i, "op": name, "ms": round((time.perf_counter() - t) * 1000, 2), **deck.log[-1]})
    return results


def load_ops(path_or_json: str) -> list[dict]:
    s = str(path_or_json)
    if s.strip().startswith(("[", "{")):
        data = json.loads(s)
    else:
        p = Path(s)
        text = p.read_text(encoding="utf-8")
        if p.suffix.lower() in (".yaml", ".yml"):
            import yaml
            data = yaml.safe_load(text)
        else:
            data = json.loads(text)
    if isinstance(data, dict):
        data = data.get("ops", [data])
    return data
