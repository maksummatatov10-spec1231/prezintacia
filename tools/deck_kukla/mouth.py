"""Recolour the red clay mouth of the doll → black (slides 13–15), keeping shading and anti-aliased edges.

How: in the face area find red pixels (HSV), split them into connected components (two cheeks + mouth),
take the wide component between the cheeks = mouth, then re-composite every mouth pixel as
    face_colour + alpha · (dark_shaded − face_colour)
where alpha is how much "mouth red" the pixel contains (edge pixels are a mix of red and the white face).
Cheeks, eyes and everything else stay bit-for-bit untouched.
"""
from __future__ import annotations

from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image


def _hsv(a: np.ndarray):
    rgb = a.astype(np.float32) / 255.0
    mx, mn = rgb.max(-1), rgb.min(-1)
    d = mx - mn + 1e-6
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    h = np.where(mx == r, ((g - b) / d) % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) * 60
    s = np.where(mx > 0, (mx - mn) / (mx + 1e-6), 0)
    return h, s, mx


def _components(mask: np.ndarray):
    seen = np.zeros_like(mask, bool)
    comps = []
    H, W = mask.shape
    for y0, x0 in zip(*np.nonzero(mask)):
        if seen[y0, x0]:
            continue
        q, pts = deque([(y0, x0)]), []
        seen[y0, x0] = True
        while q:
            y, x = q.popleft()
            pts.append((y, x))
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    yy, xx = y + dy, x + dx
                    if 0 <= yy < H and 0 <= xx < W and mask[yy, xx] and not seen[yy, xx]:
                        seen[yy, xx] = True
                        q.append((yy, xx))
        comps.append(np.array(pts))
    return comps


def _dilate(m: np.ndarray, n: int = 1) -> np.ndarray:
    for _ in range(n):
        r = m.copy()
        r[1:] |= m[:-1]; r[:-1] |= m[1:]; r[:, 1:] |= m[:, :-1]; r[:, :-1] |= m[:, 1:]
        m = r
    return m


def _erode(m: np.ndarray, n: int = 1) -> np.ndarray:
    return ~_dilate(~m, n)


def find_mouth(img: Image.Image, face_box):
    """Mouth = the most elongated red component between the cheeks.
    Thin red 'bridges' (soft images) are broken by a 1-px erosion, then the mouth is grown back
    inside the red mask but never into the cheek zones."""
    x0, y0, x1, y1 = face_box
    a = np.asarray(img.convert("RGB"))[y0:y1, x0:x1]
    h, s, v = _hsv(a)
    loose = ((h >= 330) | (h <= 20)) & (s > 0.30) & (v > 0.30)
    strict = ((h >= 335) | (h <= 16)) & (s > 0.50) & (v > 0.35)
    seeds = _erode(strict, 1)
    comps = [c for c in _components(seeds) if len(c) >= 12]
    info = []
    for c in comps:
        ys, xs = c[:, 0], c[:, 1]
        info.append({"n": len(c), "cx": xs.mean(), "cy": ys.mean(), "w": int(xs.max() - xs.min() + 1),
                     "h": int(ys.max() - ys.min() + 1), "pts": c})
    mouth = max(info, key=lambda d: d["w"] / d["h"])
    others = np.zeros(seeds.shape, bool)
    for d in info:
        if d is not mouth:
            others[d["pts"][:, 0], d["pts"][:, 1]] = True
    cheek_zone = _dilate(others, 4)
    core = np.zeros(seeds.shape, bool)
    core[mouth["pts"][:, 0], mouth["pts"][:, 1]] = True
    for _ in range(3):  # geodesic growth back to the real mouth edge
        core = _dilate(core, 1) & loose & ~cheek_zone
    return core, cheek_zone, a, info, mouth


def _blur(a: np.ndarray, r: int) -> np.ndarray:
    from PIL import ImageFilter
    return np.asarray(Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(r)), np.float32)


def recolor(src: Path, dst: Path, face_box, dark=(24, 21, 23), rim=(92, 84, 86), quality=95, debug: Path | None = None) -> dict:
    img = Image.open(src).convert("RGB")
    core, cheek_zone, a, info, mouth = find_mouth(img, face_box)
    af = a.astype(np.float32)
    hh_, ss_, vv_ = _hsv(a)
    redish = ((hh_ >= 330) | (hh_ <= 20)) & (ss_ > 0.3)
    white = (ss_ < 0.12) & (vv_ > 0.78) & ~_dilate(redish, 3)
    face = np.median(af[white], 0) if white.sum() > 30 else np.array([236, 232, 230], np.float32)
    reg = _dilate(core, 2) & ~cheek_zone
    zone = _dilate(reg, 6)
    # local background (face colour incl. its soft shading): fill the mouth and blur
    bgfill = af.copy()
    bgfill[zone] = face
    bg = _blur(bgfill, 7)
    # soft coverage: how much "red clay" a pixel holds (0 = bare face, 1 = solid mouth)
    redc = np.median(af[_erode(core, 1)] if _erode(core, 1).sum() > 20 else af[core], 0)
    dvec = face - redc
    alpha = np.clip(((face - af) @ dvec) / (dvec @ dvec), 0, 1)
    cov = np.where(reg, np.clip((alpha - 0.18) / 0.62, 0, 1), 0.0)
    cov = np.where(core, np.maximum(cov, 0.92), cov)
    # clay shading: darker in the middle of the stick, slightly lighter on the rounded rim
    dist = np.zeros(core.shape, np.float32)
    todo = core.copy()
    for step in range(1, 5):
        todo = _dilate(todo, 1) & reg & (dist == 0) & ~core
        dist[todo] = step
    t = np.clip(dist / 3.5, 0, 1)[..., None]
    shade = np.array(dark, np.float32)[None, None, :] * (1 - t) + np.array(rim, np.float32)[None, None, :] * t
    out = bg * (1 - cov[..., None]) + shade * cov[..., None]
    res = np.where((cov > 0)[..., None], out, af)
    full = np.asarray(img).copy()
    x0, y0, x1, y1 = face_box
    full[y0:y1, x0:x1] = np.clip(res + 0.5, 0, 255).astype(np.uint8)
    out_img = Image.fromarray(full)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.suffix.lower() in (".jpg", ".jpeg"):
        out_img.save(dst, quality=quality, subsampling=0, optimize=True)
    else:
        out_img.save(dst)
    diff = np.abs(np.asarray(out_img, np.int16) - np.asarray(img, np.int16)).sum(-1)
    if debug:
        z = 4
        bx = tuple(face_box)
        before = img.crop(bx).resize(((bx[2] - bx[0]) * z, (bx[3] - bx[1]) * z), Image.NEAREST)
        after = out_img.crop(bx).resize(before.size, Image.NEAREST)
        sheet = Image.new("RGB", (before.width * 2 + 10, before.height), (20, 20, 20))
        sheet.paste(before, (0, 0)); sheet.paste(after, (before.width + 10, 0))
        sheet.save(debug)
    ys, xs = np.nonzero(diff > 6)
    return {"mouth": (int(core.sum()), mouth["w"], mouth["h"]), "face": face.round().tolist(),
            "changed_px": int((diff > 6).sum()),
            "changed_bbox": (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())) if len(xs) else None}
