"""build_deck.py — apply the agreed changes to «Кукла из воздушного пластилина.pptx».

1. mouth of the doll → black on slides 13–15 (new media, same rIds / crop)
2. the girl's photo on slide 18 (new picture part, rounded, soft shadow)
3. animated paint-blob background on EVERY slide: a looping mp4 (autoplay + loop, stored once) + poster
4. errors: slide-17 note text had 4 leading spaces (text ran off the card), slide-18 low contrast,
   slide-1 title box too short, 13 pt labels → 14 pt

    python tools/deck_kukla/build_deck.py            # → presentations/kukla-iz-vozdushnogo-plastilina.pptx
"""
from __future__ import annotations

import re
import shutil
import sys
import time
import zipfile
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pptx_xml as X  # noqa: E402
from lxml import etree  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "input/kukla-iz-vozdushnogo-plastilina.pptx"
OUT = ROOT / "presentations/kukla-iz-vozdushnogo-plastilina.pptx"
VIDEO = ROOT / "tools/deck_kukla/assets/bg/paint_loop.mp4"
POSTER = ROOT / "tools/deck_kukla/assets/bg/paint_poster.jpg"
PHOTO = ROOT / "tools/deck_kukla/assets/photo/girl_square.jpg"
MOUTHS = {n: ROOT / f"tools/deck_kukla/assets/mouth/slide{n}.jpg" for n in (13, 14, 15)}

SLIDE_W, SLIDE_H = 12192000, 6858000
NO_VIDEO = {18, 19}  # photo slide: the photo must stay visible; final slide: dark, white text
P = X.P
A = X.A


def slide_no(name: str) -> int | None:
    m = re.fullmatch(r"ppt/slides/slide(\d+)\.xml", name)
    return int(m.group(1)) if m else None


def sub(xml: bytes, pattern: str, repl, count=1, flags=re.S) -> bytes:
    s = xml.decode("utf-8")
    new, n = re.subn(pattern, repl, s, count=count, flags=flags)
    assert n > 0, f"pattern not found: {pattern[:80]}"
    return new.encode("utf-8")


def shape_block(s: str, name: str) -> tuple[int, int]:
    m = re.search(r'<p:sp>(?:(?!</p:sp>).)*?name="%s".*?</p:sp>' % re.escape(name), s, re.S)
    assert m, name
    return m.span()


def edit_shape(s: str, name: str, fn) -> str:
    a, b = shape_block(s, name)
    return s[:a] + fn(s[a:b]) + s[b:]


# --------------------------------------------------------------------------- per-slide edits
log: list[str] = []


def edit_slide(n: int, xml: bytes) -> bytes:
    s = xml.decode("utf-8")

    # --- 3. every slide: fade transition (added after the shapes are edited)
    # --- page numbers: the last 12 pt note — 14 pt with a box that actually fits
    def bigger_number(blk: str) -> str:
        blk = blk.replace('sz="1200"', 'sz="1400"').replace('spcPts val="1380"', 'spcPts val="1610"')
        return blk.replace('<a:ext cx="142280" cy="200660"/>', '<a:ext cx="165993" cy="234103"/>')
    for nm in re.findall(r'<p:cNvPr id="\d+" name="(Text \d+)"', s):
        a, b = shape_block(s, nm)
        blk = s[a:b]
        if re.search(r'<a:t>\d{1,2}</a:t>', blk) and 'sz="1200"' in blk and 'spcPts val="1380"' in blk:
            s = s[:a] + bigger_number(blk) + s[b:]
            log.append(f"слайд {n}: номер страницы 12 → 14 pt")

    # --- 4. 13 pt eyebrow labels → 14 pt (min size for a big screen)
    s2, k = re.subn(r'sz="1300"', 'sz="1400"', s)
    if k:
        log.append(f"слайд {n}: подписи 13 pt → 14 pt ({k} шт.)")
        s = s2

    if n == 1:
        # the title box was 5.6 cm tall for ~6.5 cm of text; the design is fixed → give it the free room
        def taller(blk: str) -> str:
            return re.sub(r'(<a:off x="812800" y="1577086"/><a:ext cx="5886450" cy=")\d+"',
                          r'\g<1>2133594"', blk, count=1)
        s = edit_shape(s, "Text 1", taller)
        log.append("слайд 1: заголовок — рамка 5.6 → 5.9 см (запас под 3 строки)")

    if n == 7:
        # the two long labels («Полимерные связующие», «Наполнители») needed 1.4 cm in a 1.1 cm box
        for nm in ("Text 10", "Text 12", "Text 14", "Text 16"):
            def room(blk: str) -> str:
                blk = re.sub(r'<a:off x="(\d+)" y="(\d+)"/>', lambda m: f'<a:off x="{m.group(1)}" y="{int(m.group(2)) - 95250}"/>', blk, count=1)
                return re.sub(r'(<a:ext cx="\d+" cy=")\d+"', r'\g<1>1447800"', blk, count=1)
            s = edit_shape(s, nm, room)
        log.append("слайд 7: подписи-«пилюли» — рамки выше на 0.26 см (2 строки больше не обрезаются)")

    if n == 17:
        # the conclusion text box ended exactly at the yellow card's edge (0 right padding) → it overflowed
        def narrower(blk: str) -> str:
            return blk.replace('<a:ext cx="9601200" cy="723900"/>', '<a:ext cx="8661400" cy="723900"/>', 1)
        s = edit_shape(s, "Text 57", narrower)
        log.append("слайд 17: «Вывод» — текст не выходит за карточку (правый отступ 0.78 см)")

    if n == 18:
        def card(blk: str) -> str:
            return blk.replace('srgbClr val="E5625B"', 'srgbClr val="C8553D"', 1)
        s = edit_shape(s, "Shape 13", card)
        # 1.94:1 → 5.4:1 : the gold label on the terracotta card was unreadable
        s = edit_shape(s, "Text 14", lambda b: b.replace('srgbClr val="F4C430"', 'srgbClr val="FFF4E4"'))
        log.append("слайд 18: карточка гипотезы E5625B → C8553D, подпись золотая → кремовая (контраст 5.4:1)")
    return s.encode("utf-8")


def add_photo(xml: bytes) -> bytes:
    """slide 18: the girl with the doll — square card under the checklist, bottom-left."""
    return X.add_picture(xml, x=813600, y=4500000, w=2100000, h=2100000,
                         embed_rid="rId90", name="Камилла с куклой", index=2, shadow=0.26,
                         descr="Автор работы — Камилла — держит готовую куклу «Барыня»",
                         round_adj=5500)


# --------------------------------------------------------------------------- assembly
def main() -> int:
    t0 = time.time()
    assert VIDEO.exists() and POSTER.exists() and PHOTO.exists(), "assets missing"
    for p in MOUTHS.values():
        assert p.exists(), p
    tmp = OUT.with_suffix(".tmp.pptx")
    video_bytes, poster_bytes, photo_bytes = VIDEO.read_bytes(), POSTER.read_bytes(), PHOTO.read_bytes()

    with zipfile.ZipFile(SRC) as zin:
        infos = zin.infolist()
        ct = X.ensure_default(zin.read("[Content_Types].xml"), "mp4", "video/mp4")
        # map: which media part holds the step photo of slides 13–15
        media = {}
        for n in (13, 14, 15):
            rels = zin.read(f"ppt/slides/_rels/slide{n}.xml.rels").decode()
            m = re.search(r'Id="(rId\d+)"[^>]*Target="\.\./media/([^"]+)"', rels)
            media[n] = (m.group(1), "ppt/media/" + m.group(2))
        HANDLED = {f"ppt/slides/_rels/slide{n}.xml.rels" for n in range(1, 20)} | {"[Content_Types].xml"}
        MEDIA_REPL = {media[n][1]: n for n in media}

        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
            for it in infos:
                name = it.filename
                if name in HANDLED:
                    continue
                data = zin.read(name)
                if name in MEDIA_REPL:  # 1. the mouth is black now
                    data = MOUTHS[MEDIA_REPL[name]].read_bytes()
                    log.append(f"{name}: рот перекрашен в чёрный (слайд {MEDIA_REPL[name]})")
                    zout.writestr(it, data)
                    continue
                n = slide_no(name)
                if n:
                    data = edit_slide(n, data)
                    rels_name = f"ppt/slides/_rels/slide{n}.xml.rels"
                    rels = zin.read(rels_name)
                    if n == 18:
                        rels = X.add_rel(rels, "rId90", "image", "../media/girl_with_doll.jpg")
                        data = add_photo(data)
                        log.append("слайд 18: добавлено фото девочки с куклой")
                    if n == 18:  # no video here (the photo must stay visible) — but keep the same background
                        rels = X.add_rel(rels, "rId93", "image", "../media/paint_poster.jpg")
                        data = X.set_bg_image(data, "rId93")
                    if n not in NO_VIDEO:
                        rels = X.add_rel(rels, "rId91", "video", "../media/paint_loop.mp4")
                        rels = X.add_rel(rels, "rId92", "video", "../media/paint_loop.mp4")
                        rels = X.add_rel(rels, "rId93", "image", "../media/paint_poster.jpg")
                        data = X.add_video_background(data, w=SLIDE_W, h=SLIDE_H, poster_rid="rId93",
                                                      video_link_rid="rId91", video_embed_rid="rId92")
                        data = X.set_bg_image(data, "rId93")  # same frame as a static fallback
                    data = X.set_fade(data, "med")
                    zout.writestr(rels_name, rels)
                zout.writestr(it, data)
            zout.writestr("[Content_Types].xml", ct)
            zout.writestr("ppt/media/paint_loop.mp4", video_bytes)
            zout.writestr("ppt/media/paint_poster.jpg", poster_bytes)
            zout.writestr("ppt/media/girl_with_doll.jpg", photo_bytes)
    shutil.move(tmp, OUT)
    print("\n".join(log))
    print(f"\n→ {OUT}  {OUT.stat().st_size/1048576:.2f} MB  ({time.time()-t0:.1f} s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
