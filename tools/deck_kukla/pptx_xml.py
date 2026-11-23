"""Helpers for editing raw PresentationML that python-pptx cannot express.

* add_video_background(): full-slide, autoplaying, looping video + poster frame (the way PowerPoint 2010+
  itself stores it: a p:pic whose nvPr carries a:videoFile + p14:media, with the poster in blipFill)
* add_picture_part(): insert a new image part + relationship + p:pic shape
* set_transition(): fade transition
* replace_media(): swap the bytes of an existing media part (keeps rIds, crop, geometry)
"""
from __future__ import annotations

import re
from lxml import etree

P = "http://schemas.openxmlformats.org/presentationml/2006/main"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
P14 = "http://schemas.microsoft.com/office/powerpoint/2010/main"
PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"
VIDEO_EXT_URI = "{DAA4B4D4-6D71-4841-9C94-3DE7FCFB9230}"


def q(ns: str, tag: str) -> str:
    return "{%s}%s" % (ns, tag)


def _max_id(root) -> int:
    ids = [int(e.get("id")) for e in root.iter(q(P, "cNvPr")) if (e.get("id") or "").isdigit()]
    return max(ids, default=1)


# --------------------------------------------------------------------------- relationships & content types
def next_rid(rels_xml: bytes) -> str:
    have = {m.group(1) for m in re.finditer(rb'Id="rId(\d+)"', rels_xml)}
    n = 1
    while str(n) in {h.decode() for h in have}:
        n += 1
    return f"rId{n}"


def add_rel(rels_xml: bytes, rid: str, rtype: str, target: str) -> bytes:
    rel = f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/{rtype}" Target="{target}"/>'
    s = rels_xml.decode("utf-8")
    i = s.rindex("</Relationships>")
    return (s[:i] + rel + s[i:]).encode("utf-8")


def ensure_default(ct_xml: bytes, ext: str, mime: str) -> bytes:
    s = ct_xml.decode("utf-8")
    if re.search(rf'<Default Extension="{ext}"', s, re.I):
        return ct_xml
    i = s.index(">", s.index("<Types")) + 1
    return (s[:i] + f'<Default Extension="{ext}" ContentType="{mime}"/>' + s[i:]).encode("utf-8")


# --------------------------------------------------------------------------- slide pieces
def _sp_tree(root):
    return root.find(f"{q(P, 'cSld')}/{q(P, 'spTree')}")


def _pic_el(root, spid: int, name: str, xfrm, embed_rid: str, video: tuple[str, str] | None = None, descr: str | None = None):
    """A p:pic element (image, or image+video when video=(link_rid, embed_rid))."""
    pic = etree.Element(q(P, "pic"))
    pic.set("__new", "1")
    nv = etree.SubElement(pic, q(P, "nvPicPr"))
    cnv = etree.SubElement(nv, q(P, "cNvPr"))
    cnv.set("id", str(spid))
    cnv.set("name", name)
    if descr:
        cnv.set("descr", descr)
    cnvp = etree.SubElement(nv, q(P, "cNvPicPr"))
    locks = etree.SubElement(cnvp, q(A, "picLocks"))
    for k in ("noChangeAspect", "noMove", "noResize"):
        locks.set(k, "1")
    nvpr = etree.SubElement(nv, q(P, "nvPr"))
    if video:
        vf = etree.SubElement(nvpr, q(A, "videoFile"))
        vf.set(q(R, "link"), video[0])
        extl = etree.SubElement(nvpr, q(P, "extLst"))
        ext = etree.SubElement(extl, q(P, "ext"))
        ext.set("uri", VIDEO_EXT_URI)
        media = etree.SubElement(ext, q(P14, "media"))
        media.set(q(R, "embed"), video[1])
    blip = etree.SubElement(pic, q(P, "blipFill"))
    b = etree.SubElement(blip, q(A, "blip"))
    b.set(q(R, "embed"), embed_rid)
    st = etree.SubElement(blip, q(A, "stretch"))
    etree.SubElement(st, q(A, "fillRect"))
    sppr = etree.SubElement(pic, q(P, "spPr"))
    x = etree.SubElement(sppr, q(A, "xfrm"))
    off = etree.SubElement(x, q(A, "off")); off.set("x", str(xfrm[0])); off.set("y", str(xfrm[1]))
    ext_ = etree.SubElement(x, q(A, "ext")); ext_.set("cx", str(xfrm[2])); ext_.set("cy", str(xfrm[3]))
    geo = etree.SubElement(sppr, q(A, "prstGeom")); geo.set("prst", "rect")
    etree.SubElement(geo, q(A, "avLst"))
    etree.SubElement(sppr, q(A, "noFill"))
    ln = etree.SubElement(sppr, q(A, "ln")); etree.SubElement(ln, q(A, "noFill"))
    return pic


def add_picture(slide_xml: bytes, *, x: int, y: int, w: int, h: int, embed_rid: str, name: str = "Picture",
                descr: str | None = None, round_adj: int | None = None, index: int = 2,
                shadow: float | None = None) -> bytes:
    """Insert a p:pic at position `index` inside spTree (2 = first shape, on top of the background)."""
    root = etree.fromstring(slide_xml)
    tree = _sp_tree(root)
    assert tree is not None, "p:spTree not found"
    spid = _max_id(root) + 1
    pic = _pic_el(tree, spid, name, (x, y, w, h), embed_rid, descr=descr)
    pic.attrib.pop("__new", None)
    if round_adj is not None:
        geo = pic.find(f"{q(P, 'spPr')}/{q(A, 'prstGeom')}")
        geo.set("prst", "roundRect")
        av = geo.find(q(A, "avLst"))
        gd = etree.SubElement(av, q(A, "gd")); gd.set("name", "adj"); gd.set("fmla", f"val {round_adj}")
    if shadow:  # soft drop shadow, like the cards in the deck
        eff = etree.SubElement(pic.find(q(P, "spPr")), q(A, "effectLst"))
        sh = etree.SubElement(eff, q(A, "outerShdw"))
        sh.set("blurRad", "190500"); sh.set("dist", "25400"); sh.set("dir", "2700000")
        sh.set("algn", "tl"); sh.set("rotWithShape", "0")
        clr = etree.SubElement(sh, q(A, "srgbClr")); clr.set("val", "2A1A17")
        al = etree.SubElement(clr, q(A, "alpha")); al.set("val", str(int(shadow * 100000)))
    tree.insert(index, pic)
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def add_backdrop(slide_xml: bytes, *, w: int, h: int, embed_rid: str, name: str = "Фон · краски") -> bytes:
    """Full-bleed background picture, bottom of the z-order. Plain png/jpg only — no media, no timing:
    PowerPoint opens such a file without any repair prompt."""
    root = etree.fromstring(slide_xml)
    tree = _sp_tree(root)
    assert tree is not None, "p:spTree not found"
    spid = _max_id(root) + 1
    pic = _pic_el(tree, spid, name, (0, 0, w, h), embed_rid,
                  descr="Фон: размытые пятна красок")
    pic.attrib.pop("__new", None)
    tree.insert(2, pic)

    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def set_bg_image(slide_xml: bytes, rid: str) -> bytes:
    """Slide background = an image (cover-filled). It shows until/unless the video starts, so a failed
    video can never leave a white slide."""
    root = etree.fromstring(slide_xml)
    csld = root.find(q(P, "cSld"))
    old = csld.find(q(P, "bg"))
    if old is not None:
        csld.remove(old)
    bg = etree.Element(q(P, "bg"))
    bgpr = etree.SubElement(bg, q(P, "bgPr"))
    blip = etree.SubElement(bgpr, q(A, "blipFill"))
    b = etree.SubElement(blip, q(A, "blip")); b.set(q(R, "embed"), rid)
    st = etree.SubElement(blip, q(A, "stretch")); etree.SubElement(st, q(A, "fillRect"))
    etree.SubElement(bgpr, q(A, "effectLst"))
    csld.insert(0, bg)
    # keep schema order: bg first child of cSld, then spTree
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def set_fade(slide_xml: bytes, spd: str = "med") -> bytes:
    root = etree.fromstring(slide_xml)
    if root.find(q(P, "transition")) is not None:
        return slide_xml
    tr = etree.Element(q(P, "transition")); tr.set("spd", spd)
    etree.SubElement(tr, q(P, "fade"))
    # order: cSld, clrMapOvr, transition, timing
    anchor = root.find(q(P, "clrMapOvr"))
    if anchor is None:
        anchor = root.find(q(P, "cSld"))
    anchor.addnext(tr)
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)




# --------------------------------------------------------------------------- entrances (animations)
#
# PowerPoint keeps slide animation in p:timing (the LAST child of p:sld, after cSld / clrMapOvr / transition).
# The shape of it that PowerPoint itself writes for "Fade, start with previous, quickly":
#
#   p:timing > p:tnLst > p:par > p:cTn id=1 dur=indefinite nodeType=tmRoot restart=never
#     p:childTnLst > p:seq concurrent=1 nextAc=seek
#       p:cTn id=2 dur=indefinite nodeType=mainSeq
#         p:childTnLst
#           p:par                                   ← one "click group"
#             p:cTn id=3 fill=hold
#               p:stCondLst > p:cond delay=...      ← 0 = starts by itself, indefinite = on click
#               p:childTnLst
#                 p:par > p:cTn id=4 fill=hold
#                   p:stCondLst > p:cond delay=0
#                   p:childTnLst
#                     p:par > p:cTn id=5 nodeType=clickEffect presetID=10 presetClass=entr
#                       presetSubtype=0 grpId=0
#                       p:stCondLst > p:cond delay=k*step
#                       p:childTnLst
#                         p:set / p:animEffect   ← each one needs cBhvr > cTn(stCondLst) + tgtEl (+ attrNameLst)
#       p:prevCondLst / p:nextCondLst               ← PowerPoint always writes both
#
# Every cTn needs a unique id, dur and restart="whenNotActive"; a missing piece is what makes PowerPoint
# offer «Восстановить». Only plain fade — no media, no motion paths.
_ID = [1]
FADE_PRESET = {"presetID": "10", "presetClass": "entr", "presetSubtype": "0", "grpId": "0"}


def _tn(parent, *, dur="1", fill="hold", node_type=None, restart="whenNotActive", attrs=None, cond=None):
    el = etree.SubElement(parent, q(P, "cTn"))
    el.set("id", str(_ID[0])); _ID[0] += 1
    el.set("dur", str(dur))
    if node_type:
        el.set("nodeType", node_type)
    if fill:
        el.set("fill", fill)
    if restart:
        el.set("restart", restart)
    for k, v in (attrs or {}).items():
        el.set(k, v)
    if cond is not None:
        _cond(etree.SubElement(el, q(P, "stCondLst")), cond)
    return el


def _cond(parent, delay="0", evt=None):
    c = etree.SubElement(parent, q(P, "cond"))
    c.set("delay", str(delay))
    if evt:
        c.set("evt", evt)
    return c


def _sld_tgt(parent):
    etree.SubElement(etree.SubElement(parent, q(P, "tgtEl")), q(P, "sldTgt"))


def _sp_tgt(parent, spid):
    etree.SubElement(etree.SubElement(parent, q(P, "tgtEl")), q(P, "spTgt")).set("spid", str(spid))


def _fade_effect(parent, spid: int, dur: int):
    """The two behaviours of a Fade entrance: make it visible, then fade it in."""
    pset = etree.SubElement(parent, q(P, "set"))
    cb = etree.SubElement(pset, q(P, "cBhvr"))
    _tn(cb, dur="1", cond="0")
    _sp_tgt(cb, spid)
    names = etree.SubElement(cb, q(P, "attrNameLst"))
    etree.SubElement(names, q(P, "attrName")).text = "style.visibility"
    to = etree.SubElement(pset, q(P, "to"))
    etree.SubElement(to, q(P, "strVal")).set("val", "visible")

    anim = etree.SubElement(parent, q(P, "animEffect"))
    anim.set("transition", "in")
    anim.set("filter", "fade")
    ab = etree.SubElement(anim, q(P, "cBhvr"))
    _tn(ab, dur=str(dur))
    _sp_tgt(ab, spid)


def _timing(ids: list[int], *, dur: int, step: int, on_click: bool) -> etree._Element:
    _ID[0] = 1
    timing = etree.Element(q(P, "timing"))
    tnl = etree.SubElement(timing, q(P, "tnLst"))
    rpar = etree.SubElement(tnl, q(P, "par"))
    root_tn = etree.SubElement(rpar, q(P, "cTn"))
    root_tn.set("id", "1"); root_tn.set("dur", "indefinite")
    root_tn.set("restart", "never"); root_tn.set("nodeType", "tmRoot")
    _ID[0] = 2
    seq = etree.SubElement(etree.SubElement(root_tn, q(P, "childTnLst")), q(P, "seq"))
    seq.set("concurrent", "1")
    seq.set("nextAc", "seek")
    main = etree.SubElement(seq, q(P, "cTn"))
    main.set("id", "2"); main.set("dur", "indefinite"); main.set("nodeType", "mainSeq")
    _ID[0] = 3
    lst = etree.SubElement(main, q(P, "childTnLst"))

    click = etree.SubElement(lst, q(P, "par"))
    click_tn = _tn(click, cond="indefinite" if on_click else "0")
    group = etree.SubElement(etree.SubElement(click_tn, q(P, "childTnLst")), q(P, "par"))
    group_tn = _tn(group, cond="0")
    effs = etree.SubElement(group_tn, q(P, "childTnLst"))
    for k, spid in enumerate(ids):
        par = etree.SubElement(effs, q(P, "par"))
        tn = _tn(par, dur=str(dur), node_type="clickEffect", attrs=FADE_PRESET, cond=str(k * step))
        _fade_effect(etree.SubElement(tn, q(P, "childTnLst")), spid, dur)

    prev = etree.SubElement(seq, q(P, "prevCondLst"))
    _sld_tgt(_cond(prev, "0", "onPrev"))
    nxt = etree.SubElement(seq, q(P, "nextCondLst"))
    _sld_tgt(_cond(nxt, "0", "onNext"))
    return timing


def auto_entrances(slide_xml: bytes, *, dur: int = 400, total: int = 1500, skip_names=(), skip_ids=()) -> bytes:
    """Fade in every text block / picture of the slide in reading order, fast, no clicking needed.

    `total` ms is the budget for the whole cascade, so a dense slide (17 has 60+ chart bars) still
    finishes quickly instead of dragging for seconds.
    """
    root = etree.fromstring(slide_xml)
    old = root.find(q(P, "timing"))
    if old is not None:
        root.remove(old)
    tree = _sp_tree(root)
    assert tree is not None
    ids: list[int] = []
    for el in tree:
        cnv = el.find(f"{q(P, 'nvPicPr')}/{q(P, 'cNvPr')}") if el.tag == q(P, "pic") else \
              el.find(f"{q(P, 'nvSpPr')}/{q(P, 'cNvPr')}")
        if cnv is None:
            continue
        if cnv.get("name") in skip_names or cnv.get("id") in {str(i) for i in skip_ids}:
            continue
        ids.append(int(cnv.get("id")))
    if not ids:
        return slide_xml
    step = max(20, min(90, total // max(1, len(ids))))
    root.append(_timing(ids, dur=dur, step=step, on_click=False))
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def page_number_ids(slide_xml: bytes) -> list[int]:
    """Ids of the little «1»…«19» page numbers, so they never animate."""
    out = []
    root = etree.fromstring(slide_xml)
    for sp in root.iter(q(P, "sp")):
        txt = "".join(t.text or "" for t in sp.iter(q(A, "t"))).strip()
        if re.fullmatch(r"\d{1,2}", txt):
            cnv = sp.find(f"{q(P, 'nvSpPr')}/{q(P, 'cNvPr')}")
            if cnv is not None:
                out.append(int(cnv.get("id")))
    return out
