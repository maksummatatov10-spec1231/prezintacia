"""Render the slide model to ONE self-contained HTML file (all images, fonts, maps inlined).

* landscape screens (PC, tablet, phone held sideways): the exact 16:9 slide "stage" scaled to fit,
  elements positioned 1:1 like the PPTX, with build animations;
* phone portrait: a dedicated vertical layout per slide (picture on top, card below, owl bubble),
  generated from each slide's `flow` description;
* swipe / tap / keyboard / dots navigation, progress bar, fullscreen, interactive quiz;
* contract for the screenshot tools: window.DECK = {count, index, go(i,{instant}), audit(), replay()},
  ?static=1 (all animations finished, used for screenshots), ?slide=N.
"""
from __future__ import annotations

import base64
import html
import json
import re
from pathlib import Path

import slides as S

SEG = re.compile(r"\*\*(.+?)\*\*|__(.+?)__|\{\{(.+?)\}\}")


def md(text: str) -> str:
    """markup → HTML (escaped)."""
    out, pos = [], 0
    for m in SEG.finditer(text):
        out.append(html.escape(text[pos:m.start()]))
        if m.group(1):
            out.append(f"<b>{html.escape(m.group(1))}</b>")
        elif m.group(2):
            out.append(f"<b class=acc>{html.escape(m.group(2))}</b>")
        else:
            out.append(f'<span class=gr>{html.escape(m.group(3))}</span>')
        pos = m.end()
    out.append(html.escape(text[pos:]))
    return "".join(out).replace("\n", "<br>")


class Assets:
    """Inline every asset ONCE as a CSS class rule  .A3{background-image:url(data:…)}  — elements just get
    the class (no huge var() substitution on every style recalc → fast slide changes on phones)."""

    def __init__(self):
        self.items: dict[str, str] = {}     # key -> data uri
        self.classes: dict[str, str] = {}   # key -> class name

    def key(self, path: str | Path, prefer_webp=True) -> str:
        p = Path(path)
        if prefer_webp and p.with_suffix(".webp").exists():
            p = p.with_suffix(".webp")
        k = f"{p.parent.name}-{p.stem}-{p.suffix[1:]}".replace(" ", "_")
        if k not in self.items:
            mime = {".webp": "image/webp", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                    ".svg": "image/svg+xml", ".woff2": "font/woff2"}[p.suffix.lower()]
            self.items[k] = f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode()
            self.classes[k] = f"A{len(self.classes)}"
        return k

    def cls(self, path, prefer_webp=True) -> str:
        return self.classes[self.key(path, prefer_webp)]

    def icon(self, name) -> str:
        return self.cls(S.A / "icons" / f"{name}.png")

    def css(self) -> str:
        # doubled class = higher specificity, so layout rules can never reset the picture
        return "".join(f".{c}.{c}{{background-image:url({self.items[k]})}}" for k, c in self.classes.items()
                       if not self.items[k].startswith("data:font"))


def pct(v, total):
    return f"{v / total * 100:.3f}%"


def anim_attrs(a, order):
    if not a:
        return ""
    eff = a["effect"]
    if a["start"] == "trigger":
        return f' data-trig="{a["trigger"]}" data-eff="{eff}" data-delay="{a["delay"]}" data-dur="{a["dur"]}"'
    return (f' data-o="{order}" data-eff="{eff}" data-dir="{a.get("direction", "")}" data-delay="{a["delay"]}"'
            f' data-dur="{a["dur"]}"')


def stage_html(sm, assets: Assets) -> str:
    """Absolute-positioned 16:9 stage (identical to the PPTX)."""
    parts = []
    order = 0
    t_cursor = 0  # timeline (ms) for "after"/"with" chaining (mirrors PowerPoint auto-sequence)
    for el in sm.els:
        t = el["type"]
        x, y, w, h = el.get("x", 0), el.get("y", 0), el.get("w", 0), el.get("h", 0)
        if t == "chip" and el.get("align") == "right":
            x -= w
        a = el.get("anim")
        attrs = ""
        if a and a["start"] != "trigger":
            if a["start"] == "after":
                order = t_cursor
            start = order + a["delay"]
            t_cursor = max(t_cursor, start + a["dur"])
            attrs = f' data-at="{start}" data-eff="{a["effect"]}" data-dir="{a.get("direction", "")}" data-dur="{a["dur"]}"'
        elif a:
            attrs = anim_attrs(a, 0)
        box = f"left:{pct(x, S.W)};top:{pct(y, S.H)};width:{pct(w, S.W)};height:{pct(h, S.H)}"
        rot = f";--r:{el['rot']}deg" if el.get("rot") else ""
        role = el.get("role", "")
        if t == "pic":
            ac = assets.cls(el["src"])
            fx, fy = el.get("focus", (0.5, 0.5))
            style = f"{box}{rot};background-position:{fx * 100:.1f}% {fy * 100:.1f}%"
            cls = f"e pic {ac}" + (" contain" if el.get("fit") == "contain" else "")
            if el.get("radius"):
                style += f";border-radius:calc(var(--u)*{el['radius'] * 100 / S.W:.3f})"
            if el.get("border"):
                style += f";border:calc(var(--u)*{el.get('border_w', 4) / 72 * 100 / S.W:.3f}) solid {el['border']}"
            if el.get("shadow"):
                cls += " shd"
            alt = html.escape(el.get("alt") or "")
            parts.append(f'<div class="{cls} {role}" style="{style}" role="img" aria-label="{alt}"{attrs}></div>')
        elif t == "rect":
            style = box
            if el.get("gradient"):
                stops = ", ".join(f"{_rgba(c, a_)} {p * 100:.0f}%" for p, c, a_ in el["gradient"])
                style += f";background:linear-gradient({90 + el.get('angle', 0)}deg, {stops})"
            elif el.get("fill"):
                style += f";background:{_rgba(el['fill'], el.get('alpha') or 1)}"
            if el.get("radius"):
                style += f";border-radius:calc(var(--u)*{el['radius'] * 100 / S.W:.3f})"
            if el.get("line"):
                style += f";border:calc(var(--u)*{el.get('line_w', 1.5) / 72 * 100 / S.W:.3f}) solid {el['line']}"
            cls = "e box" + (" shd" if el.get("shadow") else "")
            fb = f' data-fb="{el["feedback_for"]}"' if el.get("feedback_for") else ""
            parts.append(f'<div class="{cls} {role}" style="{style}"{attrs}{fb}></div>')
        elif t == "text":
            fs = el.get("size", 18)
            style = (f"{box};font-size:calc(var(--u)*{fs / 72 * 100 / S.W:.4f});color:{el.get('color', S.INK)};"
                     f"text-align:{el.get('align', 'left')};line-height:{1.25 * el.get('ls', 1.0):.3f}")
            fam = _fam(el.get("font", S.BODY), el.get("bold"))
            anchor = {"top": "flex-start", "middle": "center", "bottom": "flex-end"}[el.get("anchor", "top")]
            style += f";{fam};justify-content:{anchor}"
            fb = f' data-fb="{el["feedback_for"]}"' if el.get("feedback_for") else ""
            parts.append(f'<div class="e txt {role}" style="{style}"{attrs}{fb}><div>{md(el["text"])}</div></div>')
        elif t == "chip":
            fs = el["size"]
            style = (f"{box};background:{el['fill']};color:{el['color']};"
                     f"font-size:calc(var(--u)*{fs / 72 * 100 / S.W:.4f})")
            parts.append(f'<div class="e chip {role}" style="{style}"{attrs}>{md(el["text"])}</div>')
        elif t == "bubble":
            fs = el.get("size", 16)
            tx, ty = el["tip"]
            # tail: point (tx,ty) relative to centre, in fractions of w/h
            px, py = (0.5 + tx) * 100, (0.5 + ty) * 100
            side = "l" if px < 0 else "r" if px > 100 else ("t" if py < 0 else "b")
            style = (f"{box};font-size:calc(var(--u)*{fs / 72 * 100 / S.W:.4f});--tx:{px:.1f}%;--ty:{py:.1f}%")
            parts.append(f'<div class="e bub tail-{side} {role}" style="{style}"{attrs}><div>{md(el["text"])}</div></div>')
        elif t == "meander":
            ac = assets.cls(S.A / {"terra": "meander.png", "gold": "meander_gold.png", "white": "meander_white.png"}[el["color"]],
                            prefer_webp=False)
            parts.append(f'<div class="e mea {ac}" style="{box}"{attrs}></div>')
        elif t in ("badge", "dot"):
            fs = el.get("size", 18)
            style = f"{box};background:{el['fill']};color:{el.get('color', '#fff')};font-size:calc(var(--u)*{fs / 72 * 100 / S.W:.4f})"
            if el.get("line"):
                style += f";border:calc(var(--u)*0.22) solid {el['line']}"
            cls = "e badge" + (" shd" if el.get("shadow") else "")
            parts.append(f'<div class="{cls} {role}" style="{style}"{attrs}>{html.escape(el.get("text", ""))}</div>')
        elif t == "arrow":
            parts.append(f'<div class="e arrow" style="{box};background:{el["fill"]}"{attrs}></div>')
        elif t == "num":
            fs = el["size"]
            parts.append(f'<div class="e num" style="{box};color:{el["color"]};font-size:calc(var(--u)*{fs / 72 * 100 / S.W:.4f})"'
                         f'{attrs}>{el["text"]}</div>')
        elif t == "answer":
            parts.append(f'<button class="e ans" style="{box};font-size:calc(var(--u)*{24 / 72 * 100 / S.W:.4f})" '
                         f'data-id="{el["id"]}" data-ok="{1 if el["correct"] else 0}"{attrs}>'
                         f'<span>{html.escape(el["text"])}</span></button>')
    return "".join(parts)


def _rgba(hexc, alpha=1.0):
    hexc = hexc.lstrip("#")
    r, g, b = int(hexc[0:2], 16), int(hexc[2:4], 16), int(hexc[4:6], 16)
    return f"rgba({r},{g},{b},{alpha:.3f})" if alpha < 1 else f"#{hexc}"


def _fam(font, bold=False):
    if font == S.GREEK:
        return "font-family:var(--fg);font-weight:700"
    w = {"Nunito Black": 900, "Nunito ExtraBold": 800, "Nunito": 700 if bold else 400}.get(font, 400)
    return f"font-family:var(--f);font-weight:{w}"


# ----------------------------------------------------------------------------- phone portrait (flow)
def rows_html(rows, assets, numbered=False):
    out = []
    for icon, txt in rows or []:
        ic = f'<i class="ic {assets.icon(icon)}"></i>' if not numbered else f'<i class="nb">{icon}</i>'
        out.append(f'<li class="fi">{ic}<span>{md(txt)}</span></li>')
    return f'<ul class="rows">{"".join(out)}</ul>' if out else ""


def flow_html(sm, assets: Assets) -> str:
    f = sm.flow
    k = f.get("kind", "art")
    kick = f'<span class="kick fi">{md(f["kicker"])}</span>' if f.get("kicker") else ""
    title = f'<h2 class="fi">{md(f["title"])}</h2>' if f.get("title") else ""
    lead = f'<p class="lead fi">{md(f["lead"])}</p>' if f.get("lead") else ""
    owl = ""
    if f.get("owl"):
        owl = (f'<div class="fowl fi"><i class="{assets.icon("owl")}"></i><p>{md(f["owl"])}</p></div>')
    if k == "cover":
        a = assets.cls(S.A / "art" / f"{f['art']}.jpg")
        return (f'<div class="fl cover {a}"><div class="shade"></div><div class="in">{kick}'
                f'<h1 class="fi">Как появилась<br>Древняя Греция</h1><i class="mband gold fi"></i><p class="sub fi">{md(f["lead"])}</p>'
                f'{owl}<p class="hint fi">Листай дальше →</p></div></div>')
    if k == "map":
        mp = assets.cls(S.A / "maps" / f"{f['map']}.png", prefer_webp=False)  # same file as the 16:9 stage
        extra = rows_html(f.get("rows"), assets)
        pin = ""
        if f.get("pin"):
            px, py, label = f["pin"]
            pin = (f'<b class="mpin" style="left:{px * 100:.1f}%;top:{py * 100:.1f}%"><i class="{assets.icon("pin")}"></i>'
                   f'<span>{html.escape(label)}</span></b>')
        ratio = {"aegean": "1200/984", "colonies": "1600/850"}.get(f["map"], "4/3")
        zh = ('<span class="zhint"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">'
              '<circle cx="10" cy="10" r="7"/><path d="M15 15l6 6M10 7v6M7 10h6"/></svg>Увеличить</span>')
        return (f'<div class="fl"><div class="fimg map {mp}" data-zoom="{mp}" style="aspect-ratio:{ratio}">{pin}{zh}</div>'
                f'<div class="fcard">{kick}{title}{lead}{extra}{owl}</div></div>')
    if k == "timeline":
        eras = "".join(
            f'<li class="fi"><i class="ic {assets.icon(ic)}"></i><div><span class="d">{html.escape(d)}</span>'
            f'<b>{html.escape(n)}</b><small>{html.escape(ds)}</small></div></li>' for ic, d, n, ds in f["eras"])
        return (f'<div class="fl solid"><i class="mband top"></i><div class="fcard plain">{kick}{title}{lead}'
                f'<ol class="tl">{eras}</ol>{owl}</div></div>')
    if k == "alphabet":
        tiles = "".join(f'<div class="tile fi"><span class="gr">{g}</span><em>→</em><b>{r}</b></div>' for g, r in f["pairs"])
        return (f'<div class="fl dark"><i class="mband gold top"></i><div class="fcard plain">{kick}{title}{lead}'
                f'{rows_html(f["rows"], assets)}<div class="tiles">{tiles}</div>{owl}</div></div>')
    if k == "polis":
        a = assets.cls(S.A / "art" / f"{sm.flow['art']}.jpg")
        marks = "".join(f'<b class="mk" style="left:{x * 100:.1f}%;top:{y * 100:.1f}%">{i + 1}</b>'
                        for i, (x, y) in enumerate(f["markers"]))
        return (f'<div class="fl"><div class="fimg tall {a}">{marks}</div>'
                f'<div class="fcard">{kick}{title}{lead}{rows_html(f["legend"], assets, numbered=True)}{owl}</div></div>')
    if k == "quiz":
        letters = "АБВ"
        answers = "".join(
            f'<button class="fans fi" data-ok="{1 if i == f["correct"] else 0}"><i>{letters[i]}</i><span>{html.escape(a)}</span>'
            f'<em></em></button>' for i, a in enumerate(f["answers"]))
        return (f'<div class="fl solid quiz"><i class="mband top"></i><div class="fcard plain">{kick}'
                f'<div class="qhead fi"><i class="{assets.icon("question")}"></i></div>{title}'
                f'<div class="answers">{answers}</div><p class="explain">{md(f["explain"])}</p>{owl}</div></div>')
    if k == "summary":
        items = "".join(f'<li class="fi"><i class="ic {assets.icon(ic)}"></i><span>{md(t)}</span></li>'
                        for ic, t in f["items"])
        return (f'<div class="fl solid"><i class="mband top"></i><div class="fcard plain">{kick}{title}'
                f'<ul class="sum">{items}</ul>{owl}</div></div>')
    if k == "final":
        a = assets.cls(S.A / "art" / f"{f['art']}.jpg")
        return (f'<div class="fl cover final {a}"><div class="shade"></div><div class="in">'
                f'<h1 class="fi">{md(f["title"])}</h1><p class="greek gr fi">{html.escape(f["greek"])}</p>'
                f'<p class="sub2 fi">{md(f["lead"])}</p><div class="qcard fi"><b>{md(f["question"])}</b>'
                f'<small>{md(f["hint"])}</small></div>{owl}<button class="restart fi" data-go="0">↺ Сначала</button></div></div>')
    if k == "credits":
        return (f'<div class="fl solid"><i class="mband top"></i><div class="fcard plain">{title}{rows_html(f["rows"], assets)}'
                f'</div></div>')
    # default: art + card
    a = assets.cls(S.A / "art" / f"{f['art']}.jpg")
    fx, fy = f.get("focus", (0.5, 0.5))
    photo = ""
    if f.get("photo"):
        pk = assets.cls(S.A / f["photo"]["src"])
        photo = (f'<figure class="fphoto fi"><i class="{pk}"></i>'
                 f'<figcaption>{html.escape(f["photo"]["caption"])}</figcaption></figure>')
    dark = " dark" if f.get("dark") else ""
    return (f'<div class="fl{dark}"><div class="fimg {a}" style="background-position:{fx * 100:.0f}% {fy * 100:.0f}%"></div>'
            f'<div class="fcard">{kick}{title}{lead}{rows_html(f.get("rows"), assets)}{photo}{owl}</div></div>')


# ----------------------------------------------------------------------------- page
CSS = r"""
@font-face{font-family:Nunito;src:url(var(--x)) format("woff2");font-weight:200 1000}
:root{--navy:#0E2A47;--ink:#1D2433;--muted:#5B6475;--terra:#C8553D;--gold:#F2B134;--cream:#FFFAF1;--sand:#FFF4E2;
 --turq:#0E8794;--f:Nunito,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;--fg:Comfortaa,Nunito,sans-serif}
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%;background:#0b1626;color:var(--ink);font-family:var(--f);-webkit-tap-highlight-color:transparent;
 overscroll-behavior:none}
body{overflow:hidden;touch-action:pan-y pinch-zoom}
#bar,#nav,.arw,#fs,#count{transition:opacity .4s}
@media (orientation:landscape),(min-width:821px){.idle .arw,.idle #fs,.idle #count{opacity:0;pointer-events:none}.idle{cursor:none}}
#zoom{position:fixed;inset:0;z-index:50;background:rgba(11,22,38,.96);display:none;overflow:auto;-webkit-overflow-scrolling:touch}
#zoom.on{display:block}#zoom img{display:block;height:88vh;width:auto;max-width:none;margin:6vh 0 0}
#zoom button{position:fixed;right:14px;top:14px;width:44px;height:44px;border-radius:50%;border:0;background:#fff;color:var(--navy);
 font:900 22px var(--f);box-shadow:0 4px 16px rgba(0,0,0,.4)}
#zoom p{position:fixed;left:0;right:0;bottom:18px;text-align:center;color:#fff;font:700 14px var(--f);opacity:.8}
b{font-weight:800}.acc{color:var(--terra)}.gr{font-family:var(--fg);font-weight:700}
#deck{position:fixed;inset:0;overflow:hidden}
.slide{position:absolute;inset:0;display:none;align-items:center;justify-content:center}
.slide.on{display:flex;z-index:2;animation:sIn .55s cubic-bezier(.2,.7,.2,1) both}
.slide.out{display:flex;z-index:1;animation:sOut .45s ease both;pointer-events:none}
.slide.on.back{animation-name:sInB}.slide.out.back{animation-name:sOutB}
@keyframes sIn{from{opacity:0;transform:translateX(5%)}to{opacity:1;transform:none}}
@keyframes sInB{from{opacity:0;transform:translateX(-5%)}to{opacity:1;transform:none}}
@keyframes sOut{to{opacity:0;transform:translateX(-5%)}}
@keyframes sOutB{to{opacity:0;transform:translateX(5%)}}
.slide.on.done,.static .slide.on{animation:none}
/* ---------- 16:9 stage */
.stage{position:relative;width:var(--sw);height:calc(var(--sw)*0.5625);--u:calc(var(--sw)/100);overflow:hidden;
 background:var(--bg,#FFF4E2);box-shadow:0 20px 60px rgba(0,0,0,.45);border-radius:calc(var(--u)*.6)}
.e{position:absolute;transform:rotate(var(--r,0deg))}
.pic{background-position:center;background-size:cover;background-repeat:no-repeat}.pic.contain{background-size:contain}
.shd{box-shadow:0 calc(var(--u)*.35) calc(var(--u)*1.6) rgba(14,42,71,.28)}
.photo{box-shadow:0 calc(var(--u)*.5) calc(var(--u)*1.8) rgba(0,0,0,.38)}
.txt{display:flex;flex-direction:column;padding:0 calc(var(--u)*.3);overflow:visible}
.chip{display:flex;align-items:center;justify-content:center;border-radius:999px;font-weight:800;white-space:nowrap}
.bub{background:#fff;border-radius:calc(var(--u)*1.6);display:flex;align-items:center;padding:0 calc(var(--u)*1.2);
 color:var(--navy);line-height:1.25;box-shadow:0 calc(var(--u)*.3) calc(var(--u)*1.2) rgba(0,0,0,.22)}
.bub:after{content:"";position:absolute;width:calc(var(--u)*1.6);height:calc(var(--u)*1.6);background:#fff;
 transform:rotate(45deg);border-radius:calc(var(--u)*.2)}
.bub.tail-l:after{left:calc(var(--u)*-.6);top:calc(var(--ty) - var(--u)*.8)}
.bub.tail-r:after{right:calc(var(--u)*-.6);top:calc(var(--ty) - var(--u)*.8)}
.bub.tail-t:after{top:calc(var(--u)*-.6);left:calc(var(--tx) - var(--u)*.8)}
.bub.tail-b:after{bottom:calc(var(--u)*-.6);left:calc(var(--tx) - var(--u)*.8)}
.mea{background-position:left center;background-size:auto 100%;background-repeat:repeat-x}
.badge{border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:900}
.arrow{clip-path:polygon(0 0,100% 50%,0 100%)}
.num{display:flex;align-items:center;justify-content:center;font-weight:900}
.ans{border:calc(var(--u)*.11) solid #E2D6C3;background:#fff;border-radius:999px;font:800 1em var(--f);color:var(--ink);
 text-align:left;padding-left:calc(var(--u)*7.4);cursor:pointer;box-shadow:0 calc(var(--u)*.3) calc(var(--u)*1.2) rgba(0,0,0,.14);
 transition:transform .15s,background .3s,border-color .3s}
.ans:hover{transform:scale(1.015)}.ans.right{background:#E3F4E8;border-color:#2E9E5B}.ans.wrong{background:#FDE8E4;border-color:#C8553D}
.stage [data-trig],.stage [data-fb]{opacity:0;transform:scale(.6);transition:opacity .35s,transform .35s cubic-bezier(.3,1.6,.5,1)}
.stage .shown{opacity:1!important;transform:none!important}
/* build animations */
.stage [data-eff]:not([data-trig]){opacity:0}
.slide.play .stage [data-eff]:not([data-trig]){animation:var(--anim) var(--dur) cubic-bezier(.2,.7,.2,1) var(--at) both}
@keyframes fade{from{opacity:0}to{opacity:1}}
@keyframes zoom{from{opacity:0;transform:rotate(var(--r,0deg)) scale(.5)}to{opacity:1;transform:rotate(var(--r,0deg)) scale(1)}}
@keyframes flyL{from{opacity:0;transform:translateX(-30%)}to{opacity:1;transform:none}}
@keyframes flyR{from{opacity:0;transform:translateX(30%)}to{opacity:1;transform:none}}
@keyframes flyB{from{opacity:0;transform:translateY(40%)}to{opacity:1;transform:none}}
@keyframes flyT{from{opacity:0;transform:translateY(-60%)}to{opacity:1;transform:none}}
@keyframes wipe{from{opacity:1;clip-path:inset(0 100% 0 0)}to{opacity:1;clip-path:inset(0 0 0 0)}}
.static .stage [data-eff]:not([data-trig]),.slide.done .stage [data-eff]:not([data-trig]){animation:none!important;opacity:1!important}
.slide.kb .pic.art{animation:kb 14s ease-out both}
@keyframes kb{from{transform:scale(1.06)}to{transform:scale(1)}}
.static .slide .pic.art{animation:none!important}
/* ---------- chrome */
#bar{position:fixed;left:0;top:0;height:4px;background:linear-gradient(90deg,#F2B134,#C8553D);z-index:20;transition:width .4s}
#nav{position:fixed;left:50%;bottom:max(10px,env(safe-area-inset-bottom));transform:translateX(-50%);display:flex;gap:6px;z-index:20;
 padding:7px 10px;border-radius:99px;background:rgba(11,22,38,.55);backdrop-filter:blur(8px)}
#nav button{width:8px;height:8px;border-radius:50%;border:0;background:rgba(255,255,255,.45);cursor:pointer;padding:0;transition:all .3s}
#nav button.on{width:22px;border-radius:5px;background:#F2B134}
.arw{position:fixed;top:50%;transform:translateY(-50%);z-index:20;width:52px;height:52px;border-radius:50%;border:0;
 background:rgba(255,255,255,.14);color:#fff;font-size:26px;cursor:pointer;backdrop-filter:blur(6px);transition:background .2s}
.arw:hover{background:rgba(255,255,255,.3)}#prev{left:14px}#next{right:14px}
#fs{position:fixed;right:12px;top:12px;z-index:20;border:0;background:rgba(11,22,38,.5);color:#fff;border-radius:10px;
 width:38px;height:34px;display:flex;align-items:center;justify-content:center;cursor:pointer}#fs svg{width:18px;height:18px}
#count{position:fixed;left:14px;top:12px;z-index:20;color:rgba(255,255,255,.75);font:800 13px var(--f);
 background:rgba(11,22,38,.5);padding:6px 10px;border-radius:10px}
.flow{display:none}
/* ---------- phone portrait layout */
@media (orientation:portrait) and (max-width:820px){
 .stage{display:none}.flow{display:block}.arw{display:none}
 .slide{align-items:stretch;justify-content:stretch}
 .fl{position:absolute;inset:0;overflow-y:auto;overflow-x:hidden;background-color:var(--cream);-webkit-overflow-scrolling:touch;
  padding-bottom:70px;scrollbar-width:none}
 .fl::-webkit-scrollbar{display:none}
 .fl.solid{background-color:var(--sand)}.fl.dark{background-color:var(--navy);color:#fff}
 .fimg{height:44vh;min-height:250px;background-position:center;background-size:cover;background-repeat:no-repeat;position:relative}
 .fimg.tall{height:auto;aspect-ratio:1376/768;min-height:0;background-size:cover}
 .fimg.map{height:auto;min-height:0;background-size:contain;background-color:#BDE7F2}
 .fimg.map+.fcard,.fimg.tall+.fcard{margin-top:12px}
 .fimg.map{cursor:zoom-in}
 .zhint{position:absolute;right:10px;bottom:10px;background:rgba(14,42,71,.82);color:#fff;font:800 12px var(--f);padding:6px 10px;
  border-radius:99px;display:flex;gap:5px;align-items:center}.zhint svg{width:14px;height:14px}
 .mpin{position:absolute;display:flex;align-items:center;gap:4px;transform:translate(-50%,-100%)}
 .mpin i{width:34px;height:34px;background-size:contain;background-repeat:no-repeat;animation:bob 1.4s ease-in-out infinite}
 .mpin span{position:absolute;right:100%;top:2px;white-space:nowrap;background:var(--terra);color:#fff;font:800 12px var(--f);
  padding:4px 9px;border-radius:99px;margin-right:4px}
 @keyframes bob{50%{transform:translateY(-5px)}}
 .fimg:after{content:"";position:absolute;left:0;right:0;bottom:-1px;height:40px;background:linear-gradient(transparent,var(--cream))}
 .dark .fimg:after{background:linear-gradient(transparent,var(--navy))}
 .fimg.map:after,.fimg.tall:after{display:none}
 .fcard{position:relative;margin:-26px 14px 0;background:#fff;border-radius:22px;padding:20px 18px 18px;
  box-shadow:0 10px 30px rgba(14,42,71,.14)}
 .dark .fcard{background:#16365A;box-shadow:none}
 .fcard.plain{margin:0;background:none;box-shadow:none;padding:30px 18px 10px}
 .kick{display:inline-block;background:var(--terra);color:#fff;font-weight:800;font-size:13px;padding:5px 12px;border-radius:99px}
 .dark .kick{background:var(--gold);color:var(--navy)}
 h2{font-weight:900;font-size:clamp(25px,7.4vw,31px);line-height:1.12;color:var(--navy);margin:10px 0 8px}
 .dark h2{color:#fff}
 .lead{font-size:17px;line-height:1.45;margin-bottom:10px}
 .rows{list-style:none;display:grid;gap:12px;margin:12px 0 4px}
 .rows li{display:grid;grid-template-columns:44px 1fr;gap:12px;align-items:center;font-size:16px;line-height:1.4}
 .ic{display:block;width:44px;height:44px;background-position:center;background-size:contain;background-repeat:no-repeat}
 .nb{display:flex;width:34px;height:34px;margin:0 5px;border-radius:50%;background:var(--terra);color:#fff;font:900 17px var(--f);
  align-items:center;justify-content:center;font-style:normal}
 .fowl{display:grid;grid-template-columns:62px 1fr;gap:10px;align-items:center;margin-top:16px}
 .fowl i{width:62px;height:62px;background-position:center;background-size:contain;background-repeat:no-repeat}
 .fowl p{position:relative;background:var(--sand);border-radius:16px;padding:10px 13px;font-size:15px;line-height:1.38;color:var(--navy)}
 .dark .fowl p,.solid .fowl p,.plain .fowl p{background:#fff;box-shadow:0 4px 14px rgba(14,42,71,.1)}
 .fowl p:before{content:"";position:absolute;left:-7px;top:50%;width:14px;height:14px;background:inherit;transform:translateY(-50%) rotate(45deg);border-radius:2px}
 .fphoto{margin:16px 0 4px;text-align:center}
 .fphoto i{display:block;height:190px;background-position:center;background-size:contain;background-repeat:no-repeat}
 .fphoto figcaption{display:inline-block;margin-top:8px;background:var(--navy);color:#fff;font-weight:800;font-size:13px;padding:5px 12px;border-radius:99px}
 .mband{display:block;height:14px;background-position:left center;background-size:auto 100%;background-repeat:repeat-x}
 .mband.top{position:sticky;top:0;z-index:2}
 .cover,.final{background-position:62% bottom;background-size:cover;background-repeat:no-repeat;color:#fff;display:flex}
 /* text sits in the sky (top), the bright harbour illustration stays visible at the bottom */
 .cover .shade{position:absolute;inset:0;background:linear-gradient(180deg,rgba(14,42,71,.92) 0%,rgba(14,42,71,.78) 42%,
  rgba(14,42,71,.25) 66%,rgba(14,42,71,0) 80%,rgba(14,42,71,.35) 100%)}
 .final .shade{background:linear-gradient(180deg,rgba(14,42,71,.92) 0%,rgba(14,42,71,.8) 55%,rgba(14,42,71,.2) 78%,rgba(14,42,71,.35) 100%)}
 .cover .in{position:relative;margin:0;padding:max(34px,env(safe-area-inset-top)) 22px 120px;width:100%}
 .cover .kick{background:var(--gold);color:var(--navy)}
 .cover h1{font-weight:900;font-size:clamp(36px,11vw,48px);line-height:1.02;margin:14px 0 14px}
 .cover .mband{width:70%;margin-bottom:14px}
 .cover .sub{font-weight:800;font-size:20px;color:#FFE1A1}
 .cover .fowl p{background:#fff}
 .hint{margin-top:22px;font-size:14px;opacity:.8;font-weight:700;animation:nudge 1.6s ease-in-out infinite}
 @keyframes nudge{50%{transform:translateX(8px)}}
 .final h1{font-size:clamp(30px,9vw,40px)}
 .greek{font-size:34px;color:var(--gold);margin:6px 0 4px}
 .sub2{font-size:15px;opacity:.9}
 .qcard{background:var(--cream);color:var(--navy);border-radius:18px;padding:14px 16px;margin-top:18px;display:grid;gap:6px}
 .qcard b{font-size:18px;line-height:1.3}.qcard small{font-size:14px;color:var(--muted)}
 .restart{margin-top:18px;border:0;background:var(--gold);color:var(--navy);font:900 16px var(--f);padding:12px 20px;border-radius:99px}
 .tl{list-style:none;display:grid;gap:12px;margin:14px 0 4px;position:relative}
 .tl:before{content:"";position:absolute;left:21px;top:10px;bottom:10px;width:4px;border-radius:2px;background:var(--terra)}
 .tl li{display:grid;grid-template-columns:46px 1fr;gap:12px;align-items:center;position:relative}
 .tl li .ic{background-color:#fff;border-radius:50%;box-shadow:0 0 0 4px var(--sand);background-size:70%}
 .tl li div{background:#fff;border-radius:16px;padding:10px 14px;box-shadow:0 4px 14px rgba(14,42,71,.08)}
 .tl .d{display:inline-block;background:var(--terra);color:#fff;font-weight:800;font-size:12px;padding:3px 9px;border-radius:99px}
 .tl b{display:block;font-weight:900;font-size:18px;color:var(--navy);margin-top:4px}.tl small{font-size:14px;color:var(--muted)}
 .tiles{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:16px 0 6px}
 .tile{display:flex;align-items:center;justify-content:space-around;border:1.5px solid var(--gold);border-radius:14px;padding:8px;background:rgba(255,255,255,.06)}
 .tile .gr{font-size:34px;color:var(--gold)}.tile em{color:#8FA6C1;font-style:normal;font-size:20px}.tile b{font-weight:900;font-size:32px}
 .fimg .mk{position:absolute;width:30px;height:30px;margin:-15px 0 0 -15px;border-radius:50%;background:var(--terra);color:#fff;
  border:2.5px solid #fff;font:900 15px var(--f);display:flex;align-items:center;justify-content:center;box-shadow:0 3px 8px rgba(0,0,0,.3)}
 .quiz .qhead{float:right;width:64px;height:64px;margin:-6px -4px 0 8px}.quiz .qhead i{display:block;width:100%;height:100%;background-position:center;background-size:contain;background-repeat:no-repeat}
 .answers{display:grid;gap:11px;margin:16px 0 8px;clear:both}
 .fans{display:grid;grid-template-columns:38px 1fr 30px;gap:12px;align-items:center;text-align:left;width:100%;border:2px solid #E2D6C3;
  background:#fff;border-radius:18px;padding:12px 12px;font:800 18px var(--f);color:var(--ink);transition:all .25s}
 .fans i{display:flex;width:38px;height:38px;border-radius:50%;background:var(--navy);color:#fff;font:900 17px var(--f);font-style:normal;
  align-items:center;justify-content:center}
 .fans em{width:30px;height:30px;background-position:center;background-size:contain;background-repeat:no-repeat;opacity:0;transform:scale(.4);transition:all .35s cubic-bezier(.3,1.6,.5,1)}
 .fans.right{background:#E3F4E8;border-color:#2E9E5B}.fans.right em{opacity:1;transform:none}
 .fans.wrong{background:#FDE8E4;border-color:#C8553D}.fans.wrong em{opacity:1;transform:none}
 .explain{max-height:0;overflow:hidden;opacity:0;transition:all .45s;background:#E3F4E8;border:2px solid #2E9E5B;border-radius:16px;
  color:#14532D;font-size:16px;line-height:1.4;padding:0 14px}
 .explain.shown{max-height:240px;opacity:1;padding:12px 14px}
 .sum{list-style:none;display:grid;gap:10px;margin-top:14px}
 .sum li{display:grid;grid-template-columns:44px 1fr;gap:12px;align-items:center;background:#fff;border-radius:16px;padding:10px 12px;
  font-size:16px;line-height:1.38;box-shadow:0 4px 14px rgba(14,42,71,.08)}
 .slide .fi{opacity:0;transform:translateY(14px)}
 .slide.play .fi{animation:fi .55s cubic-bezier(.2,.7,.2,1) both;animation-delay:calc(var(--i,0)*90ms + 120ms)}
 .static .slide .fi,.slide.done .fi{animation:none!important;opacity:1;transform:none}
 @keyframes fi{to{opacity:1;transform:none}}
 #nav{bottom:max(12px,env(safe-area-inset-bottom))}
 #count{display:none}#fs{display:none}
}
@media (prefers-reduced-motion:reduce){.slide,.slide *{animation:none!important;transition:none!important}
 .stage [data-eff]:not([data-trig]),.slide .fi{opacity:1!important;transform:none!important}}
/* ---------- tablets in portrait: same vertical layout, scaled up (bigger text, no empty half-screen) */
@media (orientation:portrait) and (min-width:600px) and (max-width:820px){.fl{zoom:1.32}}
/* ---------- no JavaScript (iOS Quick Look, in-app previews): all slides stacked, everything visible */
:root{--sw:min(calc(100vw - 56px),calc((100vh - 56px)*1.7778))}
.nojs body{overflow:auto;height:auto}.nojs #deck{position:static}
.nojs .slide{display:flex;position:relative;inset:auto;padding:14px 0}
.nojs .stage{--sw:min(96vw,1400px)}
.nojs .stage [data-eff],.nojs .stage [data-trig],.nojs .stage [data-fb]{opacity:1!important;transform:none!important;animation:none!important}
.nojs #nav,.nojs .arw,.nojs #fs,.nojs #count,.nojs #bar,.nojs .zhint,.nojs .hint{display:none}
@media (orientation:portrait) and (max-width:820px){.nojs .slide{padding:0}.nojs .fl{position:relative;inset:auto;overflow:visible;padding-bottom:28px}
 .nojs .slide .fi{opacity:1;transform:none}.nojs .cover{min-height:92vh}.nojs .explain{max-height:none;opacity:1;padding:12px 14px}
 .nojs .mband.top{position:static}}
@media print{body{overflow:visible;background:#fff}#deck{position:static}.slide{position:relative;visibility:visible;opacity:1;
 page-break-after:always;height:100vh}#nav,.arw,#bar,#fs,#count{display:none}.stage{box-shadow:none}
 .stage [data-eff]{opacity:1!important;animation:none!important}}
"""

JS = r"""
(()=>{
document.documentElement.classList.remove('nojs');
const q=new URLSearchParams(location.search);const STATIC=q.has('static')||q.has('print');
const slides=[...document.querySelectorAll('.slide')];const N=slides.length;let cur=-1;
if(STATIC)document.documentElement.classList.add('static');
const bar=document.getElementById('bar'),nav=document.getElementById('nav'),cnt=document.getElementById('count');
slides.forEach((s,i)=>{const b=document.createElement('button');b.setAttribute('aria-label','Слайд '+(i+1));
 b.onclick=()=>go(i);nav.appendChild(b);
 s.querySelectorAll('.flow .fi').forEach((e,k)=>e.style.setProperty('--i',k));
 s.querySelectorAll('.stage [data-eff]:not([data-trig])').forEach(e=>{const ef=e.dataset.eff,d=e.dataset.dir;
  const n=ef==='fly'?({left:'flyL',right:'flyR',bottom:'flyB',top:'flyT'}[d]||'flyB'):ef==='appear'?'fade':ef;
  e.style.setProperty('--anim',n);e.style.setProperty('--dur',(ef==='appear'?1:+e.dataset.dur)+'ms');
  e.style.setProperty('--at',(+e.dataset.at||0)+'ms');});});
function fit(){const vw=innerWidth,vh=innerHeight;const pad=vw>900?28:0;const w=Math.min(vw-pad*2,(vh-pad*2)*16/9);
 document.documentElement.style.setProperty('--sw',w+'px');}
addEventListener('resize',fit);fit();
/* decode every background image of a slide (so it never flashes empty) */
const decoded=new Set();
function urls(s){const out=new Set();s.querySelectorAll('[class*="A"]').forEach(e=>{const m=/url\("?(.*?)"?\)$/.exec(getComputedStyle(e).backgroundImage);
 if(m&&m[1].startsWith('data:image'))out.add(m[1]);});return [...out];}
function decode(i){if(i<0||i>=N||decoded.has(i))return Promise.resolve();const s=slides[i];const was=s.style.display;
 s.style.display='flex';s.style.visibility='hidden';const list=urls(s);s.style.display=was;s.style.visibility='';decoded.add(i);
 return Promise.all(list.map(u=>{const im=new Image();im.src=u;return im.decode().catch(()=>{});}));}
let outT;
function go(i,o={}){i=Math.max(0,Math.min(N-1,i));if(i===cur&&!o.force)return Promise.resolve();
 const back=i<cur;const old=slides[cur];clearTimeout(outT);
 slides.forEach(s=>s.classList.remove('on','out','back','play','done','kb'));
 const s=slides[i];const instant=o.instant||STATIC;
 if(old&&old!==s&&!instant){old.classList.add('out');if(back)old.classList.add('back');outT=setTimeout(()=>old.classList.remove('out','back'),500);}
 cur=i;s.classList.add('on');if(back&&!instant)s.classList.add('back');
 if(instant){s.classList.add('done');}else{void s.offsetWidth;s.classList.add('play','kb');}
 s.querySelectorAll('.fl').forEach(f=>f.scrollTop=0);
 bar.style.width=((i+1)/N*100)+'%';[...nav.children].forEach((b,k)=>b.classList.toggle('on',k===i));
 cnt.textContent=(i+1)+' / '+N;history.replaceState(null,'','#'+(i+1));
 const p=decode(i);setTimeout(()=>{decode(i+1);decode(i-1);},700);return p;}
function next(){go(cur+1)}function prev(){go(cur-1)}
document.getElementById('next').onclick=next;document.getElementById('prev').onclick=prev;
document.getElementById('fs').onclick=()=>{const d=document.documentElement;
 (document.fullscreenElement?document.exitFullscreen():(d.requestFullscreen||d.webkitRequestFullscreen).call(d)).catch?.(()=>{});};
addEventListener('hashchange',()=>{const n=parseInt(location.hash.slice(1));if(n&&n-1!==cur)go(n-1)});
addEventListener('keydown',e=>{if(e.key==='Escape'&&zoom.classList.contains('on')){zoom.classList.remove('on');return}
 if(['ArrowRight','PageDown',' ','Enter'].includes(e.key)){e.preventDefault();next()}
 else if(['ArrowLeft','PageUp','Backspace'].includes(e.key)){e.preventDefault();prev()}
 else if(e.key==='Home')go(0);else if(e.key==='End')go(N-1);else if(e.key==='f')document.getElementById('fs').click();});
let sx=0,sy=0,st=0,multi=false;const zoom=document.getElementById('zoom');
addEventListener('touchstart',e=>{const t=e.touches[0];sx=t.clientX;sy=t.clientY;st=Date.now();multi=e.touches.length>1},{passive:true});
addEventListener('touchend',e=>{if(multi||zoom.classList.contains('on')||(visualViewport&&visualViewport.scale>1.05))return;
 const t=e.changedTouches[0];const dx=t.clientX-sx,dy=t.clientY-sy;
 if(Math.abs(dx)>50&&Math.abs(dx)>Math.abs(dy)*1.3&&Date.now()-st<900){dx<0?next():prev()}},{passive:true});
/* map lightbox (phone): open the full-resolution SVG map, pan with the finger */
document.querySelectorAll('[data-zoom]').forEach(m=>m.addEventListener('click',e=>{e.stopPropagation();
 const u=/url\("?(.*?)"?\)$/.exec(getComputedStyle(m).backgroundImage);if(!u)return;
 const im=zoom.querySelector('img');im.src=u[1];zoom.classList.add('on');
 requestAnimationFrame(()=>{zoom.scrollLeft=(im.offsetWidth-innerWidth)/2;});}));
zoom.addEventListener('click',e=>{if(e.target.tagName!=='IMG')zoom.classList.remove('on')});
/* hide the presenter chrome when the mouse is idle */
let idleT;const wake=()=>{document.body.classList.remove('idle');clearTimeout(idleT);idleT=setTimeout(()=>document.body.classList.add('idle'),2500)};
addEventListener('mousemove',wake);addEventListener('keydown',wake);if(STATIC)document.body.classList.add('idle');else wake();
/* stage click = next (like a slideshow), except on interactive elements */
document.getElementById('deck').addEventListener('click',e=>{if(e.target.closest('button,.ans,.fans,a,.fl'))return;
 const x=e.clientX/innerWidth;x<0.3?prev():next();});
/* quiz (stage) */
const CHEER=['Молодец! Так держать!','Верно! Ты настоящий историк!','Ура! Правильно!'];
const WRONG='Почти! Попробуй ещё раз.';
function owlSay(root,txt){const p=root.querySelector('.bub>div,.fowl p');if(p){p.textContent=txt;p.parentElement.animate(
 [{transform:'scale(.85)'},{transform:'scale(1.06)'},{transform:'scale(1)'}],{duration:450,easing:'ease-out'});}}
document.querySelectorAll('.stage .ans').forEach(b=>b.addEventListener('click',e=>{e.stopPropagation();
 const st=b.closest('.stage');const ok=b.dataset.ok==='1';b.classList.add(ok?'right':'wrong');
 st.querySelectorAll('[data-trig="'+b.dataset.id+'"]').forEach(x=>x.classList.add('shown'));
 if(ok)st.querySelectorAll('[data-fb="'+b.dataset.id+'"]').forEach(x=>x.classList.add('shown'));
 owlSay(st,ok?CHEER[cur%3]:WRONG);}));
/* quiz (phone) */
document.querySelectorAll('.fans').forEach(b=>b.addEventListener('click',e=>{e.stopPropagation();const ok=b.dataset.ok==='1';
 b.classList.add(ok?'right':'wrong');const card=b.closest('.fcard');owlSay(card,ok?CHEER[cur%3]:WRONG);
 if(ok){const ex=card.querySelector('.explain');ex&&ex.classList.add('shown');
 ex&&setTimeout(()=>ex.scrollIntoView({behavior:'smooth',block:'nearest'}),250);}}));
document.querySelectorAll('[data-go]').forEach(b=>b.addEventListener('click',e=>{e.stopPropagation();go(+b.dataset.go)}));
/* contract for the screenshot tools */
window.DECK={get count(){return N},get index(){return cur},go:(i,o={})=>go(i,{...o,force:true}).then(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))),
 replay(){go(cur,{force:true})},
 revealAll(){document.querySelectorAll('.stage [data-trig],.stage [data-fb],.explain').forEach(x=>x.classList.add('shown'))},
 audit(){const out=[];const s=slides[cur];const vis=[...s.querySelectorAll('.stage,.flow')].find(x=>x.offsetParent!==null||getComputedStyle(x).display!=='none');
  if(!vis)return out;const R=vis.getBoundingClientRect();
  vis.querySelectorAll('.txt>div,.bub>div,.chip,h1,h2,p,li,.ans span,.fans').forEach(el=>{const p=el.closest('.e')||el;
   const r=el.getBoundingClientRect();if(!r.width)return;
   if(el.parentElement.classList.contains('txt')||el.parentElement.classList.contains('bub')){const pr=el.parentElement.getBoundingClientRect();
    if(r.height>pr.height*1.08+2)out.push('переполнение: «'+el.textContent.slice(0,40)+'» '+Math.round(r.height)+'>'+Math.round(pr.height)+'px');}
   if(el.classList.contains('chip')&&el.scrollWidth>el.clientWidth+2)out.push('чип не помещается: «'+el.textContent.slice(0,30)+'»');
   if(vis.classList.contains('stage')&&(r.right>R.right+2||r.bottom>R.bottom+2||r.left<R.left-2))out.push('за краем слайда: «'+el.textContent.slice(0,40)+'»');
   if(vis.classList.contains('flow')&&(r.right>innerWidth+1||r.left<-1))out.push('за краем экрана: «'+el.textContent.slice(0,40)+'»');});
  return out;}};
const h=parseInt((location.hash||'').slice(1))||parseInt(q.get('slide'))||1;go(h-1,{instant:STATIC});
})();
"""


def render(slides: list, out: Path) -> dict:
    assets = Assets()
    # fonts
    fonts_css = []
    nk = assets.key(S.A / "fonts" / "nunito.woff2", prefer_webp=False)
    ck = assets.key(S.A / "fonts" / "comfortaa.woff2", prefer_webp=False)
    mt = assets.key(S.A / "meander.png", prefer_webp=False)
    mg = assets.key(S.A / "meander_gold.png", prefer_webp=False)
    ok_k, no_k = assets.key(S.A / "icons" / "check.png"), assets.key(S.A / "icons" / "cross.png")
    for ic in ("owl", "question", "pin"):
        assets.key(S.A / "icons" / f"{ic}.png")
    body = []
    for i, sm in enumerate(slides):
        st = stage_html(sm, assets)
        fl = flow_html(sm, assets)
        bg = f"--bg:{sm.bg}" if sm.bg else ""
        body.append(f'<section class="slide" aria-label="{html.escape(sm.title)}" data-key="{sm.key}">'
                    f'<div class="stage" style="{bg}">{st}</div><div class="flow">{fl}</div></section>')
    vars_css = (assets.css() + f".mband{{background-image:url({assets.items[mt]})}}"
                f".mband.gold{{background-image:url({assets.items[mg]})}}"
                f".fans.right em{{background-image:url({assets.items[ok_k]})}}.fans.wrong em{{background-image:url({assets.items[no_k]})}}")
    # @font-face can't use var() → write real urls
    face = (f'@font-face{{font-family:Nunito;src:url({assets.items[nk]}) format("woff2");font-weight:200 1000;font-display:block}}'
            f'@font-face{{font-family:Comfortaa;src:url({assets.items[ck]}) format("woff2");font-weight:300 700;font-display:block}}')
    css = CSS.replace('@font-face{font-family:Nunito;src:url(var(--x)) format("woff2");font-weight:200 1000}\n', "")
    doc = f"""<!doctype html>
<html lang="ru" class="nojs"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#0E2A47"><meta name="generator" content="pptkit-deck"><meta name="apple-mobile-web-app-capable" content="yes">
<title>Как появилась Древняя Греция — презентация для детей</title>
<meta name="description" content="Интерактивная презентация для детей: Крит, Микены, Троя, Гомер, алфавит, полисы и первые Олимпийские игры.">
<style>{face}{vars_css}{css}</style></head>
<body><div id="bar"></div><div id="count"></div><button id="fs" aria-label="Во весь экран" title="Во весь экран (F)">
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round"><path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/></svg></button>
<div id="zoom" role="dialog" aria-label="Карта"><img alt="Карта"><button aria-label="Закрыть">✕</button><p>Двигай карту пальцем</p></div>
<main id="deck">{''.join(body)}</main>
<button class="arw" id="prev" aria-label="Назад">‹</button><button class="arw" id="next" aria-label="Вперёд">›</button>
<nav id="nav"></nav>
<script>{JS}</script></body></html>"""
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(doc, encoding="utf-8")
    return {"kb": round(out.stat().st_size / 1024, 1), "assets": len(assets.items)}
