"""Перекраска и мелкие правки картинок слайдов, когда нужен именно результат, а не перерисовка.

Здесь: webp → png (PowerPoint не читает webp — из-за него слайд 6 показывал
«Сейчас не удаётся отобразить рисунок»), фото для слайда 18 в пропорции 4:5.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image


def webp_to_png(src: Path, dst: Path) -> dict:
    im = Image.open(src)
    out = im.convert("RGBA") if im.mode in ("RGBA", "LA", "P") else im.convert("RGB")
    dst.parent.mkdir(parents=True, exist_ok=True)
    out.save(dst, "PNG", optimize=True)
    return {"src": src.name, "dst": dst.name, "size": out.size, "kb": round(dst.stat().st_size / 1024)}


def photo_4x5(src: Path, dst: Path, box: tuple[int, int, int, int], width: int = 1280) -> dict:
    im = Image.open(src).convert("RGB").crop(box)
    h = round(width * im.height / im.width)
    im = im.resize((width, h), Image.LANCZOS)
    im.save(dst, quality=92, subsampling=0, optimize=True, progressive=True)
    return {"dst": dst.name, "size": im.size, "kb": round(dst.stat().st_size / 1024)}
