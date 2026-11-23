"""Quality checks for a deck (works on the dict produced by inspect.inspect_deck).

Checks: text overflow (measured with real font metrics), overlapping text, shapes off the slide,
small fonts, too much text, low-resolution / stretched pictures, missing fonts, empty placeholders,
missing alt-text, colour contrast (solid fills AND sampled from the rendered slide image).
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageFont

from .env import FONTS_DIR
from .imaging import contrast_ratio, hex2rgb
from .units import EMU_PER_IN, EMU_PER_PT

SEV_ORDER = {"error": 0, "warn": 1, "info": 2}

DEFAULTS = {
    "min_pt": 14,            # smallest acceptable font size
    "max_words": 80,         # words per slide before warning
    "min_dpi": 96,           # effective picture resolution at display size (full-HD slide = 144)
    "min_contrast": 3.0,     # WCAG large text = 3.0, normal = 4.5
    "overlap_pct": 8,        # % of the smaller text box covered by another text box
}


@lru_cache(maxsize=256)
def _font_path(name: str | None, bold: bool) -> str | None:
    from .fonts import METRIC_FALLBACKS, find_font
    cands = [name] if name else []
    for row in METRIC_FALLBACKS:
        if name and row[0].lower() == name.lower():
            cands += row[1:]
    cands += ["Carlito", "Arimo", "Nunito"]
    for c in cands:
        if not c:
            continue
        p = find_font(c, bold=bold)
        if p:
            return str(p)
    dv = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    return str(dv) if dv.exists() else None


@lru_cache(maxsize=1024)
def _pil_font(path: str | None, px: int):
    if not path:
        return ImageFont.load_default()
    return ImageFont.truetype(path, max(1, px))


def estimate_text_height(paragraphs: list[tuple[str, float, str | None, bool]], box_w_emu: int,
                         line_spacing: float = 1.0) -> int:
    """paragraphs: [(text, size_pt, font_name, bold)] -> estimated height in EMU (wrap at box width)."""
    total = 0.0
    scale = 4  # measure at 4 px per pt for precision
    width_px = box_w_emu / EMU_PER_PT * scale
    for text, size, fname, bold in paragraphs:
        size = size or 18
        f = _pil_font(_font_path(fname, bold), int(size * scale))
        asc, desc = f.getmetrics()
        lh = (asc + desc) * line_spacing
        lines = 0
        for hard in (text or " ").split("\n") or [" "]:
            words, cur = hard.split(" "), ""
            n = 1
            for w in words:
                trial = (cur + " " + w).strip() if cur else w
                if f.getlength(trial) <= width_px or not cur:
                    cur = trial
                else:
                    n += 1
                    cur = w
            lines += n
        total += lines * lh
    return int(total / scale * EMU_PER_PT)


def _walk(shapes):
    for s in shapes:
        yield s
        yield from _walk(s.get("children", []))


def _issue(issues, slide, sev, code, msg, shape=None, fix=None):
    issues.append({"slide": slide, "severity": sev, "code": code, "message": msg,
                   "shape_id": shape["id"] if shape else None, "shape": shape["name"] if shape else None,
                   "fix": fix})


def lint(info: dict, renders: list | None = None, opts: dict | None = None, prs=None) -> list[dict]:
    """Return a list of issues. `renders` = slide PNG paths (optional, enables contrast sampling)."""
    o = {**DEFAULTS, **(opts or {})}
    issues: list[dict] = []
    sw, sh_ = info["slide_size"]["w"], info["slide_size"]["h"]
    available = {p.stem.split("-")[0].lower() for p in FONTS_DIR.glob("*.ttf")} if FONTS_DIR.exists() else set()
    from .fonts import find_font
    embedded = {f["typeface"].lower() for f in info.get("embedded_fonts", [])}
    for fname in info.get("fonts_used", {}):
        clean = fname.replace(" (theme)", "")
        if clean.startswith("+"):
            continue
        if clean.lower() not in embedded and not find_font(clean):
            from .fonts import METRIC_FALLBACKS
            sub = next((r[1] for r in METRIC_FALLBACKS if r[0].lower() == clean.lower()), None)
            _issue(issues, None, "info" if sub else "warn", "font-missing",
                   f"Шрифт «{clean}» не установлен в тулките" + (f" — рендер использует метрический аналог {sub}" if sub else
                                                              " — рендер подставит другой шрифт; переносы строк могут отличаться"),
                   fix="tools/fonts.py add <семейство> или встроить шрифт")
    for s in info["slides"]:
        si = s["index"]
        if s["hidden"]:
            _issue(issues, si, "info", "hidden", "Слайд скрыт (не показывается в режиме показа)")
        if s["words"] > o["max_words"]:
            _issue(issues, si, "warn", "too-much-text", f"Много текста: {s['words']} слов (рекомендуется ≤ {o['max_words']})",
                   fix="разбить на 2 слайда или сократить")
        texts = []
        img = None
        if renders and si - 1 < len(renders) and renders[si - 1]:
            try:
                img = Image.open(renders[si - 1]).convert("RGB")
            except Exception:
                img = None
        for shp in _walk(s["shapes"]):
            x, y, w, h = shp["x"], shp["y"], shp["w"], shp["h"]
            t = shp.get("text")
            has_text = bool(t and t["text"].strip())
            # --- off slide
            tol_x, tol_y = sw * 0.004, sh_ * 0.004
            if w and h and (x < -tol_x or y < -tol_y or x + w > sw + tol_x or y + h > sh_ + tol_y):
                fully = x >= sw or y >= sh_ or x + w <= 0 or y + h <= 0
                if fully:
                    _issue(issues, si, "warn", "off-slide", "Фигура целиком за пределами слайда", shp, "move или delete")
                elif has_text:
                    _issue(issues, si, "error", "text-off-slide", "Текстовая фигура выходит за край слайда", shp,
                           "move/resize внутрь слайда")
                elif shp["kind"] not in ("picture",) or not (x <= tol_x and y <= tol_y):
                    _issue(issues, si, "info", "bleed", "Фигура выходит за край слайда (обрезается при показе)", shp)
            # --- empty placeholder
            if shp["kind"].startswith("placeholder") and not has_text and "picture" not in shp and shp["kind"] not in (
                    "placeholder:picture",):
                _issue(issues, si, "warn", "empty-placeholder", "Пустой заполнитель (в редакторе видно «Щелкните, чтобы добавить…»)",
                       shp, "delete")
            # --- pictures
            pic = shp.get("picture")
            if pic and pic.get("px"):
                dpi = pic.get("effective_dpi", 999)
                if dpi < o["min_dpi"]:
                    _issue(issues, si, "warn" if dpi >= 72 else "error", "low-res",
                           f"Низкое разрешение картинки: ≈{dpi} dpi при текущем размере ({pic['px'][0]}×{pic['px'][1]} px)",
                           shp, "заменить картинку на более крупную или уменьшить рамку")
                dist = pic.get("distortion", 1)
                if abs(dist - 1) > 0.03:
                    _issue(issues, si, "error", "stretched", f"Картинка искажена (растянута) ×{dist}", shp,
                           "edit fit --mode cover (обрезка вместо растяжения)")
                if not pic.get("alt"):
                    _issue(issues, si, "info", "no-alt", "Нет альтернативного текста у картинки", shp)
            # --- text
            if has_text:
                sizes = t["sizes_pt"]
                if sizes:
                    mn = min(sizes)
                    if mn < o["min_pt"]:
                        _issue(issues, si, "warn", "small-font", f"Мелкий шрифт {mn} pt (минимум {o['min_pt']} pt)", shp,
                               "font --size")
                texts.append(shp)
                # overflow estimation (skip when autofit resizes the shape)
                if t.get("autofit") != "resize-shape" and w and h:
                    paras = []
                    dsize = max(sizes, key=sizes.get) if sizes else 18
                    for p in t["paragraphs"]:
                        paras.append((p["text"], dsize, next(iter(t["fonts"]), None), False))
                    scale = 1.0
                    if t.get("autofit", "") and t["autofit"].startswith("shrink"):
                        try:
                            scale = float(t["autofit"].split("=")[1].rstrip("%)")) / (100000 if "%" not in t["autofit"] else 100)
                        except Exception:
                            scale = 1.0
                        if scale > 1:
                            scale /= 1000
                    ins = t.get("insets") or {}
                    inset_w = ins.get("lIns", 91440) + ins.get("rIns", 91440)
                    inset_h = ins.get("tIns", 45720) + ins.get("bIns", 45720)
                    est = estimate_text_height([(a, b * scale, c, d) for a, b, c, d in paras], max(1, w - inset_w),
                                               t.get("line_spacing", 1.0))
                    if est > (h - inset_h) * 1.12 + 0.03 * EMU_PER_IN and t.get("wrap") != "none":
                        bottom = y + est + inset_h
                        sev = "error" if bottom > sh_ else "warn"
                        _issue(issues, si, sev, "text-overflow",
                               f"Текст, вероятно, не помещается в рамку: нужно ≈{est / 360000:.1f} см, есть {h / 360000:.1f} см"
                               + (" — и выходит за низ слайда" if bottom > sh_ else ""), shp,
                               "resize по высоте, уменьшить шрифт или сократить текст")
                # contrast (decorative shapes named "deco…" are skipped)
                cols = t.get("colors") or {}
                if cols and not shp["name"].lower().startswith("deco"):
                    txt_rgb = hex2rgb(max(cols, key=cols.get))
                    bg_rgb = None
                    if shp.get("fill", {}).get("type") == "solid" and shp["fill"].get("rgb"):
                        bg_rgb = hex2rgb(shp["fill"]["rgb"])
                    elif img is not None and w and h:
                        sx, sy = img.width / sw, img.height / sh_
                        box = (max(0, int(x * sx)), max(0, int(y * sy)), min(img.width, int((x + w) * sx)),
                               min(img.height, int((y + h) * sy)))
                        if box[2] > box[0] + 2 and box[3] > box[1] + 2:
                            reg = img.crop(box).resize((48, 24))
                            px = [p for p in reg.getdata() if sum(abs(a - b) for a, b in zip(p, txt_rgb)) > 90]
                            if len(px) > 20:
                                bg_rgb = tuple(sum(c[i] for c in px) // len(px) for i in range(3))
                    if bg_rgb:
                        cr = contrast_ratio(txt_rgb, bg_rgb)
                        if cr < o["min_contrast"]:
                            _issue(issues, si, "warn", "low-contrast",
                                   f"Низкий контраст текста {cr}:1 (текст #{'%02X%02X%02X' % txt_rgb} на фоне ≈#{'%02X%02X%02X' % bg_rgb})",
                                   shp, "темнее/светлее цвет текста или подложка под текстом")
        # overlapping text boxes — compares the *content* areas (box minus insets), so a badge that
        # sits inside a button's empty inset area is not reported
        def content(sh):
            ins = (sh.get("text") or {}).get("insets") or {}
            x0 = sh["x"] + ins.get("lIns", 91440)
            y0 = sh["y"] + ins.get("tIns", 45720)
            x1 = sh["x"] + sh["w"] - ins.get("rIns", 91440)
            y1 = sh["y"] + sh["h"] - ins.get("bIns", 45720)
            return x0, y0, max(x0, x1), max(y0, y1)

        for i in range(len(texts)):
            for j in range(i + 1, len(texts)):
                a, b = texts[i], texts[j]
                if a["rot"] or b["rot"]:
                    continue
                ax0, ay0, ax1, ay1 = content(a)
                bx0, by0, bx1, by1 = content(b)
                ix = max(0, min(ax1, bx1) - max(ax0, bx0))
                iy = max(0, min(ay1, by1) - max(ay0, by0))
                inter = ix * iy
                small = min((ax1 - ax0) * (ay1 - ay0), (bx1 - bx0) * (by1 - by0)) or 1
                if inter / small * 100 > o["overlap_pct"]:
                    _issue(issues, si, "warn", "text-overlap",
                           f"Текстовые фигуры перекрываются: «{a['name']}» и «{b['name']}» ({inter / small * 100:.0f}%)", b,
                           "move одну из фигур")
    issues.sort(key=lambda d: (d["slide"] or 0, SEV_ORDER[d["severity"]]))
    return issues


def to_markdown(issues: list[dict]) -> str:
    if not issues:
        return "## Проверка качества\n\n✅ Проблем не найдено.\n"
    icon = {"error": "🛑", "warn": "⚠️", "info": "ℹ️"}
    cnt = {k: sum(1 for i in issues if i["severity"] == k) for k in icon}
    L = [f"## Проверка качества\n\n🛑 ошибок: **{cnt['error']}** · ⚠️ предупреждений: **{cnt['warn']}** · ℹ️ заметок: {cnt['info']}\n",
         "| Слайд | | Код | Фигура | Описание | Как исправить |", "|---|---|---|---|---|---|"]
    for i in issues:
        L.append(f"| {i['slide'] or '—'} | {icon[i['severity']]} | `{i['code']}` | {i['shape'] or ''}"
                 f"{' (id ' + str(i['shape_id']) + ')' if i['shape_id'] else ''} | {i['message']} | {i['fix'] or ''} |")
    return "\n".join(L) + "\n"
