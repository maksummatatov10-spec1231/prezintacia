#!/usr/bin/env python3
"""Prepare every asset of the deck «Как появилась Древняя Греция» into deck/greece/assets/.

  python deck/greece/assets.py          # idempotent; skips what already exists (use --force)

art/      AI illustrations: .jpg (PPTX, 1376×768) + .webp (HTML)
photos/   real artefacts (Wikimedia Commons / public-domain artworks)
icons/    Microsoft Fluent 3D emoji (MIT) .png 256 + .webp 160
maps/     Natural Earth (public domain) maps: .svg (HTML, vector) + .png (PPTX)
fonts/    Nunito + Comfortaa (SIL OFL): static .ttf for PPTX / LibreOffice, subset .woff2 for HTML
meander   Greek-key band .png + .svg
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw  # noqa: E402

from pptkit import imaging  # noqa: E402
from pptkit.env import CACHE, FONTS_DIR  # noqa: E402
from pptkit.maps import MapSVG  # noqa: E402

A = HERE / "assets"
RAW = ROOT / "raw"
FLUENT = CACHE / "src" / "fluent" / "assets"
GF = CACHE / "src" / "gfonts" / "ofl"
FORCE = "--force" in sys.argv

PALETTE = {
    "navy": "#0E2A47", "blue": "#1667A8", "sea": "#2E9CCA", "turq": "#18A8B5", "terra": "#C8553D",
    "terra_dk": "#9E3B27", "gold": "#F2B134", "sand": "#FFF4E2", "cream": "#FFFAF1", "olive": "#6E8B3D",
    "ink": "#1D2433", "muted": "#5B6475",
}

ART = ["cover", "landscape", "knossos", "minotaur", "volcano", "mycenae", "trojan_horse", "homer", "polis", "olympics"]
ICONS = {
    "owl": "Owl", "mountain": "Snow-capped mountain", "amphora": "Amphora", "grapes": "Grapes",
    "sailboat": "Sailboat", "dolphin": "Dolphin", "lion": "Lion", "horse": "Horse", "hourglass": "Hourglass done",
    "temple": "Classical building", "medal": "1st place medal", "scroll": "Scroll", "volcano": "Volcano",
    "wave": "Water wave", "thread": "Thread", "trophy": "Trophy", "theatre": "Performing arts", "map": "World map",
    "check": "Check mark button", "cross": "Cross mark", "question": "Red question mark", "party": "Party popper",
    "bulb": "Light bulb", "shield": "Shield", "crown": "Crown", "runner": "Person running", "island": "Desert island",
    "fire": "Fire", "books": "Books", "letters": "Input latin letters", "sparkles": "Sparkles", "pick": "Pick",
    "star": "Glowing star", "compass": "Compass", "ship": "Ship", "wheat": "Sheaf of rice", "herb": "Herb",
    "swords": "Crossed swords", "rock": "Rock", "speech": "Speech balloon", "pin": "Round pushpin",
    "ballot": "Ballot box with ballot", "dove": "Dove", "thinking": "Thinking face", "wave_hand": "Waving hand",
    "calendar": "Calendar", "key": "Old key", "music": "Musical note",
}


def _need(p: Path) -> bool:
    return FORCE or not p.exists()


# ----------------------------------------------------------------------------- images
def build_art():
    (A / "art").mkdir(parents=True, exist_ok=True)
    for name in ART:
        src = RAW / "ai" / f"{name}.png"
        if not src.exists():
            print("  ! missing", src)
            continue
        jpg, webp = A / "art" / f"{name}.jpg", A / "art" / f"{name}.webp"
        if _need(jpg):
            imaging.optimize(src, jpg, max_size=(1920, 1080), quality=88)
        if _need(webp):
            imaging.optimize(src, webp, max_size=(1600, 900), quality=80)
        # phone-portrait crop helper is done in CSS (object-position) — no extra file


def build_photos():
    (A / "photos").mkdir(parents=True, exist_ok=True)
    web = RAW / "web"
    jobs = {
        # Minoan "Dolphin fresco", Queen's Megaron, Knossos (c. 1600 BC) — public-domain artwork
        "dolphins": (web / "minoan-dolphin-fresco-knossos-queen-s-me-3.jpg", None),
        # Mask of Agamemnon, National Archaeological Museum, Athens — Wikimedia Commons photo
        "mask": (web / "mask-of-agamemnon-gold-national-archaeol-3.jpg", None),
        # Linear B tablet — Wikimedia Commons photo
        "linearb": (web / "linear-b-clay-tablet-mycenaean-writing-m-3.jpg", None),
    }
    for name, (src, box) in jobs.items():
        if not src.exists():
            print("  ! missing", src)
            continue
        im = imaging.open_image(src)
        if box:
            im = im.crop(box)
        for ext, q in (("jpg", 90), ("webp", 82)):
            dst = A / "photos" / f"{name}.{ext}"
            if _need(dst):
                imaging.optimize(im, dst, max_size=None, quality=q)


def build_icons():
    (A / "icons").mkdir(parents=True, exist_ok=True)
    for key, folder in ICONS.items():
        d = FLUENT / folder / "3D"
        if not d.exists():
            d = FLUENT / folder / "Default" / "3D"
        files = sorted(d.glob("*.png")) if d.exists() else []
        if not files:
            print("  ! icon missing", folder)
            continue
        png, webp = A / "icons" / f"{key}.png", A / "icons" / f"{key}.webp"
        if _need(png):
            shutil.copy2(files[0], png)
        if _need(webp):
            im = Image.open(files[0]).convert("RGBA")
            im.thumbnail((160, 160), Image.LANCZOS)
            im.save(webp, "WEBP", quality=88, method=6)


# ----------------------------------------------------------------------------- meander (Greek key)
MEANDER_UNIT = 12  # pattern repeat in grid units


def meander_svg(color="#C8553D", h=24, bg=None) -> str:
    """Tileable Greek-key band (one repeat = 12×12 units, scaled to height h)."""
    u = h / 12
    sw = 1.6 * u
    d = (f"M0 {0.8 * u:.2f}H{12 * u:.2f}"                      # top line
         f"M0 {11.2 * u:.2f}H{12 * u:.2f}"                     # bottom line
         f"M{9 * u:.2f} {11.2 * u:.2f}V{3 * u:.2f}H{3 * u:.2f}V{8.4 * u:.2f}H{6.2 * u:.2f}V{5.6 * u:.2f}")
    rect = f'<rect width="{12 * u:.2f}" height="{h}" fill="{bg}"/>' if bg else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{12 * u:.2f}" height="{h}" viewBox="0 0 {12 * u:.2f} {h}">'
            f'{rect}<path d="{d}" fill="none" stroke="{color}" stroke-width="{sw:.2f}" stroke-linecap="square"/></svg>')


def meander_png(path: Path, color=(200, 85, 61, 255), height=48, repeats=120, bg=(0, 0, 0, 0)):
    u = height / 12
    W = int(round(12 * u * repeats))
    im = Image.new("RGBA", (W, height), bg)
    d = ImageDraw.Draw(im)
    sw = max(2, int(round(1.6 * u)))

    def hline(x0, x1, y):
        d.rectangle((x0, y - sw / 2, x1, y + sw / 2), fill=color)

    def vline(x, y0, y1):
        d.rectangle((x - sw / 2, min(y0, y1) - sw / 2, x + sw / 2, max(y0, y1) + sw / 2), fill=color)

    hline(0, W, 0.8 * u)
    hline(0, W, 11.2 * u)
    for k in range(repeats):
        o = k * 12 * u
        vline(o + 9 * u, 11.2 * u, 3 * u)
        hline(o + 3 * u, o + 9 * u, 3 * u)
        vline(o + 3 * u, 3 * u, 8.4 * u)
        hline(o + 3 * u, o + 6.2 * u, 8.4 * u)
        vline(o + 6.2 * u, 8.4 * u, 5.6 * u)
    im.save(path, optimize=True)


def build_meander():
    p = A / "meander.png"
    if _need(p):
        meander_png(p)
        meander_png(A / "meander_gold.png", color=(242, 177, 52, 255))
        meander_png(A / "meander_white.png", color=(255, 250, 241, 235))
    (A / "meander.svg").write_text(meander_svg(), encoding="utf-8")


# ----------------------------------------------------------------------------- maps
MAP_CSS = """
.sea-bg{fill:url(#seaG)}
.land-halo{fill:none;stroke:#DDF4FA;stroke-width:10;stroke-linejoin:round;opacity:.95}
.land{fill:#F8EBCB;stroke:#B98F55;stroke-width:1.4;stroke-linejoin:round}
.glow{fill:url(#glowG)}
.city circle{fill:#fff;stroke:#C8553D;stroke-width:4}
.city text,.mount text{font-family:Nunito,sans-serif;font-weight:800;font-size:27px;fill:#33261A;paint-order:stroke;stroke:#FFF8EA;stroke-width:7px;stroke-linejoin:round}
.colony circle{fill:#F2B134;stroke:#7A3B1E;stroke-width:3}
.colony text{font-family:Nunito,sans-serif;font-weight:800;font-size:25px;fill:#33261A;paint-order:stroke;stroke:#FFF8EA;stroke-width:6px;stroke-linejoin:round}
.mount path{fill:#8C6B4A;stroke:#FFF8EA;stroke-width:2}
.sea{font-family:Nunito,sans-serif;font-style:italic;font-weight:700;font-size:28px;fill:#2A7FA8;letter-spacing:1px}
.sea-sm{font-family:Nunito,sans-serif;font-style:italic;font-weight:700;font-size:23px;fill:#2A7FA8}
.region{font-family:Nunito,sans-serif;font-weight:900;font-size:40px;fill:#8F5A2C;letter-spacing:6px;opacity:.9}
.region-sm{font-family:Nunito,sans-serif;font-weight:900;font-size:24px;fill:#8F5A2C;letter-spacing:3px;opacity:.85}
.region-faint{font-family:Nunito,sans-serif;font-weight:900;font-size:26px;fill:#A88B66;letter-spacing:4px;opacity:.75}
.route{fill:none;stroke:#C8553D;stroke-width:3.2;stroke-dasharray:10 8;stroke-linecap:round;opacity:.9}
.frame{fill:none;stroke:#C8553D;stroke-width:5;stroke-dasharray:12 8}
"""
SEA_DEFS = ('<linearGradient id="seaG" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#BDE7F2"/>'
            '<stop offset="1" stop-color="#8ED0E6"/></linearGradient>'
            '<radialGradient id="glowG"><stop offset="0" stop-color="#F2B134" stop-opacity=".55"/>'
            '<stop offset="1" stop-color="#F2B134" stop-opacity="0"/></radialGradient>')


def map_aegean() -> MapSVG:
    m = MapSVG((19.3, 34.7, 30.0, 41.6), width=1200)
    m.defs.append(SEA_DEFS)
    m.land()
    m.label("ГРЕЦИЯ", 21.95, 39.55, cls="region")
    m.label("ПЕЛОПОННЕС", 22.2, 37.42, cls="region-sm")
    m.label("МАЛАЯ АЗИЯ", 28.0, 38.75, cls="region")
    m.label("Эгейское\nморе", 25.15, 39.55, cls="sea")
    m.label("Ионическое\nморе", 20.15, 37.25, cls="sea")
    m.label("Средиземное море", 20.95, 35.25, cls="sea")
    m.label("о. Крит", 23.75, 34.98, cls="region-sm")
    # Mount Olympus
    x, y = m.xy(22.35, 40.085)
    m.add(f'<g class="mount"><path d="M{x - 16:.1f} {y + 12:.1f}L{x:.1f} {y - 16:.1f}L{x + 16:.1f} {y + 12:.1f}Z"/>'
          f'<text x="{x + 22:.1f}" y="{y + 9:.1f}">гора Олимп</text></g>')
    m.city("Афины", 23.727, 37.984, dx=14, dy=9)
    m.city("Микены", 22.756, 37.731, dx=-14, dy=-6, anchor="end")
    m.city("Спарта", 22.43, 37.075, dx=-14, dy=9, anchor="end")
    m.city("Олимпия", 21.63, 37.638, dx=-14, dy=9, anchor="end")
    m.city("Кносс", 25.163, 35.298, dx=0, dy=32, anchor="middle")
    m.city("Троя", 26.239, 39.957, dx=14, dy=9)
    m.city("о. Фера", 25.43, 36.40, dx=14, dy=9)
    return m


def map_colonies() -> MapSVG:
    m = MapSVG((-1.0, 29.8, 42.5, 47.8), width=1600)
    m.defs.append(SEA_DEFS)
    gx, gy = m.xy(24.6, 38.0)
    m.defs.append('<radialGradient id="homeG"><stop offset="0" stop-color="#fff"/><stop offset=".65" stop-color="#fff"/>'
                  '<stop offset="1" stop-color="#000"/></radialGradient>'
                  f'<mask id="homeM"><circle cx="{gx:.0f}" cy="{gy:.0f}" r="175" fill="url(#homeG)"/></mask>')
    d = m.land(datasets=("ne_10m_land",), min_step=1.8)
    m.add(f'<use href="#{d}" fill="#F0C987" stroke="none" mask="url(#homeM)"/>')
    m.label("Средиземное море", 19.6, 35.2, cls="sea")
    m.label("Чёрное море", 34.2, 43.35, cls="sea")
    m.label("ГРЕЦИЯ", 21.6, 39.75, cls="region-sm")
    m.label("ЕГИПЕТ", 28.6, 30.55, cls="region-faint")
    m.label("МАЛАЯ АЗИЯ", 32.6, 39.1, cls="region-faint")
    corinth, miletus = (22.9, 37.9), (27.28, 37.53)
    west = {"Массалия": ((5.37, 43.30), (0, 32, "middle")), "Неаполь": ((14.27, 40.85), (-13, -8, "end")),
            "Тарент": ((17.24, 40.46), (12, -8, "start")), "Сиракузы": ((15.29, 37.08), (-13, 9, "end")),
            "Кирена": ((21.86, 32.82), (0, 30, "middle"))}
    east = {"Византий": ((28.98, 41.01), (-13, -6, "end")), "Ольвия": ((31.90, 46.69), (-13, 9, "end")),
            "Херсонес": ((33.49, 44.61), (-13, 9, "end")), "Пантикапей": ((36.47, 45.36), (12, 22, "start")),
            "Танаис": ((39.27, 47.27), (-13, 9, "end")), "Синопа": ((35.15, 42.02), (0, 30, "middle")),
            "Трапезунд": ((39.72, 41.00), (-10, 30, "end")), "Навкратис": ((30.6, 30.9), (12, 9, "start"))}
    byz, thera = (28.98, 41.01), (25.43, 36.40)
    for name, (pos, _) in west.items():
        m.arc(thera if name == "Кирена" else corinth, pos, bend=0.12)
    m.arc(miletus, byz, bend=-0.25)
    m.arc(miletus, east["Навкратис"][0], bend=-0.12)
    for name, (pos, _) in east.items():
        if name not in ("Византий", "Навкратис"):
            m.arc(byz, pos, bend=-0.1)
    for name, (pos, (dx, dy, anc)) in {**west, **east}.items():
        m.city(name, *pos, dx=dx, dy=dy, anchor=anc, cls="colony", r=7)
    m.city("Коринф", *corinth, dx=-14, dy=24, anchor="end", r=7)
    m.city("Милет", *miletus, dx=12, dy=24, r=7)
    return m


def map_europe() -> MapSVG:
    m = MapSVG((-11.0, 33.5, 45.0, 61.0), width=560)
    m.defs.append(SEA_DEFS)
    m.css.append(".land{stroke-width:.8}.land-halo{stroke-width:5}"
                 ".region-faint{font-size:24px}")
    m.land(datasets=("ne_50m_land",), min_step=0.8)
    m.label("ЕВРОПА", 14.0, 51.2, cls="region-faint")
    m.label("АФРИКА", 9.0, 34.4, cls="region-faint")
    x0, y0 = m.xy(19.3, 41.6)
    x1, y1 = m.xy(30.0, 34.7)
    m.add(f'<rect class="frame" x="{x0:.1f}" y="{y0:.1f}" width="{x1 - x0:.1f}" height="{y1 - y0:.1f}" rx="6"/>')
    return m


def _svg_with_font(svg: str, tmpdir: Path) -> str:
    """Embed a tiny Nunito subset (only the glyphs of the labels) INTO the SVG, so the map looks the same
    when used as an <img>/CSS background (those cannot see the page fonts)."""
    import base64
    import html as _html
    import re as _re
    from pptkit.fonts import subset
    texts = _re.findall(r">([^<>]+)<", svg)
    chars = "".join(sorted(set("".join(_html.unescape(t) for t in texts)) | set("0123456789 .-")))
    woff = subset(CACHE / "fonts_variable" / "Nunito[wght].ttf", tmpdir / "map-font.woff2", text=chars,
                  unicodes=None, flavor="woff2")
    b64 = base64.b64encode(woff.read_bytes()).decode()
    face = f"@font-face{{font-family:Nunito;src:url(data:font/woff2;base64,{b64}) format('woff2');font-weight:200 1000}}"
    return svg.replace("<style>", f"<style>{face}", 1)


def build_maps():
    import tempfile
    (A / "maps").mkdir(parents=True, exist_ok=True)
    maps = {"aegean": map_aegean(), "colonies": map_colonies(), "europe": map_europe()}
    tmp = Path(tempfile.mkdtemp())
    pages = []
    for name, m in maps.items():
        svg = _svg_with_font(m.svg(css=MAP_CSS), tmp)
        (A / "maps" / f"{name}.svg").write_text(svg, encoding="utf-8")
        page = (f"<html><head><meta charset=\"utf-8\"><style>html,body{{margin:0}}"
                f"svg{{display:block;width:{m.W}px;height:{m.H}px}}</style></head><body>{svg}</body></html>")
        (A / "maps" / f"_{name}.html").write_text(page, encoding="utf-8")
        pages.append((name, m))
    from pptkit.browser import Chrome
    with Chrome() as c:
        for name, m in pages:
            c.shot(A / "maps" / f"_{name}.html", A / "maps" / f"{name}.png", width=m.W, height=m.H, scale=1.5,
                   wait_ms=80, mobile=False)
            (A / "maps" / f"_{name}.html").unlink()
    for name, m in pages:
        print(f"  map {name}: {m.W}×{m.H}, svg {len((A / 'maps' / f'{name}.svg').read_bytes()) // 1024} KB")


# ----------------------------------------------------------------------------- fonts
def build_fonts():
    from pptkit.fonts import subset
    d = A / "fonts"
    d.mkdir(parents=True, exist_ok=True)
    for f in ["Nunito-Regular", "Nunito-Bold", "Nunito-ExtraBold", "Nunito-Black", "Comfortaa-Bold"]:
        src = FONTS_DIR / f"{f}.ttf"
        if _need(d / f"{f}.ttf") and src.exists():
            shutil.copy2(src, d / f"{f}.ttf")
    vf = CACHE / "fonts_variable"
    if _need(d / "nunito.woff2"):
        subset(vf / "Nunito[wght].ttf", d / "nunito.woff2",
               unicodes="U+0000-00FF,U+0131,U+0152-0153,U+02C6,U+02DA,U+02DC,U+0400-045F,U+0490-0491,U+2000-206F,"
                        "U+20AC,U+2116,U+2122,U+2190-2199,U+2212,U+2215,U+2248,U+2260,U+2264-2265,U+2713,U+2714,U+2716,U+FEFF,U+FFFD",
               flavor="woff2")
    if _need(d / "comfortaa.woff2"):
        subset(vf / "Comfortaa[wght].ttf", d / "comfortaa.woff2",
               unicodes="U+0000-00FF,U+0370-03FF,U+0400-045F,U+2000-206F", flavor="woff2")
    for lic in ("nunito", "comfortaa"):
        src = GF / lic / "OFL.txt"
        if src.exists():
            shutil.copy2(src, d / f"OFL-{lic}.txt")


def main():
    for fn in (build_art, build_photos, build_icons, build_meander, build_fonts, build_maps):
        print("•", fn.__name__)
        fn()
    total = sum(p.stat().st_size for p in A.rglob("*") if p.is_file())
    print(f"assets: {total / 1e6:.1f} MB in {A}")


if __name__ == "__main__":
    main()
