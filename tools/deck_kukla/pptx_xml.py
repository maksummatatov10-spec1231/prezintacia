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


def add_video_background(slide_xml: bytes, *, w: int, h: int, poster_rid: str, video_link_rid: str,
                         video_embed_rid: str, name: str = "Фон · краски") -> bytes:
    """Full-bleed video behind everything + timing that starts & loops it when the slide opens."""
    root = etree.fromstring(slide_xml)
    tree = _sp_tree(root)
    assert tree is not None, "p:spTree not found"
    spid = _max_id(root) + 1
    pic = _pic_el(tree, spid, name, (0, 0, w, h), poster_rid, video=(video_link_rid, video_embed_rid),
                  descr="Живой фон: размытые пятна красок")
    pic.attrib.pop("__new", None)
    tree.insert(2, pic)

    # timing: <p:timing><p:tnLst><p:par><p:cTn nodeType="tmRoot">… video autoplay, loop
    timing = root.find(q(P, "timing"))
    if timing is None:
        timing = etree.SubElement(root, q(P, "timing"))
    tl = etree.SubElement(timing, q(P, "tnLst"))
    par = etree.SubElement(tl, q(P, "par"))
    c1 = etree.SubElement(par, q(P, "cTn")); c1.set("id", "1"); c1.set("dur", "indefinite")
    c1.set("restart", "never"); c1.set("nodeType", "tmRoot")
    ch1 = etree.SubElement(c1, q(P, "childTnLst"))
    seq = etree.SubElement(ch1, q(P, "seq")); seq.set("concurrent", "1"); seq.set("nextAc", "seek")
    c2 = etree.SubElement(seq, q(P, "cTn")); c2.set("id", "2"); c2.set("dur", "indefinite"); c2.set("nodeType", "mainSeq")
    ch2 = etree.SubElement(c2, q(P, "childTnLst"))
    par2 = etree.SubElement(ch2, q(P, "par"))
    c3 = etree.SubElement(par2, q(P, "cTn")); c3.set("id", "3"); c3.set("fill", "hold")
    st3 = etree.SubElement(c3, q(P, "stCondLst"))
    cond = etree.SubElement(st3, q(P, "cond")); cond.set("delay", "indefinite")
    cond = etree.SubElement(st3, q(P, "cond")); cond.set("evt", "onBegin"); cond.set("delay", "0")
    tn = etree.SubElement(cond, q(P, "tn")); tn.set("val", "2")
    ch3 = etree.SubElement(c3, q(P, "childTnLst"))
    par3 = etree.SubElement(ch3, q(P, "par"))
    c4 = etree.SubElement(par3, q(P, "cTn")); c4.set("id", "4"); c4.set("fill", "hold")
    st4 = etree.SubElement(c4, q(P, "stCondLst"))
    cond = etree.SubElement(st4, q(P, "cond")); cond.set("delay", "0")
    ch4 = etree.SubElement(c4, q(P, "childTnLst"))
    video = etree.SubElement(ch4, q(P, "video"))
    mn = etree.SubElement(video, q(P, "cMediaNode"))
    mn.set("vol", "800"); mn.set("numLoop", "0"); mn.set("showWhenStopped", "1"); mn.set("fullScrn", "0")
    c5 = etree.SubElement(mn, q(P, "cTn")); c5.set("id", "5"); c5.set("fill", "hold"); c5.set("display", "0")
    st5 = etree.SubElement(c5, q(P, "stCondLst"))
    cond = etree.SubElement(st5, q(P, "cond")); cond.set("delay", "0")
    en5 = etree.SubElement(c5, q(P, "endCondLst"))
    cond = etree.SubElement(en5, q(P, "cond")); cond.set("evt", "onStopAudio"); cond.set("delay", "0")
    tg = etree.SubElement(cond, q(P, "tgtEl")); etree.SubElement(tg, q(P, "sldTgt"))
    tg = etree.SubElement(mn, q(P, "tgtEl"))
    sp = etree.SubElement(tg, q(P, "spTgt")); sp.set("spid", str(spid))
    prev = etree.SubElement(seq, q(P, "prevCondLst"))
    cond = etree.SubElement(prev, q(P, "cond")); cond.set("evt", "onPrev"); cond.set("delay", "0")
    tg = etree.SubElement(cond, q(P, "tgtEl")); etree.SubElement(tg, q(P, "sldTgt"))
    nxt = etree.SubElement(seq, q(P, "nextCondLst"))
    cond = etree.SubElement(nxt, q(P, "cond")); cond.set("evt", "onNext"); cond.set("delay", "0")
    tg = etree.SubElement(cond, q(P, "tgtEl")); etree.SubElement(tg, q(P, "sldTgt"))
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
