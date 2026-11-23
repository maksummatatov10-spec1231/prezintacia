"""Office rendering through LibreOffice compiled to WebAssembly (no system LibreOffice needed).

render_slides(pptx) -> list of PNG paths, cached by sha256(file)+dpi+pages, so re-checking an
unchanged deck is instant. A PDF export is also available (render_pdf).
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import time
from pathlib import Path

from .env import JS_DIR, RENDER_CACHE, ROOT, font_dirs, node_bin


class RenderError(RuntimeError):
    pass


def sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _run(args: list[str], timeout: int = 300) -> dict:
    p = subprocess.run([node_bin(), str(JS_DIR / "office.mjs"), *args], cwd=ROOT, capture_output=True,
                       text=True, timeout=timeout)
    line = (p.stdout.strip().splitlines() or ["{}"])[-1]
    try:
        res = json.loads(line)
    except json.JSONDecodeError:
        res = {"ok": False, "error": p.stdout[-2000:] + p.stderr[-2000:]}
    if not res.get("ok"):
        raise RenderError(res.get("error") or p.stderr[-2000:])
    return res


# fallbacks configured in js/office.mjs — families listed here are *substituted* by metric clones
SUBSTITUTED = {"Arial": "Arimo", "Helvetica": "Arimo", "Arial Black": "Arimo", "Calibri": "Carlito",
               "Calibri Light": "Carlito", "Cambria": "Caladea", "Times New Roman": "Tinos", "Courier New": "Cousine",
               "Georgia": "Gelasio", "Segoe UI": "Open Sans", "Verdana": "DejaVu Sans", "Tahoma": "DejaVu Sans",
               "Comic Sans MS": "Comic Neue", "Century Gothic": "Didact Gothic", "Trebuchet MS": "Open Sans"}


def split_missing(missing: list[str]) -> tuple[dict, list[str]]:
    """-> ({requested: substitute}, [really missing families])"""
    sub = {m: SUBSTITUTED[m] for m in missing if m in SUBSTITUTED}
    return sub, [m for m in missing if m not in SUBSTITUTED]


# ---------------------------------------------------------------------------- per-slide hashing
def slide_hashes(src) -> list[str]:
    """Content hash of every slide INCLUDING everything it depends on (layout, master, theme, images,
    charts, slide size). Identical hash ⇒ identical render, so unchanged slides are never re-rendered."""
    import posixpath
    import zipfile
    from lxml import etree
    RNS = "{http://schemas.openxmlformats.org/package/2006/relationships}"
    with zipfile.ZipFile(src) as z:
        names = set(z.namelist())
        part_hash: dict[str, str] = {}

        def ph(name):
            if name not in part_hash:
                part_hash[name] = hashlib.sha1(z.read(name)).hexdigest() if name in names else "-"
            return part_hash[name]

        def rels_of(part):
            d, b = posixpath.split(part)
            rp = posixpath.join(d, "_rels", b + ".rels")
            if rp not in names:
                return []
            out = []
            for r in etree.fromstring(z.read(rp)).findall(RNS + "Relationship"):
                if r.get("TargetMode") == "External":
                    continue
                t = r.get("Target")
                tgt = posixpath.normpath(posixpath.join(d, t)) if not t.startswith("/") else t.lstrip("/")
                out.append((r.get("Type", "").rsplit("/", 1)[-1], r.get("Id"), tgt, rp))
            return out

        pres = etree.fromstring(z.read("ppt/presentation.xml"))
        P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
        R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
        glob = hashlib.sha1()
        for tag in ("sldSz", "defaultTextStyle"):
            el = pres.find(P + tag)
            if el is not None:
                glob.update(etree.tostring(el))
        prels = {rid: tgt for _, rid, tgt, _ in rels_of("ppt/presentation.xml")}
        out = []
        for sid in pres.find(P + "sldIdLst") if pres.find(P + "sldIdLst") is not None else []:
            part = prels[sid.get(R + "id")]
            h = hashlib.sha1(glob.digest())
            seen, stack = set(), [part]
            while stack:
                cur = stack.pop()
                if cur in seen:
                    continue
                seen.add(cur)
                h.update(cur.encode() + ph(cur).encode())
                for kind, _, tgt, rp in rels_of(cur):
                    if kind in ("notesSlide", "slide", "notesMaster", "handoutMaster", "tags"):
                        continue
                    h.update(ph(rp).encode())
                    stack.append(tgt)
            h.update(sid.get("show", "1").encode() if hasattr(sid, "get") else b"")
            out.append(h.hexdigest()[:24])
    return out


def render_slides(src, dpi: int = 144, pages: list[int] | None = None, use_cache: bool = True,
                  incremental: bool = True) -> dict:
    """Render every slide (or `pages`, 1-based) to PNG. Unchanged slides come from the per-slide
    cache (milliseconds); only new/changed slides are rendered by LibreOffice. Returns
    {'images': [Path...], 'cached': bool, 'ms': int, 'missingFonts': [...], 'rendered': [n...], 'dir': Path}."""
    src = Path(src).resolve()
    if incremental and use_cache:
        return _render_incremental(src, dpi, pages)
    t = time.time()
    key = f"{sha256(src)[:20]}_{dpi}_{'-'.join(map(str, pages)) if pages else 'all'}"
    out = RENDER_CACHE / key
    meta = out / "result.json"
    if use_cache and meta.exists():
        res = json.loads(meta.read_text())
        res["images"] = [Path(p) for p in res["images"]]
        res["cached"] = True
        res["ms"] = int((time.time() - t) * 1000)
        return res
    tmp = RENDER_CACHE / (key + ".tmp")
    if tmp.exists():
        shutil.rmtree(tmp)
    RENDER_CACHE.mkdir(parents=True, exist_ok=True)
    args = ["images", "--input", str(src), "--outdir", str(tmp), "--dpi", str(dpi),
            "--fonts", ":".join(font_dirs())]
    if pages:
        args += ["--pages", ",".join(map(str, pages))]
    res = _run(args)
    if out.exists():
        shutil.rmtree(out)
    tmp.rename(out)
    images = sorted(out.glob("*.png"))
    result = {"images": [str(p) for p in images], "missingFonts": res.get("missingFonts", []),
              "pageCount": res.get("pageCount"), "dpi": dpi, "dir": str(out), "engine_ms": res.get("ms")}
    meta.write_text(json.dumps(result, ensure_ascii=False, indent=1))
    result["images"] = images
    result["cached"] = False
    result["ms"] = int((time.time() - t) * 1000)
    return result


def _render_incremental(src: Path, dpi: int, pages: list[int] | None) -> dict:
    t = time.time()
    hashes = slide_hashes(src)
    want = pages or list(range(1, len(hashes) + 1))
    sdir = RENDER_CACHE / "slides"
    sdir.mkdir(parents=True, exist_ok=True)
    paths = {n: sdir / f"{hashes[n - 1]}_{dpi}.png" for n in want}
    todo = [n for n in want if not paths[n].exists()]
    missing_fonts: list[str] = []
    meta_f = sdir / "fonts.json"
    fonts_meta = json.loads(meta_f.read_text()) if meta_f.exists() else {}
    if todo:
        tmp = RENDER_CACHE / f"tmp_{hashes[todo[0] - 1]}_{int(t * 1000)}"
        args = ["images", "--input", str(src), "--outdir", str(tmp), "--dpi", str(dpi),
                "--fonts", ":".join(font_dirs())]
        if len(todo) < len(hashes):
            args += ["--pages", ",".join(map(str, todo))]
        res = _run(args)
        imgs = res.get("images") or []
        by_page = {int(i["page"]): Path(i["path"]) for i in imgs if "page" in i}
        if not by_page:
            files = sorted(tmp.glob("*.png"))
            by_page = dict(zip(todo, files)) if len(files) == len(todo) else \
                {n: files[n - 1] for n in todo if n - 1 < len(files)}
        for n in todo:
            if n in by_page and Path(by_page[n]).exists():
                shutil.move(str(by_page[n]), paths[n])
        shutil.rmtree(tmp, ignore_errors=True)
        missing_fonts = res.get("missingFonts", [])
        for n in todo:
            fonts_meta[hashes[n - 1]] = missing_fonts
        meta_f.write_text(json.dumps(fonts_meta))
    else:
        for n in want:
            missing_fonts += [f for f in fonts_meta.get(hashes[n - 1], []) if f not in missing_fonts]
    images = [paths[n] for n in want if paths[n].exists()]
    return {"images": images, "cached": not todo, "rendered": todo, "missingFonts": missing_fonts,
            "pageCount": len(hashes), "dpi": dpi, "dir": str(sdir), "hashes": [hashes[n - 1] for n in want],
            "ms": int((time.time() - t) * 1000)}


def render_pdf(src, out_pdf) -> dict:
    src, out_pdf = Path(src).resolve(), Path(out_pdf).resolve()
    if out_pdf.exists():
        out_pdf.unlink()
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    return _run(["pdf", "--input", str(src), "--output", str(out_pdf), "--fonts", ":".join(font_dirs())])


def convert(src, out) -> dict:
    out = Path(out).resolve()
    if out.exists():
        out.unlink()
    return _run(["convert", "--input", str(Path(src).resolve()), "--output", str(out), "--fonts", ":".join(font_dirs())])


def pdf_to_png(pdf, out_dir, dpi: int = 110, pages: list[int] | None = None) -> list[Path]:
    import pymupdf
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open(str(pdf))
    paths = []
    for i, page in enumerate(doc, 1):
        if pages and i not in pages:
            continue
        pix = page.get_pixmap(dpi=dpi)
        p = out_dir / f"page-{i:04d}.png"
        pix.save(str(p))
        paths.append(p)
    return paths
