"""PowerPoint transitions & animations written as raw PresentationML (python-pptx has no API).

The XML mirrors what PowerPoint 2010+ itself writes:
* transitions: <p:transition> (wrapped in mc:AlternateContent when a p14/p15 effect or an exact
  duration is used, with a plain fade fallback for old readers)
* entrance effects: appear / fade / zoom / fly / float / wipe, started on click, with previous or
  after previous, with delays & durations, auto-starting when the slide opens
* triggers: "on click of shape X" interactive sequences (used for quizzes)

    from pptkit import anim
    anim.set_transition(slide, "fade", dur_ms=700)
    anim.animate(slide, [dict(shape=title, effect="fade", start="after"),
                         dict(shape=pic, effect="zoom", start="with", delay_ms=200)])
    anim.add_trigger(slide, trigger=answer_box, steps=[dict(shape=check_mark, effect="zoom")])
"""
from __future__ import annotations

from lxml import etree

P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
MC_NS = "http://schemas.openxmlformats.org/markup-compatibility/2006"
P14_NS = "http://schemas.microsoft.com/office/powerpoint/2010/main"
P15_NS = "http://schemas.microsoft.com/office/powerpoint/2012/main"
P = "{%s}" % P_NS

BASE_TRANSITIONS = {"fade", "push", "wipe", "cover", "pull", "split", "zoom", "circle", "dissolve", "cut",
                    "randomBar", "diamond", "plus", "wedge", "newsflash", "blinds", "checker", "comb", "strips",
                    "wheel", "random"}
P14_TRANSITIONS = {"vortex", "ripple", "honeycomb", "glitter", "prism", "doors", "window", "ferris", "gallery",
                   "conveyor", "pan", "flip", "switch", "flythrough", "flash", "shred", "reveal", "wheelReverse",
                   "warp"}
P15_PRESETS = {"curtains", "wind", "fracture", "crush", "peelOff", "pageCurlDouble", "pageCurlSingle", "airplane",
               "origami", "drape", "prestige"}
DIR_ATTR = {"push": "dir", "wipe": "dir", "cover": "dir", "pull": "dir", "vortex": "dir", "gallery": "dir",
            "conveyor": "dir", "pan": "dir", "flip": "dir", "switch": "dir", "ferris": "dir", "flythrough": "dir",
            "prism": "dir", "reveal": "dir", "warp": "dir", "glitter": "dir", "doors": "dir", "window": "dir",
            "zoom": "dir", "split": "dir"}
DEFAULT_DIR = {"push": "l", "wipe": "l", "cover": "l", "pull": "l", "vortex": "r", "gallery": "l",
               "conveyor": "l", "pan": "l", "flip": "l", "switch": "l", "ferris": "l", "flythrough": "in",
               "prism": "l", "reveal": "l", "warp": "in", "glitter": "l", "doors": "vert", "window": "vert",
               "zoom": "in", "split": "out"}


def _sld(slide):
    return slide._element


def _clear_transition(sld):
    for child in list(sld):
        tag = etree.QName(child).localname
        if tag == "transition":
            sld.remove(child)
        elif tag == "AlternateContent" and child.find(".//" + P + "transition") is not None:
            sld.remove(child)


def _insert_after_clrmap(sld, el):
    """Children order of p:sld: cSld, clrMapOvr?, transition?, timing?, extLst?"""
    anchor = sld.find(P + "clrMapOvr")
    if anchor is None:
        anchor = sld.find(P + "cSld")
    anchor.addnext(el)


def _speed(dur_ms: int) -> str:
    return "fast" if dur_ms <= 500 else ("med" if dur_ms <= 750 else "slow")


def set_transition(slide, kind: str = "fade", dur_ms: int = 700, direction: str | None = None,
                   advance_after_ms: int | None = None, advance_on_click: bool = True):
    """kind: fade|push|wipe|cover|split|zoom|... | p14: vortex|ripple|gallery|conveyor|pan|prism|...
    | p15: curtains|wind|fracture|crush|peelOff|airplane|origami|drape|prestige | none"""
    sld = _sld(slide)
    _clear_transition(sld)
    if kind in (None, "none", ""):
        return None

    def build(ns_extra: bool, which: str):
        t = etree.Element(P + "transition", nsmap=None)
        t.set("spd", _speed(dur_ms))
        if ns_extra:
            t.set("{%s}dur" % P14_NS, str(int(dur_ms)))
        if not advance_on_click:
            t.set("advClick", "0")
        if advance_after_ms is not None:
            t.set("advTm", str(int(advance_after_ms)))
        if which in P15_PRESETS:
            e = etree.SubElement(t, "{%s}prstTrans" % P15_NS)
            e.set("prst", which)
        elif which in P14_TRANSITIONS:
            e = etree.SubElement(t, "{%s}%s" % (P14_NS, which))
            if which in DIR_ATTR:
                e.set("dir", direction or DEFAULT_DIR[which])
        else:
            e = etree.SubElement(t, P + which)
            if which in DIR_ATTR:
                d = direction or DEFAULT_DIR[which]
                if which == "split":
                    e.set("orient", "horz")
                e.set("dir", d)
        return t

    requires = "p15" if kind in P15_PRESETS else "p14"
    ac = etree.Element("{%s}AlternateContent" % MC_NS, nsmap={"mc": MC_NS})
    choice = etree.SubElement(ac, "{%s}Choice" % MC_NS,
                              nsmap={"p14": P14_NS} if requires == "p14" else {"p14": P14_NS, "p15": P15_NS})
    choice.set("Requires", requires)
    choice.append(build(True, kind))
    fb = etree.SubElement(ac, "{%s}Fallback" % MC_NS)
    fb.append(build(False, kind if kind in BASE_TRANSITIONS else "fade"))
    _insert_after_clrmap(sld, ac)
    timing = sld.find(P + "timing")
    if timing is not None:  # keep schema order: transition before timing
        sld.remove(timing)
        ac.addnext(timing)
    return ac


# ----------------------------------------------------------------------------- animations
PRESET = {  # effect -> (presetID, default subtype)
    "appear": (1, 0), "fade": (10, 0), "zoom": (53, 16), "fly": (2, 4), "float": (42, 0), "wipe": (22, 8),
}
FLY_SUB = {"bottom": 4, "left": 8, "right": 2, "top": 1}
WIPE_SUB = {"left": 8, "right": 2, "bottom": 4, "top": 1}


class _Ids:
    def __init__(self):
        self.n = 0

    def __call__(self):
        self.n += 1
        return str(self.n)


def _E(tag, attrib=None, *children):
    el = etree.Element(P + tag)
    for k, v in (attrib or {}).items():
        el.set(k, str(v))
    for c in children:
        el.append(c)
    return el


def _cbhvr(ids, spid, dur, attr=None, fill_hold=True, additive=None, delay0=False):
    ctn = _E("cTn", {"id": ids(), "dur": dur, **({"fill": "hold"} if fill_hold else {})})
    if delay0:
        ctn.append(_E("stCondLst", None, _E("cond", {"delay": 0})))
    tgt = _E("tgtEl", None, _E("spTgt", {"spid": spid}))
    cb = _E("cBhvr", {"additive": additive} if additive else None, ctn, tgt)
    if attr:
        cb.append(_E("attrNameLst", None, *[_attrname(a) for a in ([attr] if isinstance(attr, str) else attr)]))
    return cb


def _attrname(a):
    e = _E("attrName")
    e.text = a
    return e


def _set_visible(ids, spid):
    s = _E("set")
    s.append(_cbhvr(ids, spid, 1, "style.visibility", delay0=True))
    to = _E("to", None, _E("strVal", {"val": "visible"}))
    s.append(to)
    return s


def _anim(ids, spid, dur, attr, v0, v1, additive=None):
    a = _E("anim", {"calcmode": "lin", "valueType": "num"})
    a.append(_cbhvr(ids, spid, dur, attr, additive=additive))
    tav = _E("tavLst")
    for tm, v in (("0", v0), ("100000", v1)):
        val = _E("val")
        if isinstance(v, (int, float)):
            val.append(_E("fltVal", {"val": v}))
        else:
            val.append(_E("strVal", {"val": v}))
        tav.append(_E("tav", {"tm": tm}, val))
    a.append(tav)
    return a


def _anim_effect(ids, spid, dur, flt):
    ae = _E("animEffect", {"transition": "in", "filter": flt})
    ae.append(_cbhvr(ids, spid, dur, None, fill_hold=False))
    return ae


def _behaviors(ids, effect, spid, dur, direction):
    out = [_set_visible(ids, spid)]
    if effect == "appear":
        return out, 0
    if effect == "fade":
        out.append(_anim_effect(ids, spid, dur, "fade"))
        return out, 0
    if effect == "zoom":
        out += [_anim(ids, spid, dur, "ppt_w", 0, "#ppt_w"), _anim(ids, spid, dur, "ppt_h", 0, "#ppt_h"),
                _anim_effect(ids, spid, dur, "fade")]
        return out, 16
    if effect == "fly":
        d = direction or "bottom"
        x0, y0 = "#ppt_x", "#ppt_y"
        if d == "bottom":
            y0 = "1+#ppt_h/2"
        elif d == "top":
            y0 = "0-#ppt_h/2"
        elif d == "left":
            x0 = "0-#ppt_w/2"
        elif d == "right":
            x0 = "1+#ppt_w/2"
        out += [_anim(ids, spid, dur, "ppt_x", x0, "#ppt_x", additive="base"),
                _anim(ids, spid, dur, "ppt_y", y0, "#ppt_y", additive="base")]
        return out, FLY_SUB[d]
    if effect == "float":
        out += [_anim_effect(ids, spid, dur, "fade"), _anim(ids, spid, dur, "ppt_x", "#ppt_x", "#ppt_x"),
                _anim(ids, spid, dur, "ppt_y", "#ppt_y+.1", "#ppt_y")]
        return out, 0
    if effect == "wipe":
        d = direction or "left"
        out.append(_anim_effect(ids, spid, dur, f"wipe({ {'left': 'left', 'right': 'right', 'top': 'up', 'bottom': 'down'}[d] })"))
        return out, WIPE_SUB[d]
    raise ValueError(f"unknown effect {effect!r}; use {sorted(PRESET)}")


def _effect_par(ids, step, node_type):
    effect = step.get("effect", "fade")
    spid = str(step["spid"])
    dur = int(step.get("dur_ms", 500 if effect != "float" else 800))
    ctn = _E("cTn", {"id": ids(), "presetID": PRESET[effect][0], "presetClass": "entr", "presetSubtype": 0,
                     "fill": "hold", "grpId": 0, "nodeType": node_type})
    if effect in ("zoom", "fly", "wipe", "float", "fade", "appear"):
        pass
    ctn.append(_E("stCondLst", None, _E("cond", {"delay": int(step.get("delay_ms", 0))})))
    beh, sub = _behaviors(ids, effect, spid, dur, step.get("direction"))
    ctn.set("presetSubtype", str(sub))
    ctn.append(_E("childTnLst", None, *beh))
    return _E("par", None, ctn), int(step.get("delay_ms", 0)) + (dur if effect != "appear" else 1)


def _blocks(ids, steps, first_node_type):
    """Build the timing blocks of one click group. Returns list of <p:par> blocks."""
    blocks, cur, offset, cur_end = [], None, 0, 0
    for k, st in enumerate(steps):
        start = st.get("start", "after")
        if k == 0:
            node = first_node_type
            new_block = True
        else:
            node = "withEffect" if start == "with" else "afterEffect"
            new_block = start != "with"
        if new_block:
            if cur is not None:
                offset = offset + cur_end
            cur_end = 0
            ctn = _E("cTn", {"id": ids(), "fill": "hold"},
                     _E("stCondLst", None, _E("cond", {"delay": offset})), _E("childTnLst"))
            cur = ctn
            blocks.append(_E("par", None, ctn))
        par, end = _effect_par(ids, st, node)
        cur.find(P + "childTnLst").append(par)
        cur_end = max(cur_end, end)
    return blocks


def _shape_info(slide, shape_or_id):
    if isinstance(shape_or_id, (int, str)):
        spid = int(shape_or_id)
        el = None
        for sh in slide.shapes:
            if sh.shape_id == spid:
                el = sh._element
        return spid, el
    return shape_or_id.shape_id, shape_or_id._element


def _get_timing(sld, create=True):
    timing = sld.find(P + "timing")
    if timing is None and create:
        timing = _E("timing")
        ac = None
        for child in sld:
            if etree.QName(child).localname in ("transition",) or (
                    etree.QName(child).localname == "AlternateContent" and child.find(".//" + P + "transition") is not None):
                ac = child
        if ac is not None:
            ac.addnext(timing)
        else:
            _insert_after_clrmap(sld, timing)
    return timing


def clear_animations(slide):
    sld = _sld(slide)
    t = sld.find(P + "timing")
    if t is not None:
        sld.remove(t)


def _bld(timing, slide, spids):
    bl = timing.find(P + "bldLst")
    if bl is None:
        bl = _E("bldLst")
        timing.append(bl)
    have = {b.get("spid") for b in bl}
    for spid in spids:
        _, el = _shape_info(slide, spid)
        if el is not None and etree.QName(el).localname == "sp" and str(spid) not in have:
            bl.append(_E("bldP", {"spid": spid, "grpId": 0, "animBg": 1}))
            have.add(str(spid))


def animate(slide, steps: list[dict], interactive: list[dict] | None = None):
    """Replace the slide's animations.

    steps: [{shape, effect: appear|fade|zoom|fly|float|wipe, start: click|with|after,
             delay_ms, dur_ms, direction: bottom|left|right|top}]
    The first step with start != 'click' auto-starts when the slide appears.
    interactive: [{trigger: shape, steps: [...]}] — revealed when the trigger shape is clicked.
    """
    sld = _sld(slide)
    clear_animations(slide)
    if not steps and not interactive:
        return None
    for st in steps:
        st["spid"], _ = _shape_info(slide, st["shape"])
    ids = _Ids()
    timing = _get_timing(sld)
    root_ctn = _E("cTn", {"id": ids(), "dur": "indefinite", "restart": "never", "nodeType": "tmRoot"})
    root_children = _E("childTnLst")
    root_ctn.append(root_children)
    timing.append(_E("tnLst", None, _E("par", None, root_ctn)))

    if steps:
        main_ctn = _E("cTn", {"id": ids(), "dur": "indefinite", "nodeType": "mainSeq"})
        main_id = main_ctn.get("id")
        main_children = _E("childTnLst")
        main_ctn.append(main_children)
        seq = _E("seq", {"concurrent": 1, "nextAc": "seek"}, main_ctn)
        seq.append(_E("prevCondLst", None, _E("cond", {"evt": "onPrev", "delay": 0}, _E("tgtEl", None, _E("sldTgt")))))
        seq.append(_E("nextCondLst", None, _E("cond", {"evt": "onNext", "delay": 0}, _E("tgtEl", None, _E("sldTgt")))))
        root_children.append(seq)
        # split into click groups
        groups, cur = [], []
        for st in steps:
            if st.get("start", "after") == "click" and cur:
                groups.append(cur)
                cur = []
            cur.append(st)
        if cur:
            groups.append(cur)
        for gi, grp in enumerate(groups):
            first_start = grp[0].get("start", "after")
            gctn = _E("cTn", {"id": ids(), "fill": "hold"})
            st_cond = _E("stCondLst", None, _E("cond", {"delay": "indefinite"}))
            if gi == 0 and first_start != "click":
                st_cond.append(_E("cond", {"evt": "onBegin", "delay": 0}, _E("tn", {"val": main_id})))
            gctn.append(st_cond)
            node_first = "clickEffect" if first_start == "click" else (
                "withEffect" if first_start == "with" else "afterEffect")
            gctn.append(_E("childTnLst", None, *_blocks(ids, grp, node_first)))
            main_children.append(_E("par", None, gctn))

    for inter in interactive or []:
        tid, _ = _shape_info(slide, inter["trigger"])
        for st in inter["steps"]:
            st["spid"], _ = _shape_info(slide, st["shape"])
        ictn = _E("cTn", {"id": ids(), "restart": "whenNotActive", "fill": "hold", "evtFilter": "cancelBubble",
                          "nodeType": "interactiveSeq"})
        ictn.append(_E("stCondLst", None, _E("cond", {"evt": "onClick", "delay": 0},
                                              _E("tgtEl", None, _E("spTgt", {"spid": tid})))))
        ictn.append(_E("endSync", {"evt": "end", "delay": 0}, _E("rtn", {"val": "all"})))
        gctn = _E("cTn", {"id": ids(), "fill": "hold"}, _E("stCondLst", None, _E("cond", {"delay": 0})))
        gctn.append(_E("childTnLst", None, *_blocks(ids, inter["steps"], "clickEffect")))
        ictn.append(_E("childTnLst", None, _E("par", None, gctn)))
        seq = _E("seq", {"concurrent": 1, "nextAc": "seek"}, ictn)
        seq.append(_E("nextCondLst", None, _E("cond", {"evt": "onClick", "delay": 0},
                                               _E("tgtEl", None, _E("spTgt", {"spid": tid})))))
        root_children.append(seq)

    all_spids = [st["spid"] for st in steps] + [st["spid"] for it in (interactive or []) for st in it["steps"]]
    _bld(timing, slide, all_spids)
    return timing


def summary(slide) -> dict:
    """Describe a slide's transition/animations (used by inspect)."""
    sld = _sld(slide)
    tr = None
    for child in sld:
        ln = etree.QName(child).localname
        el = child if ln == "transition" else (child.find(".//" + P + "transition") if ln == "AlternateContent" else None)
        if el is not None:
            kinds = [etree.QName(c).localname for c in el]
            tr = {"type": kinds[0] if kinds else "none", "spd": el.get("spd"),
                  "dur": el.get("{%s}dur" % P14_NS)}
            break
    effects = []
    t = sld.find(P + "timing")
    if t is not None:
        for ctn in t.iter(P + "cTn"):
            if ctn.get("presetClass"):
                sp = ctn.find(".//" + P + "spTgt")
                effects.append({"class": ctn.get("presetClass"), "preset": ctn.get("presetID"),
                                "node": ctn.get("nodeType"), "spid": sp.get("spid") if sp is not None else None})
    triggers = len(t.findall(".//" + P + "cTn[@nodeType='interactiveSeq']")) if t is not None else 0
    return {"transition": tr, "effects": effects, "triggers": triggers}
