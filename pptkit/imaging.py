"""Image operations used by every other module (and by the CLI `tools/img.py`).

Highlights
* cover()/contain()          — CSS object-fit semantics with focal point + zoom
* cover_crop_fractions()     — the same math expressed as PowerPoint srcRect crop fractions
* optimize()                 — resize + recompress for decks / web (JPEG / WebP / PNG)
* contact_sheet()            — labelled grid of many images in ONE picture (fast visual review)
* diff()                     — before/after pixel diff with heat-map + score
"""
from __future__ import annotations

import base64
import io
import math
from pathlib import Path
from typing import Iterable, Sequence

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps

from .env import FONTS_DIR

IMG_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff"}


# ----------------------------------------------------------------------------- basics
def open_image(path) -> Image.Image:
    im = Image.open(path)
    im = ImageOps.exif_transpose(im)
    if im.mode in ("P", "LA", "L"):
        im = im.convert("RGBA")
    elif im.mode not in ("RGB", "RGBA"):
        im = im.convert("RGB")
    return im


def info(path) -> dict:
    p = Path(path)
    with Image.open(p) as im:
        w, h = im.size
        return {"path": str(p), "w": w, "h": h, "aspect": round(w / h, 3), "mode": im.mode,
                "format": im.format, "kb": round(p.stat().st_size / 1024, 1)}


def font(size: int = 20, bold: bool = False) -> ImageFont.FreeTypeFont:
    cands = []
    if FONTS_DIR.exists():
        cands += sorted(FONTS_DIR.glob("Nunito-Bold*.ttf" if bold else "Nunito-Regular*.ttf"))
    cands += [Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else
                   "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")]
    for c in cands:
        if c.exists():
            return ImageFont.truetype(str(c), size)
    return ImageFont.load_default()


# ----------------------------------------------------------------------------- geometry
def cover_crop_fractions(src_w: float, src_h: float, dst_w: float, dst_h: float,
                         focus=(0.5, 0.5), zoom: float = 1.0) -> tuple[float, float, float, float]:
    """Fractions (left, top, right, bottom) to crop from the source so that it fills dst
    without distortion (object-fit: cover), centred on `focus` (0..1, 0..1), with extra `zoom`>=1.
    These map 1:1 onto PowerPoint's <a:srcRect l t r b> (in 1/1000 %)."""
    zoom = max(1.0, float(zoom))
    src_ar, dst_ar = src_w / src_h, dst_w / dst_h
    if src_ar > dst_ar:      # source wider -> crop sides
        vis_w, vis_h = dst_ar / src_ar, 1.0
    else:                    # source taller -> crop top/bottom
        vis_w, vis_h = 1.0, src_ar / dst_ar
    vis_w, vis_h = vis_w / zoom, vis_h / zoom
    fx, fy = focus
    left = min(max(fx - vis_w / 2, 0.0), 1.0 - vis_w)
    top = min(max(fy - vis_h / 2, 0.0), 1.0 - vis_h)
    return (left, top, 1.0 - vis_w - left, 1.0 - vis_h - top)


def cover(im: Image.Image, size: tuple[int, int], focus=(0.5, 0.5), zoom: float = 1.0) -> Image.Image:
    w, h = im.size
    l, t, r, b = cover_crop_fractions(w, h, size[0], size[1], focus, zoom)
    box = (round(l * w), round(t * h), round(w - r * w), round(h - b * h))
    return im.crop(box).resize(size, Image.LANCZOS)


def contain(im: Image.Image, size: tuple[int, int], bg=None) -> Image.Image:
    im2 = ImageOps.contain(im, size, Image.LANCZOS)
    if bg is None:
        return im2
    canvas = Image.new("RGBA" if len(bg) == 4 else "RGB", size, bg)
    canvas.paste(im2, ((size[0] - im2.width) // 2, (size[1] - im2.height) // 2),
                 im2 if im2.mode == "RGBA" else None)
    return canvas


def rounded(im: Image.Image, radius: int) -> Image.Image:
    im = im.convert("RGBA")
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, im.width - 1, im.height - 1), radius, fill=255)
    im.putalpha(ImageChops.multiply(im.getchannel("A"), mask))
    return im


def trim(im: Image.Image, tolerance: int = 8) -> Image.Image:
    """Remove uniform borders (e.g. white frame around a scanned picture)."""
    rgb = im.convert("RGB")
    bg = Image.new("RGB", rgb.size, rgb.getpixel((0, 0)))
    diff = ImageChops.difference(rgb, bg).convert("L").point(lambda v: 255 if v > tolerance else 0)
    box = diff.getbbox()
    return im.crop(box) if box else im


# ----------------------------------------------------------------------------- output
def optimize(src, dst, max_size=(1920, 1080), quality: int = 82, fmt: str | None = None,
             cover_size: tuple[int, int] | None = None, focus=(0.5, 0.5), zoom: float = 1.0) -> dict:
    """Resize (never upscale) + recompress. fmt: jpeg|webp|png (default from dst suffix)."""
    im = open_image(src) if not isinstance(src, Image.Image) else src
    if cover_size:
        im = cover(im, cover_size, focus, zoom)
    elif max_size:
        im = im.copy()
        im.thumbnail(max_size, Image.LANCZOS)
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    fmt = (fmt or dst.suffix.lstrip(".")).lower().replace("jpg", "jpeg")
    if fmt == "jpeg":
        if im.mode == "RGBA":
            bg = Image.new("RGB", im.size, (255, 255, 255))
            bg.paste(im, mask=im.getchannel("A"))
            im = bg
        im.convert("RGB").save(dst, "JPEG", quality=quality, optimize=True, progressive=True, subsampling="4:2:0")
    elif fmt == "webp":
        im.save(dst, "WEBP", quality=quality, method=6)
    else:
        im.save(dst, "PNG", optimize=True)
    return info(dst)


def to_data_uri(path, mime: str | None = None) -> str:
    p = Path(path)
    mime = mime or {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp",
                    ".svg": "image/svg+xml", ".gif": "image/gif", ".woff2": "font/woff2"}.get(p.suffix.lower(),
                                                                                         "application/octet-stream")
    return f"data:{mime};base64,{base64.b64encode(p.read_bytes()).decode()}"


# ----------------------------------------------------------------------------- review helpers
def collect(paths: Iterable) -> list[Path]:
    out: list[Path] = []
    for p in paths:
        p = Path(p)
        if p.is_dir():
            out += sorted(q for q in p.rglob("*") if q.suffix.lower() in IMG_EXT)
        elif p.suffix.lower() in IMG_EXT and p.exists():
            out.append(p)
    return out


def _thumb_open(p: Path, box_w: int) -> Image.Image:
    """Open an image already shrunk close to box_w (JPEG draft mode / integer reduce) — much faster."""
    im = Image.open(p)
    if im.format == "JPEG":
        im.draft("RGB", (box_w, box_w * 4))
    k = max(1, im.width // (box_w * 2))
    if k > 1:
        im = im.reduce(k)
    return ImageOps.exif_transpose(im)


def contact_sheet(items: Sequence, out, cols: int | None = None, thumb_w: int = 420, title: str | None = None,
                  labels: Sequence[str] | None = None, bg=(24, 26, 33), fit: str = "contain",
                  aspect: float | None = None) -> Path:
    """Grid of thumbnails with labels (name · WxH · KB). `items` = paths or PIL images."""
    imgs, labs = [], []
    for i, it in enumerate(items):
        if isinstance(it, Image.Image):
            im, lab = it, (labels[i] if labels else f"#{i + 1}")
        else:
            p = Path(it)
            try:
                with Image.open(p) as _probe:
                    full = _probe.size
                im = _thumb_open(p, thumb_w)
            except Exception as e:  # unreadable file -> red tile
                full = (400, 300)
                im = Image.new("RGB", (400, 300), (120, 0, 0))
                ImageDraw.Draw(im).text((10, 10), f"ERROR {e}", fill="white")
            lab = labels[i] if labels else f"{p.name} · {full[0]}×{full[1]} · {p.stat().st_size // 1024}KB"
        imgs.append(im)
        labs.append(lab)
    n = len(imgs) or 1
    if aspect is None:  # cell shape follows the images (portrait phone shots get tall cells)
        ar = sorted(im.width / im.height for im in imgs)[len(imgs) // 2] if imgs else 16 / 9
        aspect = 16 / 9 if ar > 1.2 else ar
    if cols is None:
        cols = min(4, max(1, math.ceil(math.sqrt(n)))) if aspect >= 1 else min(10, n)
    rows = math.ceil(n / cols)
    th = int(thumb_w / aspect)
    pad, lab_h = 14, 30
    top = 56 if title else pad
    W = cols * thumb_w + (cols + 1) * pad
    H = top + rows * (th + lab_h + pad) + pad
    sheet = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(sheet)
    f, fb = font(15), font(26, True)
    if title:
        d.text((pad, 14), title, font=fb, fill=(255, 255, 255))
    for i, (im, lab) in enumerate(zip(imgs, labs)):
        r, c = divmod(i, cols)
        x = pad + c * (thumb_w + pad)
        y = top + r * (th + lab_h + pad)
        tile = Image.new("RGB", (thumb_w, th), (40, 43, 52))
        t = cover(im.convert("RGB"), (thumb_w, th)) if fit == "cover" else ImageOps.contain(im.convert("RGBA"), (thumb_w, th))
        tile.paste(t, ((thumb_w - t.width) // 2, (th - t.height) // 2), t if t.mode == "RGBA" else None)
        sheet.paste(tile, (x, y))
        d.rectangle((x - 1, y - 1, x + thumb_w, y + th), outline=(70, 74, 86))
        txt = lab if d.textlength(lab, font=f) <= thumb_w else lab[: int(len(lab) * thumb_w / d.textlength(lab, font=f)) - 2] + "…"
        d.text((x + 2, y + th + 6), txt, font=f, fill=(220, 224, 232))
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.suffix.lower() in (".jpg", ".jpeg"):
        sheet.save(out, quality=88)
    else:
        sheet.save(out, compress_level=6)
    return out


def filmstrip(items: Sequence, out, height: int = 360, gap: int = 8, bg=(24, 26, 33)) -> Path:
    ims = [open_image(p) if not isinstance(p, Image.Image) else p for p in items]
    ims = [ImageOps.contain(im, (10_000, height)) for im in ims]
    W = sum(im.width for im in ims) + gap * (len(ims) + 1)
    sheet = Image.new("RGB", (W, height + 2 * gap), bg)
    x = gap
    for im in ims:
        sheet.paste(im.convert("RGB"), (x, gap))
        x += im.width + gap
    sheet.save(out)
    return Path(out)


def diff(a, b, out=None, threshold: int = 24) -> dict:
    """Compare two renders. Returns {'changed_pct', 'bbox'} and optionally writes a heat-map overlay."""
    ia, ib = open_image(a).convert("RGB"), open_image(b).convert("RGB")
    if ia.size != ib.size:
        ib = ib.resize(ia.size, Image.LANCZOS)
    d = ImageChops.difference(ia, ib).convert("L")
    mask = d.point(lambda v: 255 if v > threshold else 0)
    hist = mask.histogram()
    changed = hist[255] / (ia.width * ia.height)
    res = {"changed_pct": round(changed * 100, 3), "bbox": mask.getbbox()}
    if out:
        red = Image.new("RGB", ia.size, (255, 0, 64))
        over = Image.composite(red, ia.point(lambda v: int(v * 0.45)), mask.filter(ImageFilter.MaxFilter(5)))
        over.save(out)
        res["heatmap"] = str(out)
    return res


# ----------------------------------------------------------------------------- color
def luminance(rgb) -> float:
    def ch(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = rgb[:3]
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast_ratio(c1, c2) -> float:
    l1, l2 = sorted((luminance(c1), luminance(c2)), reverse=True)
    return round((l1 + 0.05) / (l2 + 0.05), 2)


def dominant_colors(im: Image.Image, k: int = 5) -> list[tuple[int, int, int]]:
    small = im.convert("RGB").copy()
    small.thumbnail((200, 200))
    q = small.quantize(colors=k, method=Image.MEDIANCUT)
    pal = q.getpalette()[: k * 3]
    counts = sorted(q.getcolors(), reverse=True)
    return [tuple(pal[i * 3: i * 3 + 3]) for _, i in counts]


def hex2rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i: i + 2], 16) for i in (0, 2, 4))
