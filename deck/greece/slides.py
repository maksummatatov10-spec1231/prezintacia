"""Content + layout of the deck «Как появилась Древняя Греция» (for kids, in Russian).

One source of truth → two renderers:
  * every slide is a list of positioned elements (inches on a 13.333×7.5 slide) — rendered 1:1 to
    PPTX (render_pptx.py) and to the HTML "stage" (render_html.py, desktop / landscape);
  * plus a `flow` description used by the HTML phone-portrait layout.

Markup inside texts: **bold**, __accent__, {{Ελληνικά}} = Greek font (Comfortaa).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from pptkit import env  # noqa: E402

env.EXTRA_FONT_DIRS.insert(0, HERE / "assets" / "fonts")

from pptkit.lint import _font_path, _pil_font, estimate_text_height  # noqa: E402

A = HERE / "assets"
W, H = 13.333, 7.5
M = 0.55

NAVY, INK, MUTED = "#0E2A47", "#1D2433", "#5B6475"
TERRA, TERRA_DK, GOLD = "#C8553D", "#9E3B27", "#F2B134"
CREAM, SAND, WHITE = "#FFFAF1", "#FFF4E2", "#FFFFFF"
TURQ, BLUE, OLIVE, GREEN = "#0E8794", "#1667A8", "#6E8B3D", "#2E9E5B"
TITLE, BODY, XB, GREEK = "Nunito Black", "Nunito", "Nunito ExtraBold", "Comfortaa"

_MARK = re.compile(r"\*\*(.+?)\*\*|__(.+?)__|\{\{(.+?)\}\}")


def plain(t: str) -> str:
    return _MARK.sub(lambda m: m.group(1) or m.group(2) or m.group(3), t)


def measure(text, size, width, font=BODY, bold=False, ls=1.0, inset=(0.04, 0.02)) -> float:
    paras = plain(text).split("\n")
    h = estimate_text_height([(p, size, font, bold) for p in paras], int((width - 2 * inset[0]) * 914400), ls)
    return h / 914400 + 2 * inset[1]


def text_w(text, size, font=XB, bold=False) -> float:
    f = _pil_font(_font_path(font, bold), int(size * 4))
    return f.getlength(plain(text)) / 4 / 72


def an(effect="fade", start="after", delay=0, dur=450, **kw):
    return {"effect": effect, "start": start, "delay": delay, "dur": dur, **kw}


def img(rel: str) -> Path:
    p = A / rel
    if p.suffix == "":
        for ext in (".jpg", ".png"):
            if (A / (rel + ext)).exists():
                return A / (rel + ext)
    return p


class S:
    """One slide."""

    def __init__(self, key, title, notes, transition=("fade", 800), bg=None):
        self.key, self.title, self.notes, self.transition, self.bg = key, title, notes, transition, bg
        self.els: list[dict] = []
        self.flow: dict = {"kind": "art"}

    def add(self, type_, anim=None, **kw):
        el = {"type": type_, "anim": anim, **kw}
        self.els.append(el)
        return el

    def pic(self, src, x, y, w, h, anim=None, **kw):
        return self.add("pic", anim, src=str(img(src)), x=x, y=y, w=w, h=h, **kw)

    def rect(self, x, y, w, h, anim=None, **kw):
        return self.add("rect", anim, x=x, y=y, w=w, h=h, **kw)

    def text(self, x, y, w, h, text, anim=None, **kw):
        return self.add("text", anim, x=x, y=y, w=w, h=h, text=text, **kw)

    def chip(self, x, y, text, anim=None, fill=TERRA, color=WHITE, size=15, font=XB, **kw):
        hh = size / 72 * 1.8
        ww = text_w(text, size, font) + 0.42
        return self.add("chip", anim, x=x, y=y, w=ww, h=hh, text=text, fill=fill, color=color, size=size,
                        font=font, **kw)

    def bubble(self, x, y, w, h, text, tip, anim=None, size=16, **kw):
        return self.add("bubble", anim, x=x, y=y, w=w, h=h, text=text, tip=tip, size=size, **kw)

    def meander(self, x, y, w, h, color="terra", anim=None):
        return self.add("meander", anim, x=x, y=y, w=w, h=h, color=color)


# ----------------------------------------------------------------------------- reusable blocks
def card(s: S, x, y, w, kicker=None, title=None, lead=None, rows=None, title_size=34, lead_size=19,
         row_size=18, pad=0.36, fill=CREAM, alpha=0.95, dark=False, align_bottom=False, kicker_fill=TERRA,
         row_icon=0.6, min_h=0.0, number_rows=False, anim_rows=True):
    """Text card with optional kicker chip, title, lead and icon rows. Returns the card box.
    Auto-fit: if the card would run off the slide, text shrinks step by step (never below 16 pt) and the
    vertical gaps tighten — so a long text never gets clipped."""
    cw = w - 2 * pad
    tcol = WHITE if dark else NAVY
    bcol = "#E9EEF5" if dark else INK
    rows = rows or []
    avail = H - M * 0.6 - (M if align_bottom else y)

    def layout(ls, rs, ts, gap):
        parts, cy = [], 0.0
        if kicker:
            parts.append(("kicker", cy, 0.4))
            cy += 0.4 + 0.16
        if title:
            th = measure(title, ts, cw, TITLE)
            parts.append(("title", cy, th))
            cy += th + 0.08
        if lead:
            lh = measure(lead, ls, cw, BODY)
            parts.append(("lead", cy, lh))
            cy += lh + gap + 0.02
        for icon, txt in rows:
            rh = measure(txt, rs, cw - row_icon - 0.18, BODY)
            hh = max(row_icon, rh)
            parts.append(("row", cy, hh))
            cy += hh + gap
        return parts, max(min_h, cy - (gap if rows else gap + 0.02 if lead else 0.08) + 2 * pad)

    for k in range(8):
        ls, rs = max(16, lead_size - k * 0.5), max(16, row_size - k * 0.5)
        ts = max(28, title_size - k)
        gap = max(0.08, 0.14 - k * 0.01)
        parts, h = layout(ls, rs, ts, gap)
        if h <= avail:
            break
    lead_size, row_size, title_size = ls, rs, ts
    if align_bottom:
        y = H - M - h
    s.rect(x, y, w, h, fill=fill, alpha=alpha, radius=0.28, shadow={"blur": 0.3, "dist": 0.06, "alpha": 0.28},
           anim=an("fade", "after", 0, 500), role="card")
    ri = 0
    for kind, oy, hh in parts:
        yy = y + pad + oy
        if kind == "kicker":
            s.chip(x + pad, yy, kicker, fill=kicker_fill, anim=an("fade", "with", 150, 400), role="kicker")
        elif kind == "title":
            s.text(x + pad, yy, cw, hh, title, font=TITLE, size=title_size, color=tcol,
                   anim=an("fade", "with", 150, 500), role="title")
        elif kind == "lead":
            s.text(x + pad, yy, cw, hh, lead, size=lead_size, color=bcol, anim=an("fade", "after", 0, 450),
                   role="lead")
        elif kind == "row":
            icon, txt = rows[ri]
            ri += 1
            iy = yy + (hh - row_icon) / 2 if hh > row_icon else yy
            rh = measure(txt, row_size, cw - row_icon - 0.18, BODY)
            ty = yy + (hh - rh) / 2
            if number_rows:
                s.add("badge", an("zoom", "after", 80, 350), x=x + pad + 0.04, y=iy + 0.04, w=row_icon - 0.08,
                      h=row_icon - 0.08, text=str(icon), fill=TERRA, color=WHITE, size=20, role="row-icon")
            else:
                s.pic(f"icons/{icon}.png", x + pad, iy, row_icon, row_icon, fit="contain",
                      anim=an("zoom", "after", 80, 350) if anim_rows else None, role="row-icon")
            s.text(x + pad + row_icon + 0.18, ty, cw - row_icon - 0.18, rh, txt, size=row_size, color=bcol,
                   anim=an("fade", "with", 120, 400) if anim_rows else None, role="row")
    return (x, y, w, h)


def owl(s: S, text, pos="br", bw=4.3, size=16, osz=1.3, icon="owl", dy=0.0):
    """Mascot Afi (owl) + speech bubble. pos: br | bl | tr | tl."""
    bh = max(0.78, measure(text, size, bw - 0.32, BODY, True) + 0.22)
    top = pos.startswith("t")
    oy = (0.38 if top else H - 0.32 - osz) + dy
    if pos.endswith("r"):
        ox = W - M - osz + 0.15
        bx = ox - 0.22 - bw
        tipx = ox + 0.12
    else:
        ox = M - 0.15
        bx = ox + osz + 0.22
        tipx = ox + osz - 0.12
    by = oy + osz * 0.45 - bh / 2
    by = min(max(by, 0.25), H - 0.25 - bh)
    tipy = oy + osz * 0.42
    tip = ((tipx - (bx + bw / 2)) / bw, (tipy - (by + bh / 2)) / bh)
    s.pic(f"icons/{icon}.png", ox, oy, osz, osz, fit="contain", anim=an("zoom", "after", 150, 450), role="owl")
    s.bubble(bx, by, bw, bh, text, tip, size=size, anim=an("fade", "after", 0, 400), role="owl-bubble")
    s.flow["owl"] = text


def full_art(s: S, art, focus=(0.5, 0.5)):
    s.pic(f"art/{art}", 0, 0, W, H, focus=focus, role="art", alt=s.title)
    s.flow.update({"art": art, "focus": focus})


def polaroid(s: S, src, x, y, w, h, caption, rot=0.0, alt=None):
    s.pic(src, x, y, w, h, border=WHITE, border_w=7, shadow={"blur": 0.25, "dist": 0.08, "alpha": 0.35},
          rot=rot, anim=an("zoom", "after", 100, 500), role="photo", alt=alt or caption)
    cw = text_w(caption, 14) + 0.42
    s.chip(x + w / 2 - cw / 2, y + h - 0.22, caption, fill=NAVY, size=14, anim=an("fade", "with", 250, 400),
           role="photo-caption")
    s.flow["photo"] = {"src": src, "caption": caption}


# ----------------------------------------------------------------------------- slides
def build_slides() -> list[S]:
    slides: list[S] = []

    # 1 ── cover ---------------------------------------------------------------------------------
    s = S("cover", "Как появилась Древняя Греция", transition=("curtains", 1600), notes=(
        "Здравствуйте! Сегодня мы отправимся в путешествие на 4000 лет назад и узнаем, как появилась "
        "Древняя Греция. Нашим гидом будет совёнок Афи — сова была священной птицей богини мудрости Афины."))
    full_art(s, "cover", (0.62, 0.5))
    s.rect(0, 0, 8.4, H, gradient=[(0, NAVY, 0.9), (0.5, NAVY, 0.62), (1, NAVY, 0.0)], angle=0, role="shade")
    s.chip(0.85, 1.0, "История для юных исследователей", fill=GOLD, color=NAVY, size=16,
           anim=an("fade", "after", 200, 500))
    s.text(0.78, 1.55, 7.5, 2.3, "Как появилась\nДревняя Греция", font=TITLE, size=60, color=WHITE, ls=0.92,
           anim=an("fly", "after", 0, 700, direction="left"), role="title")
    s.meander(0.86, 3.98, 4.8, 0.26, "gold", anim=an("wipe", "after", 0, 600, direction="left"))
    s.text(0.78, 4.38, 6.8, 0.6, "Путешествие на 4000 лет назад", font=XB, size=27, color="#FFE1A1",
           anim=an("fade", "after", 0, 500), role="subtitle")
    owl(s, "Привет! Я совёнок **Афи** — птица богини Афины. Полетели в прошлое!", pos="bl", bw=4.6, size=17)
    s.flow.update({"kind": "cover", "title": "Как появилась Древняя Греция", "kicker": "История для юных исследователей",
                   "lead": "Путешествие на 4000 лет назад"})
    slides.append(s)

    # 2 ── where is Greece ------------------------------------------------------------------------
    s = S("where", "Где находится Греция?", bg=SAND, transition=("fade", 800), notes=(
        "Покажите на карте Балканский полуостров. Греция окружена морями: Эгейским, Ионическим и Средиземным. "
        "В Греции около 6000 островов и островков, но живут люди только примерно на 227 из них. "
        "Почти 80% территории занимают горы, а до моря отовсюду недалеко."))
    mh = 6.6
    mw = mh * 1200 / 984
    s.pic("maps/aegean.png", 0.45, 0.45, mw, mh, radius=0.3, border=WHITE, border_w=6,
          shadow={"blur": 0.3, "dist": 0.06, "alpha": 0.25}, role="map", alt="Карта Древней Греции",
          anim=an("fade", "after", 0, 600))
    # Europe inset in the bottom-right corner (open sea east of Crete; keeps Troy and Asia Minor visible)
    s.pic("maps/europe.png", 0.45 + mw - 0.28 - 2.3, 0.45 + mh - 0.28 - 2.3 * 405 / 560, 2.3, 2.3 * 405 / 560,
          radius=0.12, border=WHITE, border_w=4,
          shadow={"blur": 0.2, "dist": 0.05, "alpha": 0.3}, role="inset", alt="Греция на карте Европы",
          anim=an("zoom", "after", 0, 450))
    x0 = 0.45 + mw + 0.4
    cw = W - x0 - M
    s.chip(x0, 0.75, "География", fill=TURQ, anim=an("fade", "after", 0, 400))
    th = measure("Где находится Греция?", 36, cw, TITLE)
    s.text(x0, 1.25, cw, th, "Где находится Греция?", font=TITLE, size=36, color=NAVY, anim=an("fade", "with", 100, 500),
           role="title")
    lead = "На юге Европы: **Балканский полуостров** и тысячи островов в тёплых морях."
    lh = measure(lead, 19, cw, BODY)
    y = 1.25 + th + 0.12
    s.text(x0, y, cw, lh, lead, size=19, color=INK, anim=an("fade", "after", 0, 400), role="lead")
    y += lh + 0.3
    facts = [("island", "**≈ 6000** островов и островков"), ("mountain", "**80%** земли — горы"),
             ("sailboat", "До моря отовсюду **рукой подать**")]
    for icon, t in facts:
        rh = measure(t, 19, cw - 0.85, BODY)
        s.rect(x0, y, cw, max(0.82, rh + 0.2), fill=WHITE, radius=0.2, shadow={"blur": 0.15, "dist": 0.03, "alpha": 0.15},
               anim=an("fly", "after", 0, 400, direction="right"), role="fact")
        s.pic(f"icons/{icon}.png", x0 + 0.12, y + (max(0.82, rh + 0.2) - 0.6) / 2, 0.6, 0.6, fit="contain",
              anim=an("zoom", "with", 150, 350))
        s.text(x0 + 0.85, y + (max(0.82, rh + 0.2) - rh) / 2, cw - 0.95, rh, t, size=19, color=INK,
               anim=an("fade", "with", 150, 350))
        y += max(0.82, rh + 0.2) + 0.18
    # pin on Crete instead of the owl (the owl would cover the island)
    kx, ky = 0.45 + mw * (25.163 - 19.3) * 112.17 / 1200, 0.45 + mh * (41.6 - 35.298) * 142.62 / 984
    s.pic("icons/pin.png", kx - 0.3, ky - 0.62, 0.6, 0.6, fit="contain", anim=an("fly", "after", 0, 500, direction="top"),
          role="pin")
    cw2 = text_w("Здесь всё началось!", 15) + 0.42
    s.chip(kx - 0.45 - cw2, ky - 0.62, "Здесь всё началось!", fill=TERRA, size=15, anim=an("fade", "with", 200, 400))
    s.flow["owl"] = "Найди на карте остров **Крит** — с него всё началось!"
    s.flow["pin"] = ((25.163 - 19.3) * 112.17 / 1200, (41.6 - 35.298) * 142.62 / 984, "Здесь всё началось!")
    s.flow.update({"kind": "map", "map": "aegean", "kicker": "География", "title": "Где находится Греция?",
                   "lead": lead, "rows": facts})
    s.flow.pop("owl", None)
    slides.append(s)

    # 3 ── land, sea, islands ---------------------------------------------------------------------
    s = S("land", "Горы, море и острова", transition=("fade", 800), notes=(
        "Природа сильно повлияла на жизнь греков. Плодородных долин мало, поэтому хлеба не хватало. Зато хорошо "
        "росли оливки и виноград. Оливковое масло ели, им заправляли светильники, а спортсмены натирались им "
        "перед состязаниями. Море стало главной дорогой, и греки стали отличными мореходами."))
    full_art(s, "landscape", (0.5, 0.5))
    rows = [("mountain", "В горах добывали **камень** для храмов, **глину** для посуды и **металлы**."),
            ("amphora", "Хлеба не хватало. Зато росли **оливки** и **виноград**."),
            ("sailboat", "Море стало дорогой: греки стали **мореходами** и **торговцами**.")]
    card(s, W - M - 5.6, M, 5.6, kicker="Природа", title="Горы, море и острова",
         lead="Полей в Греции мало, зато гор и моря — сколько угодно!", rows=rows, kicker_fill=OLIVE)
    owl(s, "Оливковым маслом греки заправляли еду, светильники и даже натирались им!", pos="tl", bw=4.4)
    s.flow.update({"kicker": "Природа", "title": "Горы, море и острова",
                   "lead": "Полей в Греции мало, зато гор и моря — сколько угодно!", "rows": rows})
    slides.append(s)

    # 4 ── timeline ---------------------------------------------------------------------------------
    s = S("timeline", "Путешествие во времени", bg=SAND, transition=("push", 800), notes=(
        "Объясните счёт лет до нашей эры: чем больше число, тем раньше это было. Покажите четыре больших периода: "
        "минойский Крит, Микены, Тёмные века и время полисов. От Крита до наших дней — около 4000 лет."))
    s.meander(0, 0.2, W, 0.24, "terra")
    s.meander(0, H - 0.44, W, 0.24, "terra")
    s.chip(M, 0.7, "Лента времени", fill=TERRA, anim=an("fade", "after", 0, 400))
    s.text(M, 1.15, 7.2, 0.8, "Путешествие во времени", font=TITLE, size=38, color=NAVY,
           anim=an("fade", "with", 100, 500), role="title")
    expl = "**до н. э.** — «до нашей эры». Здесь чем **больше** число, тем **раньше** это было!"
    eh = measure(expl, 17, 7.4 - 0.4, BODY)
    s.rect(M, 2.05, 7.4, eh + 0.3, fill=WHITE, radius=0.18, shadow={"blur": 0.12, "dist": 0.03, "alpha": 0.12},
           anim=an("fade", "after", 0, 400))
    s.text(M + 0.2, 2.2, 7.0, eh, expl, size=17, color=INK, anim=an("fade", "with", 0, 400), role="lead")
    ay = 3.42
    s.rect(0.75, ay, W - 1.75, 0.09, fill=TERRA, anim=an("wipe", "after", 0, 900, direction="left"), role="axis")
    s.add("arrow", an("fade", "with", 700, 300), x=W - 1.05, y=ay - 0.17, w=0.36, h=0.43, fill=TERRA)
    s.chip(W - M, 2.72, "сейчас — 2026 год", fill=NAVY, size=14, align="right", anim=an("fade", "with", 800, 300))
    eras = [("dolphin", "2000–1450 до н. э.", "Минойский Крит", "Дворцы, фрески и сильный флот"),
            ("lion", "1600–1200 до н. э.", "Микены", "Крепости ахейцев и Троянская война"),
            ("hourglass", "1100–800 до н. э.", "Тёмные века", "Дворцы разрушены, письменность забыта"),
            ("temple", "с 776 г. до н. э.", "Полисы", "Города-государства и Олимпийские игры")]
    gap, x = 0.24, 0.75
    cwid = (W - 2 * 0.75 - 3 * gap) / 4
    for i, (icon, dates, name, desc) in enumerate(eras):
        cx = x + i * (cwid + gap)
        s.add("dot", an("zoom", "after", 0, 300), x=cx + cwid / 2 - 0.19, y=ay - 0.145, w=0.38, h=0.38, fill=TERRA,
              line=WHITE)
        s.rect(cx, ay + 0.45, cwid, 2.95, fill=WHITE, radius=0.22, shadow={"blur": 0.2, "dist": 0.05, "alpha": 0.18},
               anim=an("fly", "with", 0, 450, direction="bottom"), role="era")
        s.pic(f"icons/{icon}.png", cx + cwid / 2 - 0.45, ay + 0.6, 0.9, 0.9, fit="contain",
              anim=an("zoom", "after", 0, 300))
        dw = text_w(dates, 14) + 0.42
        s.chip(cx + cwid / 2 - dw / 2, ay + 1.6, dates, fill=TERRA if i != 3 else OLIVE, size=14,
               anim=an("fade", "with", 100, 300))
        s.text(cx + 0.12, ay + 2.08, cwid - 0.24, 0.5, name, font=TITLE, size=20, color=NAVY, align="center",
               anim=an("fade", "with", 150, 300))
        s.text(cx + 0.15, ay + 2.55, cwid - 0.3, 0.75, desc, size=15.5, color=MUTED, align="center",
               anim=an("fade", "with", 200, 300))
    owl(s, "Крит — это почти **4000 лет** назад!", pos="tr", bw=3.6, size=16)
    s.flow.update({"kind": "timeline", "kicker": "Лента времени", "title": "Путешествие во времени", "lead": expl,
                   "eras": eras})
    slides.append(s)

    # 5 ── Crete -----------------------------------------------------------------------------------
    s = S("crete", "Крит — остров царя Миноса", transition=("fade", 800), notes=(
        "Минойская цивилизация расцвела на Крите примерно в 2000–1450 гг. до н. э. Это первая цивилизация Европы. "
        "Дворец в Кноссе занимал огромную площадь, в нём было больше тысячи помещений, световые колодцы, "
        "водопровод и канализация. На фресках — дельфины, цветы и опасная игра: прыжки через быка."))
    full_art(s, "knossos", (0.5, 0.5))
    rows = [("temple", "Дворец в Кноссе: больше **1000 комнат**, водопровод и даже канализация!"),
            ("dolphin", "Стены украшали яркие **фрески** с дельфинами и цветами."),
            ("ship", "Сильный **флот**: минойцы торговали с Египтом.")]
    lead = "Здесь появилась **первая цивилизация Европы**. Её жителей называют **минойцами** — по имени царя Миноса."
    card(s, M, M, 5.75, kicker="≈ 2000–1450 гг. до н. э.", title="Крит — остров царя Миноса", lead=lead, rows=rows,
         title_size=33)
    polaroid(s, "photos/dolphins.jpg", 7.75, 4.85, 4.75, 4.75 * 366 / 840, "Настоящая фреска «Дельфины»", rot=-2.5,
             alt="Минойская фреска с дельфинами из Кносса")
    s.flow.update({"kicker": "≈ 2000–1450 гг. до н. э.", "title": "Крит — остров царя Миноса", "lead": lead,
                   "rows": rows})
    slides.append(s)

    # 6 ── myth: Minotaur -------------------------------------------------------------------------
    s = S("minotaur", "Тесей и Минотавр", transition=("fade", 800), notes=(
        "Расскажите миф: царь Минос держал в лабиринте Минотавра. Афинский царевич Тесей вызвался победить "
        "чудовище. Царевна Ариадна дала ему клубок ниток, и по нити Тесей нашёл обратный путь. Возможно, миф "
        "появился потому, что огромный дворец в Кноссе с сотнями комнат казался настоящим лабиринтом."))
    full_art(s, "minotaur", (0.5, 0.5))
    lead = ("В лабиринте под дворцом жил **Минотавр** — чудовище с головой быка. Герой **Тесей** победил его, "
            "а выбраться помог клубок ниток царевны **Ариадны**.")
    card(s, M, M, 6.2, kicker="Миф", title="Тесей и Минотавр", lead=lead,
         rows=[("thread", "Учёные думают: миф родился из-за огромного запутанного **дворца в Кноссе**.")],
         align_bottom=True, kicker_fill=BLUE)
    owl(s, "«**Нить Ариадны**» — так и сейчас называют подсказку, которая выводит из трудного положения.",
        pos="tr", bw=4.9)
    s.flow.update({"kicker": "Миф", "title": "Тесей и Минотавр", "lead": lead,
                   "rows": [("thread", "Учёные думают: миф родился из-за огромного запутанного **дворца в Кноссе**.")]})
    slides.append(s)

    # 7 ── volcano --------------------------------------------------------------------------------
    s = S("volcano", "Вулкан и великая волна", transition=("fade", 800), notes=(
        "Около 1600 г. до н. э. на острове Фера (Санторини) произошло одно из сильнейших извержений в истории "
        "человечества. Пепел и цунами нанесли удар по минойцам. Цивилизация ослабла, и около 1450 г. до н. э. "
        "Крит захватили ахейцы с материка."))
    full_art(s, "volcano", (0.5, 0.5))
    rows = [("volcano", "Пепел засыпал острова, а огромные волны — **цунами** — ударили по берегам Крита."),
            ("shield", "Минойцы ослабели. Около **1450 г. до н. э.** Крит захватили воины с материка — **ахейцы**.")]
    lead = "На острове **Фера** (сейчас — Санторини) случилось одно из самых мощных извержений в истории."
    card(s, W - M - 5.5, M, 5.5, kicker="≈ 1600 г. до н. э.", title="Вулкан и великая волна", lead=lead, rows=rows)
    owl(s, "Остров Санторини до сих пор похож на **подкову** — это край огромного кратера!", pos="bl", bw=4.4)
    s.flow.update({"kicker": "≈ 1600 г. до н. э.", "title": "Вулкан и великая волна", "lead": lead, "rows": rows})
    slides.append(s)

    # 8 ── Mycenae --------------------------------------------------------------------------------
    s = S("mycenae", "Микены — город золотых царей", transition=("fade", 800), notes=(
        "Ахейцы жили на материковой Греции. Их главный город — Микены. Стены сложены из огромных камней — такую "
        "кладку называют циклопической. Главный вход — Львиные ворота. Генрих Шлиман нашёл в гробницах Микен "
        "золотые маски; одну из них назвали «маской Агамемнона»."))
    full_art(s, "mycenae", (0.5, 0.5))
    rows = [("rock", "Стены из глыб в несколько тонн! Греки верили, что их сложили великаны-**циклопы**."),
            ("lion", "Над главным входом — каменные львицы: **Львиные ворота**."),
            ("crown", "В гробницах нашли **золотые маски**, кубки и оружие.")]
    lead = "На материке жили **ахейцы**. Их города были неприступными крепостями, а правил ими царь — **ванака**."
    card(s, M, M, 5.6, kicker="≈ 1600–1200 гг. до н. э.", title="Микены — город золотых царей", lead=lead, rows=rows,
         title_size=33)
    polaroid(s, "photos/mask.jpg", 6.55, 3.75, 1.95, 1.95 * 750 / 500, "«Маска Агамемнона»", rot=3,
             alt="Золотая маска Агамемнона, Национальный археологический музей, Афины")
    s.flow.update({"kicker": "≈ 1600–1200 гг. до н. э.", "title": "Микены — город золотых царей", "lead": lead,
                   "rows": rows})
    slides.append(s)

    # 9 ── Troy ------------------------------------------------------------------------------------
    s = S("troy", "Троянская война", transition=("fade", 800), notes=(
        "По преданию, около 1200 г. до н. э. ахейцы во главе с микенским царём Агамемноном десять лет осаждали "
        "Трою. Победить помогла хитрость Одиссея — деревянный конь. Генрих Шлиман в детстве прочитал Гомера, "
        "поверил, что Троя существовала, и в 1870-х годах нашёл её руины на холме Гиссарлык."))
    full_art(s, "trojan_horse", (0.5, 0.5))
    rows = [("horse", "Хитрый **Одиссей** придумал деревянного коня. В нём спрятались воины."),
            ("fire", "Троянцы сами вкатили «подарок» в город — и ночью Троя пала."),
            ("pick", "В 1870-х **Генрих Шлиман** раскопал Трою — он мечтал о ней с детства!")]
    lead = "По легенде, ахейцы **10 лет** осаждали богатый город **Трою**, но не могли взять его стены."
    card(s, M, M, 5.55, kicker="≈ 1200 г. до н. э.", title="Троянская война", lead=lead, rows=rows)
    owl(s, "«**Троянский конь**» — так говорят о подарке-ловушке. И о компьютерном вирусе!", pos="tr", bw=4.5)
    s.flow.update({"kicker": "≈ 1200 г. до н. э.", "title": "Троянская война", "lead": lead, "rows": rows})
    slides.append(s)

    # 10 ── Dark ages & Homer ----------------------------------------------------------------------
    s = S("homer", "Тёмные века и певец Гомер", transition=("fade", 900), notes=(
        "Около 1200 г. до н. э. микенские дворцы были разрушены. Письменность забыли на несколько веков, поэтому "
        "этот период называют Тёмными веками. Зато распространились железные орудия. Сказания передавали устно "
        "певцы-аэды. Самый знаменитый из них — Гомер, автор «Илиады» и «Одиссеи»."))
    full_art(s, "homer", (0.5, 0.5))
    rows = [("music", "Певцы-**аэды** пересказывали древние сказания под звуки лиры."),
            ("books", "Самый знаменитый — **Гомер**: поэмы «**Илиада**» и «**Одиссея**».")]
    lead = "Дворцы Микен разрушили, письменность забыли. Зато люди научились делать орудия из **железа**."
    card(s, M, M, 5.5, kicker="≈ 1100–800 гг. до н. э.", title="Тёмные века и певец Гомер", lead=lead, rows=rows,
         fill=NAVY, alpha=0.86, dark=True, kicker_fill=GOLD)
    for el in s.els:
        if el.get("role") == "kicker":
            el["color"] = NAVY
    owl(s, "«Илиада» — это почти **16 000 строк**! Её пели наизусть.", pos="tr", bw=3.9)
    s.flow.update({"kicker": "≈ 1100–800 гг. до н. э.", "title": "Тёмные века и певец Гомер", "lead": lead,
                   "rows": rows, "dark": True})
    slides.append(s)

    # 11 ── alphabet -------------------------------------------------------------------------------
    s = S("alphabet", "Буквы, которые знаешь и ты", bg=NAVY, transition=("fade", 800), notes=(
        "Примерно в VIII веке до н. э. греки взяли за основу финикийское письмо и добавили буквы для гласных "
        "звуков. Слово «алфавит» состоит из названий первых двух букв — альфа и бета. Через тысячу с лишним лет "
        "на основе греческого письма появилась кириллица, поэтому многие буквы похожи."))
    s.meander(0, 0.22, W, 0.24, "gold")
    s.meander(0, H - 0.46, W, 0.24, "gold")
    lx, lw = M + 0.05, 5.85
    s.chip(lx, 0.85, "VIII век до н. э.", fill=GOLD, color=NAVY, anim=an("fade", "after", 0, 400))
    th = measure("Буквы, которые знаешь и ты", 36, lw, TITLE)
    s.text(lx, 1.35, lw, th, "Буквы, которые знаешь и ты", font=TITLE, size=36, color=WHITE,
           anim=an("fade", "with", 100, 500), role="title")
    lead = "Греки взяли буквы у **финикийцев** и добавили **гласные**. Так появился первый настоящий **алфавит**."
    y = 1.35 + th + 0.12
    lh = measure(lead, 19, lw, BODY)
    s.text(lx, y, lw, lh, lead, size=19, color="#E9EEF5", anim=an("fade", "after", 0, 400), role="lead")
    y += lh + 0.25
    rows = [("scroll", "Слово «алфавит» — это **альфа** ({{Α}}) + **бета** ({{Β}})."),
            ("letters", "Из греческих букв потом выросла и наша **кириллица**.")]
    for icon, t in rows:
        rh = measure(t, 19, lw - 0.8, BODY)
        s.pic(f"icons/{icon}.png", lx, y + (max(0.6, rh) - 0.6) / 2, 0.6, 0.6, fit="contain",
              anim=an("zoom", "after", 0, 300))
        s.text(lx + 0.8, y + (max(0.6, rh) - rh) / 2, lw - 0.8, rh, t, size=19, color="#E9EEF5",
               anim=an("fade", "with", 100, 400), role="row")
        y += max(0.6, rh) + 0.2
    pairs = [("Α", "А"), ("Β", "В"), ("Γ", "Г"), ("Δ", "Д"), ("Λ", "Л"), ("Π", "П"), ("Ρ", "Р"), ("Φ", "Ф")]
    gx, gy, tw, thh, g = 7.05, 0.95, 2.72, 1.24, 0.24
    for i, (gr, ru) in enumerate(pairs):
        r, c = divmod(i, 2)
        tx, ty = gx + c * (tw + g), gy + r * (thh + g)
        st = "with" if i % 2 else "after"
        s.rect(tx, ty, tw, thh, fill=WHITE, alpha=0.09, radius=0.22, line="#F2B134", line_w=1.25,
               anim=an("zoom", st, 0, 350), role="tile")
        s.text(tx + 0.08, ty + 0.06, 0.95, thh - 0.12, "{{" + gr + "}}", font=GREEK, size=46, color=GOLD,
               align="center", anim=an("fade", "with", 100, 300), anchor="middle", bold=True, role="greek")
        s.text(tx + 1.03, ty + 0.06, 0.6, thh - 0.12, "→", font=BODY, size=26, color="#8FA6C1", align="center",
               anchor="middle", anim=an("fade", "with", 150, 300))
        s.text(tx + 1.63, ty + 0.06, 1.0, thh - 0.12, ru, font=TITLE, size=42, color=WHITE, align="center",
               anchor="middle", anim=an("fade", "with", 200, 300))
    owl(s, "Прочитай: {{ΑΛΦΑ}} — «альфа»!", pos="bl", bw=3.5, size=17)
    s.flow.update({"kind": "alphabet", "kicker": "VIII век до н. э.", "title": "Буквы, которые знаешь и ты",
                   "lead": lead, "rows": rows, "pairs": pairs, "dark": True})
    slides.append(s)

    # 12 ── polis ---------------------------------------------------------------------------------
    s = S("polis", "Полис — город-государство", transition=("fade", 800), notes=(
        "С VIII века до н. э. в Греции появились сотни полисов. Полис — это город вместе с окрестными деревнями "
        "и полями. У каждого были свои законы, войско, монеты и боги-покровители. Покажите на картинке акрополь, "
        "агору, театр и гавань. Самые известные полисы — Афины и Спарта."))
    full_art(s, "polis", (0.5, 0.5))
    lead = "Город вместе с деревнями и полями вокруг. У каждого полиса — свои **законы**, **войско** и **монеты**."
    card(s, W - M - 4.75, 0.4, 4.75, kicker="С VIII века до н. э.", title="Полис — город-государство", lead=lead,
         title_size=30, lead_size=17, align_bottom=True)
    legend = [("1", "**Акрополь** — крепость на холме, где стоят храмы богов"),
              ("2", "**Агора** — главная площадь: рынок и народные собрания"),
              ("3", "**Театр** — здесь смотрели комедии и трагедии"),
              ("4", "**Гавань** — корабли привозили и увозили товары")]
    markers = [(0.415, 0.165), (0.535, 0.545), (0.155, 0.40), (0.85, 0.38)]
    # legend card (bottom-left) built manually so markers + rows animate in pairs
    pad, lw = 0.3, 5.3
    rh = [max(0.5, measure(t, 16.5, lw - 2 * pad - 0.7, BODY)) for _, t in legend]
    lh_total = sum(rh) + 0.12 * (len(rh) - 1) + 2 * pad
    ly = H - M - lh_total
    s.rect(M, ly, lw, lh_total, fill=CREAM, alpha=0.95, radius=0.26,
           shadow={"blur": 0.3, "dist": 0.06, "alpha": 0.28}, anim=an("fade", "after", 0, 400), role="card")
    yy = ly + pad
    for i, ((num, t), (fx, fy)) in enumerate(zip(legend, markers)):
        s.add("badge", an("zoom", "after", 100, 400), x=fx * W - 0.33, y=fy * H - 0.33, w=0.66, h=0.66, text=num,
              fill=TERRA, color=WHITE, size=22, line=WHITE, role="marker", shadow=True)
        s.add("badge", an("zoom", "with", 100, 300), x=M + pad, y=yy + (rh[i] - 0.5) / 2, w=0.5, h=0.5, text=num,
              fill=TERRA, color=WHITE, size=17)
        s.text(M + pad + 0.7, yy, lw - 2 * pad - 0.7, rh[i], t, size=16.5, color=INK, anchor="middle",
               anim=an("fade", "with", 150, 350), role="row")
        yy += rh[i] + 0.12
    owl(s, "Самые знаменитые полисы — **Афины** и **Спарта**.", pos="tl", bw=3.0, size=15.5)
    s.flow.update({"kind": "polis", "kicker": "С VIII века до н. э.", "title": "Полис — город-государство",
                   "lead": lead, "legend": legend, "markers": markers})
    slides.append(s)

    # 13 ── colonies ------------------------------------------------------------------------------
    s = S("colonies", "Греки плывут за моря", transition=("push", 800), notes=(
        "В VIII–VI веках до н. э. началась Великая греческая колонизация. Из-за нехватки земли и ради торговли "
        "греки основывали новые города по берегам Средиземного и Чёрного морей: Массалию (Марсель), Сиракузы, "
        "Византий, Ольвию, Херсонес, Пантикапей, Танаис и многие другие. Колонии везли на родину зерно, рыбу, "
        "металлы, а из Греции получали вино, оливковое масло и красивую посуду."))
    s.pic("maps/colonies.png", 0, 0, W, H, focus=(0.5, 0.5), role="map", alt="Карта греческих колоний")
    s.flow.update({"kind": "map", "map": "colonies"})
    tw13 = text_w("Греки плывут за моря", 30, TITLE) + 0.2
    s.rect(0.4, 0.35, tw13 + 0.56, 1.42, fill=CREAM, alpha=0.95, radius=0.24,
           shadow={"blur": 0.25, "dist": 0.05, "alpha": 0.25}, anim=an("fade", "after", 0, 400), role="card")
    s.chip(0.68, 0.55, "VIII–VI века до н. э.", fill=TERRA, anim=an("fade", "with", 100, 400))
    s.text(0.66, 0.98, tw13, 0.62, "Греки плывут за моря", font=TITLE, size=30, color=NAVY,
           anim=an("fade", "with", 150, 400), role="title")
    lead = ("Земли не хватало — и греки основали **колонии**: новые города по берегам Средиземного и даже "
            "**Чёрного** моря.")
    lh = measure(lead, 17.5, 4.4, BODY)
    s.rect(0.4, H - 0.35 - lh - 0.5, 5.0, lh + 0.5, fill=CREAM, alpha=0.95, radius=0.24,
           shadow={"blur": 0.25, "dist": 0.05, "alpha": 0.25}, anim=an("fade", "after", 0, 400), role="card")
    s.text(0.68, H - 0.35 - lh - 0.25, 4.45, lh, lead, size=17.5, color=INK, anim=an("fade", "with", 100, 400),
           role="lead")
    s.flow.update({"kicker": "VIII–VI века до н. э.", "title": "Греки плывут за моря", "lead": lead,
                   "rows": [("wheat", "Из колоний везли **зерно**, рыбу и металлы, а туда — вино, масло и посуду.")]})
    slides.append(s)

    # 14 ── Olympics ------------------------------------------------------------------------------
    s = S("olympics", "Первые Олимпийские игры", transition=("fade", 800), notes=(
        "Первые записанные Олимпийские игры прошли в 776 г. до н. э. в Олимпии, в святилище Зевса. Они "
        "повторялись каждые четыре года, а на время игр объявлялось священное перемирие. Сначала было только "
        "одно состязание — бег на один стадий (около 192 м). Первым победителем назван повар Кореб из Элиды. "
        "Наградой служил венок из ветвей священной оливы."))
    full_art(s, "olympics", (0.55, 0.5))
    rows = [("runner", "Сначала было одно состязание — **бег на стадий**, около 192 м."),
            ("medal", "Первым победителем стал повар **Кореб** из города Элида."),
            ("herb", "Награда — **венок** из ветвей оливы.")]
    lead = "Игры проходили в **Олимпии** в честь Зевса раз в **4 года**. На время игр прекращались войны!"
    card(s, M, M, 5.45, kicker="776 г. до н. э.", title="Первые Олимпийские игры", lead=lead, rows=rows,
         kicker_fill=OLIVE)
    owl(s, "От слова «стадий» произошло наше «**стадион**»!", pos="tr", bw=4.0)
    s.flow.update({"kicker": "776 г. до н. э.", "title": "Первые Олимпийские игры", "lead": lead, "rows": rows})
    slides.append(s)

    # 15-17 ── quiz -------------------------------------------------------------------------------
    quiz = [
        ("Кто жил в лабиринте на острове Крит?", ["Циклоп", "Минотавр", "Кентавр"], 1,
         "Верно! **Минотавр** — чудовище с головой быка. Его победил Тесей."),
        ("Чем награждали победителя первых Олимпийских игр?", ["Золотой медалью", "Мешком монет",
                                                               "Венком из ветвей оливы"], 2,
         "Верно! **Оливковый венок** был самой почётной наградой."),
        ("Из каких двух букв сложилось слово «алфавит»?", ["Альфа + бета", "Альфа + омега", "Аз + буки"], 0,
         "Верно! **Альфа** и **бета**. А из «аз» и «буки» получилось слово «азбука»!"),
    ]
    for qi, (q, answers, correct, explain) in enumerate(quiz, 1):
        s = S(f"quiz{qi}", f"Викторина: вопрос {qi}", bg=SAND, transition=("zoom", 600), notes=(
            f"Вопрос {qi}. Дайте детям подумать и выбрать ответ. Нажмите на вариант ответа — появится галочка или "
            f"крестик. Правильный ответ: «{answers[correct]}»."))
        s.meander(0, 0.2, W, 0.24, "terra")
        s.chip(M, 0.72, f"Викторина · вопрос {qi} из 3", fill=TURQ, anim=an("fade", "after", 0, 400))
        qh = measure(q, 34, 8.9, TITLE)
        s.text(M, 1.2, 8.9, qh, q, font=TITLE, size=34, color=NAVY, anim=an("fade", "with", 100, 500), role="title")
        y0 = max(2.75, 1.2 + qh + 0.35)
        aw, ah, ag = 8.7, 0.92, 0.26
        letters = "АБВ"
        ids = []
        for i, a in enumerate(answers):
            y = y0 + i * (ah + ag)
            el = s.add("answer", an("fly", "after", 0, 400, direction="left"), x=M, y=y, w=aw, h=ah, text=a,
                       correct=(i == correct), letter=letters[i], id=f"q{qi}a{i}")
            ids.append(el)
            s.add("badge", an("zoom", "with", 150, 300), x=M + 0.14, y=y + (ah - 0.64) / 2, w=0.64, h=0.64,
                  text=letters[i], fill=NAVY, color=WHITE, size=22)
            s.pic(f"icons/{'check' if i == correct else 'cross'}.png", M + aw - 0.86, y + (ah - 0.7) / 2, 0.7, 0.7,
                  fit="contain", anim=an("zoom", "trigger", 0, 350, trigger=f"q{qi}a{i}"), role="feedback",
                  feedback_for=f"q{qi}a{i}")
        ey = y0 + 3 * (ah + ag) + 0.02
        eh = measure(explain, 18, aw - 0.5, BODY) + 0.3
        s.rect(M, ey, aw, eh, fill="#E3F4E8", radius=0.2, line=GREEN, line_w=2,
               anim=an("fade", "trigger", 300, 400, trigger=f"q{qi}a{correct}"), role="explain",
               feedback_for=f"q{qi}a{correct}")
        s.text(M + 0.25, ey + 0.15, aw - 0.5, eh - 0.3, explain, size=18, color="#14532D",
               anim=an("fade", "trigger", 300, 400, trigger=f"q{qi}a{correct}"), role="explain",
               feedback_for=f"q{qi}a{correct}")
        s.pic("icons/question.png", 11.05, 0.55, 1.45, 1.45, fit="contain", rot=12,
              anim=an("zoom", "after", 0, 400), role="deco")
        s.pic("icons/owl.png", 10.1, 3.7, 2.55, 2.55, fit="contain", anim=an("zoom", "after", 0, 450), role="owl")
        s.bubble(9.75, 2.35, 3.2, 1.0, "Подумай и нажми на ответ!", ((11.3 - 11.35) / 3.2, (3.85 - 2.85) / 1.0),
                 size=17, anim=an("fade", "after", 0, 400), role="owl-bubble")
        s.flow.update({"kind": "quiz", "kicker": f"Викторина · вопрос {qi} из 3", "title": q, "answers": answers,
                       "correct": correct, "explain": explain, "owl": "Подумай и нажми на ответ!"})
        slides.append(s)

    # 18 ── summary --------------------------------------------------------------------------------
    s = S("summary", "Запомни главное!", bg=CREAM, transition=("fade", 800), notes=(
        "Повторим главное: природа Греции, минойский Крит, Микены и Троянская война, алфавит, полисы и первые "
        "Олимпийские игры. Можно попросить детей назвать по одному факту с каждой карточки."))
    s.meander(0, 0.2, W, 0.24, "terra")
    s.chip(M, 0.7, "Итоги", fill=TERRA, anim=an("fade", "after", 0, 400))
    s.text(M, 1.12, 7.5, 0.75, "Запомни главное!", font=TITLE, size=38, color=NAVY, anim=an("fade", "with", 100, 500),
           role="title")
    items = [("island", "Греция — это **горы, море** и тысячи **островов**"),
             ("dolphin", "**Крит** — первая цивилизация Европы (минойцы)"),
             ("lion", "**Микены** — крепости ахейцев и **Троянская война**"),
             ("scroll", "Греки создали **алфавит** с гласными буквами"),
             ("temple", "**Полис** — город-государство со своими законами"),
             ("medal", "**776 г. до н. э.** — первые Олимпийские игры")]
    gap = 0.3
    cw = (W - 2 * M - 2 * gap) / 3
    ch = 2.42
    for i, (icon, t) in enumerate(items):
        r, c = divmod(i, 3)
        x, y = M + c * (cw + gap), 2.05 + r * (ch + gap)
        s.rect(x, y, cw, ch, fill=WHITE, radius=0.24, shadow={"blur": 0.22, "dist": 0.05, "alpha": 0.16},
               anim=an("zoom", "after", 0, 400), role="sum-card")
        s.pic(f"icons/{icon}.png", x + 0.3, y + 0.26, 0.85, 0.85, fit="contain", anim=an("zoom", "with", 150, 300))
        s.add("num", an("fade", "with", 150, 300), x=x + cw - 0.75, y=y + 0.3, w=0.5, h=0.5, text=str(i + 1),
              color="#E0C9A6", size=30, role="deco-num")
        s.text(x + 0.3, y + 1.2, cw - 0.55, ch - 1.3, t, size=18.5, color=INK, anim=an("fade", "with", 200, 300),
               role="row")
    owl(s, "Ты настоящий историк!", pos="tr", bw=3.0, size=17)
    s.flow.update({"kind": "summary", "kicker": "Итоги", "title": "Запомни главное!", "items": items})
    slides.append(s)

    # 19 ── final ---------------------------------------------------------------------------------
    s = S("final", "Спасибо!", transition=("fade", 1000), notes=(
        "Поблагодарите слушателей. Обсудите вопрос: что из Древней Греции есть в нашей жизни? Подсказки: театр, "
        "музей, стадион, Олимпийские игры, буквы алфавита, слова «география», «история», «демократия»."))
    full_art(s, "cover", (0.62, 0.5))
    s.rect(0, 0, W, H, fill=NAVY, alpha=0.58, role="shade")
    s.text(0.8, 0.95, W - 1.6, 1.15, "Спасибо за внимание!", font=TITLE, size=56, color=WHITE, align="center",
           anim=an("zoom", "after", 0, 600), role="title")
    s.text(0.8, 2.15, W - 1.6, 0.95, "{{Ευχαριστώ!}}", font=GREEK, size=44, color=GOLD, align="center", bold=True,
           anim=an("fade", "after", 0, 500))
    s.text(0.8, 3.12, W - 1.6, 0.5, "«эфхаристо́» — так говорят «спасибо» по-гречески", size=20, color="#E9EEF5",
           align="center", anim=an("fade", "with", 200, 500))
    q = "Обсудим: что из Древней Греции есть в **твоей** жизни?"
    hint = "Подсказка: театр, музей, стадион, Олимпиада, буквы А, В, Г, Д…"
    qh = measure(q, 23, W - 5.5, XB)
    hh = measure(hint, 18, W - 5.5, BODY)
    s.rect(2.4, 4.0, W - 4.8, qh + hh + 0.62, fill=CREAM, alpha=0.96, radius=0.28,
           shadow={"blur": 0.3, "dist": 0.06, "alpha": 0.3}, anim=an("fly", "after", 0, 500, direction="bottom"),
           role="card")
    s.text(2.75, 4.22, W - 5.5, qh, q, font=XB, size=23, color=NAVY, align="center",
           anim=an("fade", "with", 200, 400), role="lead")
    s.text(2.75, 4.22 + qh + 0.16, W - 5.5, hh, hint, size=18, color=MUTED, align="center",
           anim=an("fade", "with", 300, 400), role="row")
    owl(s, "Пока-пока! До новых путешествий!", pos="bl", bw=3.6, size=17)
    s.flow.update({"kind": "final", "title": "Спасибо за внимание!", "greek": "Ευχαριστώ!",
                   "lead": "«эфхаристо́» — так говорят «спасибо» по-гречески", "question": q, "hint": hint})
    slides.append(s)

    # 20 ── credits -------------------------------------------------------------------------------
    s = S("credits", "Откуда картинки и факты", bg=CREAM, transition=("fade", 600), notes=(
        "Список источников. Иллюстрации созданы ИИ специально для этой презентации; остальные материалы "
        "распространяются по свободным лицензиям."))
    s.meander(0, 0.2, W, 0.24, "terra")
    s.text(M, 0.7, 9, 0.75, "Откуда картинки и факты", font=TITLE, size=32, color=NAVY, role="title")
    credits = [
        ("sparkles", "**Иллюстрации** — нарисованы ИИ специально для этой презентации."),
        ("pin", "**Фото:** «Маска Агамемнона» (Национальный археологический музей, Афины) — Wikimedia Commons; "
                "фреска «Дельфины» (Кносс, ≈ 1600 г. до н. э.) — общественное достояние."),
        ("map", "**Карты** — по данным Natural Earth (общественное достояние)."),
        ("owl", "**Значки и совёнок Афи** — Microsoft Fluent Emoji (MIT). **Шрифты** — Nunito, Comfortaa (SIL OFL)."),
        ("books", "**Факты** — материалы по истории Древнего мира: infourok.ru, onhistory.ru, videouroki.net, "
                  "kidpassage.com, geographyworlds.com."),
        ("bulb", "Сделано Python-тулкитом **prezintacia**: python-pptx, LibreOffice (WASM), Chromium."),
    ]
    y = 1.65
    for icon, t in credits:
        rh = measure(t, 16, W - 2 * M - 0.75, BODY)
        s.pic(f"icons/{icon}.png", M, y + (max(0.48, rh) - 0.48) / 2, 0.48, 0.48, fit="contain")
        s.text(M + 0.7, y + (max(0.48, rh) - rh) / 2, W - 2 * M - 0.75, rh, t, size=16, color=INK, role="row")
        y += max(0.48, rh) + 0.2
    s.flow.update({"kind": "credits", "title": "Откуда картинки и факты", "rows": credits})
    slides.append(s)
    return slides


if __name__ == "__main__":
    for i, sl in enumerate(build_slides(), 1):
        print(f"{i:2d} {sl.key:10s} {len(sl.els):3d} elements · {sl.title}")
