"""Fonts: install toolkit fonts, make static instances of variable fonts, embed fonts into PPTX.

PowerPoint stores embedded fonts as EOT (Embedded OpenType) parts `/ppt/fonts/*.fntdata`
referenced from `<p:embeddedFontLst>` in presentation.xml. We write *uncompressed* EOT
(version 0x00020001, flags 0) — the same flavour Canva/LibreOffice produce — so decks keep
their typography on machines that do not have the font installed (PowerPoint Win/Mac).
"""
from __future__ import annotations

import io
import shutil
import struct
from pathlib import Path

from fontTools.subset import Options, Subsetter
from fontTools.ttLib import TTFont

from .env import CACHE, FONTS_DIR

GFONTS = CACHE / "src" / "gfonts"

# static weights generated from variable fonts: (family, axis value, style name)
WEIGHT_NAMES = {100: "Thin", 200: "ExtraLight", 300: "Light", 400: "Regular", 500: "Medium",
                600: "SemiBold", 700: "Bold", 800: "ExtraBold", 900: "Black"}

# metric-compatible substitutes so foreign decks render with correct line breaks
METRIC_FALLBACKS = [
    ["Arial", "Arimo", "Liberation Sans"], ["Helvetica", "Arimo"], ["Calibri", "Carlito"],
    ["Calibri Light", "Carlito"], ["Cambria", "Caladea"], ["Times New Roman", "Tinos"],
    ["Courier New", "Cousine"], ["Georgia", "Gelasio"], ["Segoe UI", "Open Sans"],
    ["Verdana", "DejaVu Sans"], ["Tahoma", "DejaVu Sans"], ["Comic Sans MS", "Comic Neue"],
    ["Century Gothic", "Didact Gothic"], ["Trebuchet MS", "Open Sans"], ["Arial Black", "Arimo"],
]


def _name(font: TTFont, nid: int) -> str:
    rec = font["name"].getName(nid, 3, 1, 0x409) or font["name"].getName(nid, 1, 0, 0)
    return str(rec) if rec else ""


def family_of(path) -> tuple[str, str]:
    f = TTFont(path, lazy=True)
    return _name(f, 1), _name(f, 2)


# ----------------------------------------------------------------------------- install
def instance_variable(src: Path, out_dir: Path, weights=(400, 600, 700, 800, 900)) -> list[Path]:
    """Create static TTFs from a variable font with Google-style names
    (e.g. family 'Nunito Black' / style 'Regular', typographic family 'Nunito')."""
    from fontTools.varLib.instancer import instantiateVariableFont
    out = []
    italic = "Italic" in src.name
    base = src.name.split("[")[0].replace("-Italic", "")
    for w in weights:
        f = TTFont(src)
        if "fvar" not in f or "wght" not in [a.axisTag for a in f["fvar"].axes]:
            return out
        axes = {a.axisTag: a for a in f["fvar"].axes}
        if not (axes["wght"].minValue <= w <= axes["wght"].maxValue):
            continue
        loc = {"wght": w}
        for tag, a in axes.items():
            if tag != "wght":
                loc[tag] = a.defaultValue
        inst = instantiateVariableFont(f, loc, inplace=False, updateFontNames=False)
        wname = WEIGHT_NAMES[w]
        typo_family = _name(f, 16) or _name(f, 1)
        if w in (400, 700):
            fam = typo_family
            sub = ("Bold " if w == 700 else "") + ("Italic" if italic else "")
            sub = sub.strip() or "Regular"
        else:
            fam = f"{typo_family} {wname}"
            sub = "Italic" if italic else "Regular"
        full = f"{typo_family} {wname}{' Italic' if italic else ''}".replace(" Regular Italic", " Italic")
        ps = f"{typo_family.replace(' ', '')}-{wname}{'Italic' if italic else ''}"
        name = inst["name"]
        for nid in (1, 2, 3, 4, 6, 16, 17, 25):
            name.removeNames(nameID=nid)
        name.setName(fam, 1, 3, 1, 0x409)
        name.setName(sub, 2, 3, 1, 0x409)
        name.setName(f"{ps};{_name(f, 5)}", 3, 3, 1, 0x409)
        name.setName(full, 4, 3, 1, 0x409)
        name.setName(ps, 6, 3, 1, 0x409)
        name.setName(typo_family, 16, 3, 1, 0x409)
        name.setName(f"{wname}{' Italic' if italic else ''}", 17, 3, 1, 0x409)
        os2 = inst["OS/2"]
        os2.usWeightClass = w
        sel = os2.fsSelection & ~(0b1100001)  # clear italic(0), bold(5), regular(6)
        if italic:
            sel |= 1
        if w == 700:
            sel |= 1 << 5
        if not italic and w != 700:
            sel |= 1 << 6
        os2.fsSelection = sel
        inst["head"].macStyle = (1 if w == 700 else 0) | (2 if italic else 0)
        for t in ("STAT", "MVAR", "HVAR", "VVAR", "avar", "fvar", "gvar", "cvar"):
            if t in inst:
                del inst[t]
        p = out_dir / f"{base}-{wname}{'Italic' if italic else ''}.ttf"
        inst.save(p)
        out.append(p)
    return out


# families that get the full weight ladder; every other variable family gets Regular + Bold
FULL_LADDER = {"Nunito", "Rubik", "Montserrat", "Inter", "Manrope", "Unbounded", "Comfortaa", "Oswald"}


def _instance_job(args):
    src, weights = args
    return [str(p) for p in instance_variable(Path(src), FONTS_DIR, weights=weights)]


def install_toolkit_fonts(verbose: bool = True, workers: int = 2) -> dict:
    """Copy all TTFs from the google/fonts sparse checkout into .cache/fonts and generate
    static instances for variable families (needed by PowerPoint + LibreOffice)."""
    from concurrent.futures import ProcessPoolExecutor
    FONTS_DIR.mkdir(parents=True, exist_ok=True)
    (CACHE / "fonts_variable").mkdir(parents=True, exist_ok=True)
    copied, jobs = 0, []
    for ttf in sorted(GFONTS.rglob("*.ttf")):
        if "[" in ttf.name:  # variable font: keep the VF for web use + make statics
            dst = CACHE / "fonts_variable" / ttf.name
            if not dst.exists():
                shutil.copy2(ttf, dst)
            stem = ttf.name.split("[")[0]
            italic = stem.endswith("-Italic")
            base = stem.replace("-Italic", "")
            probe = FONTS_DIR / f"{base}-{'Italic' if italic else 'Regular'}.ttf"
            if italic:
                probe = FONTS_DIR / f"{base}-RegularItalic.ttf"
            if not probe.exists():
                weights = (300, 400, 500, 600, 700, 800, 900) if base in FULL_LADDER else (400, 700)
                if italic and base not in FULL_LADDER:
                    weights = (400, 700)
                jobs.append((str(ttf), weights))
        else:
            dst = FONTS_DIR / ttf.name
            if not dst.exists():
                shutil.copy2(ttf, dst)
                copied += 1
    made = []
    if jobs:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            for r in ex.map(_instance_job, jobs):
                made += r
    res = {"copied": copied, "instanced": len(made), "jobs": len(jobs),
           "total_static": len(list(FONTS_DIR.glob("*.ttf")))}
    if verbose:
        print("fonts:", res)
    return res


@__import__("functools").lru_cache(maxsize=512)
def find_font(family: str, bold: bool = False, italic: bool = False) -> Path | None:
    """Find a static TTF in the toolkit font dir by legacy family name (nameID 1)."""
    want_style = ("Bold " if bold else "") + ("Italic" if italic else "")
    want_style = want_style.strip() or "Regular"
    from .env import EXTRA_FONT_DIRS
    best = None
    files = [f for d in EXTRA_FONT_DIRS for f in Path(d).glob("*.ttf")] + list(FONTS_DIR.glob("*.ttf"))
    for p in files:
        try:
            fam, sty = family_of(p)
        except Exception:
            continue
        if fam.lower() == family.lower():
            if sty.lower() == want_style.lower():
                return p
            best = best or p
    return best


def glyph_coverage(path, text: str) -> dict:
    cmap = TTFont(path, lazy=True).getBestCmap()
    missing = sorted({ch for ch in text if not ch.isspace() and ord(ch) not in cmap})
    return {"font": Path(path).name, "missing": "".join(missing), "ok": not missing}


# ----------------------------------------------------------------------------- subsetting / web
CYR_LAT = ("U+0000-00FF,U+0100-017F,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0300-0301,"
           "U+0370-03FF,U+0400-045F,U+0490-0491,U+04B0-04B1,U+2000-206F,U+20AC,U+2116,U+2122,U+2190-2199,"
           "U+2212,U+2215,U+FEFF,U+FFFD")


def _unicodes(ranges: str) -> list[int]:
    out = []
    for part in ranges.split(","):
        part = part.strip().replace("U+", "")
        if "-" in part:
            a, b = part.split("-")
            out += list(range(int(a, 16), int(b, 16) + 1))
        elif part:
            out.append(int(part, 16))
    return out


def subset(src, dst, text: str | None = None, unicodes: str = CYR_LAT, flavor: str | None = None,
           keep_layout: bool = True) -> Path:
    """Subset a font to `text` and/or unicode ranges. flavor='woff2' for the web."""
    f = TTFont(src)
    opts = Options()
    opts.layout_features = ["*"] if keep_layout else []
    opts.name_IDs = ["*"]
    opts.name_languages = ["*"]
    opts.notdef_outline = True
    opts.glyph_names = False
    opts.hinting = False
    if flavor:
        opts.flavor = flavor
    s = Subsetter(options=opts)
    s.populate(text=text or "", unicodes=_unicodes(unicodes) if unicodes else [])
    s.subset(f)
    if flavor:
        f.flavor = flavor
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    f.save(dst)
    return Path(dst)


# ----------------------------------------------------------------------------- EOT + PPTX embedding
def ttf_to_eot(ttf_bytes: bytes) -> bytes:
    """Wrap TrueType bytes into an uncompressed EOT (version 0x00020001)."""
    f = TTFont(io.BytesIO(ttf_bytes))
    os2, head = f["OS/2"], f["head"]
    panose = os2.panose
    pan = bytes([panose.bFamilyType, panose.bSerifStyle, panose.bWeight, panose.bProportion,
                 panose.bContrast, panose.bStrokeVariation, panose.bArmStyle, panose.bLetterForm,
                 panose.bMidline, panose.bXHeight])

    def u16s(s: str) -> bytes:
        b = s.encode("utf-16-le")
        return struct.pack("<H", len(b)) + b

    fam, sty, ver, full = _name(f, 1), _name(f, 2), _name(f, 5), _name(f, 4)
    italic = 1 if (os2.fsSelection & 1) else 0
    body = b"".join([
        struct.pack("<I", 0x00020001),         # Version
        struct.pack("<I", 0),                  # Flags (no MTX compression, no XOR)
        pan,
        struct.pack("<B", 1),                  # Charset DEFAULT_CHARSET
        struct.pack("<B", italic),
        struct.pack("<I", os2.usWeightClass),
        struct.pack("<H", os2.fsType),
        struct.pack("<H", 0x504C),             # MagicNumber
        struct.pack("<IIII", os2.ulUnicodeRange1, os2.ulUnicodeRange2, os2.ulUnicodeRange3, os2.ulUnicodeRange4),
        struct.pack("<II", getattr(os2, "ulCodePageRange1", 0), getattr(os2, "ulCodePageRange2", 0)),
        struct.pack("<I", head.checkSumAdjustment),
        struct.pack("<IIII", 0, 0, 0, 0),      # Reserved1..4
        struct.pack("<H", 0), u16s(fam),
        struct.pack("<H", 0), u16s(sty),
        struct.pack("<H", 0), u16s(ver),
        struct.pack("<H", 0), u16s(full),
        struct.pack("<H", 0), struct.pack("<H", 0),  # Padding5 + RootStringSize(0)
    ])
    eot_size = 8 + len(body) + len(ttf_bytes)
    return struct.pack("<II", eot_size, len(ttf_bytes)) + body + ttf_bytes


def parse_eot_header(data: bytes) -> dict:
    eot_size, font_size, version, flags = struct.unpack_from("<IIII", data, 0)
    magic = struct.unpack_from("<H", data, 34)[0]
    return {"eot_size": eot_size, "font_size": font_size, "version": hex(version), "flags": flags,
            "magic_ok": magic == 0x504C, "len": len(data)}


RT_FONT = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/font"
CT_FONT = "application/x-fontdata"


def embed_fonts(prs, faces: dict, subset_text: str | None = None, unicodes: str = CYR_LAT) -> list[dict]:
    """Embed fonts into a python-pptx Presentation.

    faces = {"Nunito": {"regular": path, "bold": path}, "Nunito Black": {"regular": path}}
    Fonts are subset to Latin+Cyrillic+Greek (+ `subset_text`) to keep the file small.
    """
    from lxml import etree
    from pptx.opc.package import Part
    from pptx.opc.packuri import PackURI

    pres_el = prs.part._element
    nsmap = {"p": "http://schemas.openxmlformats.org/presentationml/2006/main",
             "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
    P = "{%s}" % nsmap["p"]
    R = "{%s}" % nsmap["r"]
    old = pres_el.find(P + "embeddedFontLst")
    if old is not None:
        pres_el.remove(old)
    lst = etree.SubElement(pres_el, P + "embeddedFontLst")
    # schema order: ... sldSz, notesSz, smartTags?, embeddedFontLst, custShowLst?, photoAlbum?, custDataLst?,
    #               kinsoku?, defaultTextStyle?, modifyVerifier?, extLst?
    pres_el.remove(lst)
    anchor = pres_el.find(P + "smartTags")
    if anchor is None:
        anchor = pres_el.find(P + "notesSz")
    anchor.addnext(lst)

    report, n = [], 1
    existing = [p.partname for p in prs.part.package.iter_parts()]
    while any(str(pn).startswith(f"/ppt/fonts/font{n}.") for pn in existing):
        n += 1
    for typeface, styles in faces.items():
        ef = etree.SubElement(lst, P + "embeddedFont")
        fe = etree.SubElement(ef, P + "font")
        fe.set("typeface", typeface)
        fe.set("pitchFamily", "2")
        fe.set("charset", "0")
        for style in ("regular", "bold", "italic", "boldItalic"):
            src = styles.get(style)
            if not src:
                continue
            buf = io.BytesIO()
            tmp = CACHE / "tmp_font_subset.ttf"
            subset(src, tmp, text=subset_text, unicodes=unicodes)
            ttf = tmp.read_bytes()
            fs = TTFont(io.BytesIO(ttf))["OS/2"].fsType
            if fs & 0x0002:
                report.append({"typeface": typeface, "style": style, "skipped": "restricted licence (fsType)"})
                continue
            eot = ttf_to_eot(ttf)
            part = Part(PackURI(f"/ppt/fonts/font{n}.fntdata"), CT_FONT, prs.part.package, eot)
            rid = prs.part.relate_to(part, RT_FONT)
            se = etree.SubElement(ef, P + style)
            se.set(R + "id", rid)
            report.append({"typeface": typeface, "style": style, "part": f"font{n}.fntdata",
                           "kb": round(len(eot) / 1024, 1), "src": Path(src).name})
            n += 1
    pres_el.set("embedTrueTypeFonts", "1")
    return report
