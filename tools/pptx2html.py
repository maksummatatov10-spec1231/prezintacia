#!/usr/bin/env python3
"""pptx2html — ANY .pptx → one self-contained .html for phones (swipe, tap, keys, fullscreen, notes).

  python tools/pptx2html.py deck.pptx                    # → presentations/<deck>.html
  python tools/pptx2html.py deck.pptx -o out.html --dpi 180 --notes

Slides are rendered by LibreOffice (exact layout of the .pptx, incremental cache) and embedded as WebP,
so the file opens offline in any phone browser / Telegram / Google Drive preview. Landscape: slide fills
the screen; portrait: slide on top, speaker notes / text below (readable on a narrow screen).
Contract for the screenshot tools: window.DECK (count, go, audit) + ?static=1 — so check.py works on it.
"""
from __future__ import annotations

import argparse
import base64
import html
import io
import sys
import time
from pathlib import Path

import _boot  # noqa: F401

from PIL import Image

from pptkit import office
from pptkit.env import ROOT
from pptkit.inspect import inspect_deck

PAGE = """<!doctype html><html lang="ru" class="nojs"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="generator" content="pptkit-deck"><meta name="theme-color" content="#111827"><title>{title}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}html,body{{height:100%;background:#0b1220;color:#e5e7eb;
font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;overscroll-behavior:none}}body{{overflow:hidden;touch-action:pan-y pinch-zoom}}
.s{{position:fixed;inset:0;display:none;flex-direction:column;align-items:center;justify-content:center}}
.s.on{{display:flex;animation:in .35s ease both}}@keyframes in{{from{{opacity:0}}to{{opacity:1}}}}.static .s.on{{animation:none}}
.s img{{display:block;max-width:100vw;max-height:100vh;width:auto;height:auto;box-shadow:0 10px 40px rgba(0,0,0,.5)}}
.n{{display:none}}
@media (orientation:portrait){{.s{{justify-content:flex-start;overflow-y:auto}}.s img{{width:100vw;height:auto;margin-top:max(8px,env(safe-area-inset-top))}}
 .n{{display:block;width:100%;padding:16px 18px 90px;font-size:16px;line-height:1.5;color:#cbd5e1;white-space:pre-wrap}}
 .n b{{display:block;color:#fff;font-size:18px;margin-bottom:6px}}}}
.nojs body{{overflow:auto}}.nojs .s{{display:flex;position:relative;inset:auto;padding:10px 0}}.nojs #nav,.nojs #bar{{display:none}}
#bar{{position:fixed;left:0;top:0;height:3px;background:#f59e0b;z-index:9;transition:width .3s}}
#nav{{position:fixed;left:50%;bottom:max(10px,env(safe-area-inset-bottom));transform:translateX(-50%);z-index:9;display:flex;gap:8px;
 align-items:center;background:rgba(17,24,39,.75);backdrop-filter:blur(8px);padding:6px 8px;border-radius:99px;font:600 14px system-ui}}
#nav button{{border:0;background:rgba(255,255,255,.12);color:#fff;width:40px;height:34px;border-radius:99px;font-size:18px}}
#nav span{{min-width:64px;text-align:center}}
</style></head><body><div id="bar"></div>{slides}
<div id="nav"><button id="p" aria-label="Назад">‹</button><span id="c"></span><button id="x" aria-label="Вперёд">›</button>
<button id="f" aria-label="Во весь экран">⤢</button></div>
<script>
(()=>{{document.documentElement.classList.remove('nojs');const q=new URLSearchParams(location.search),S=q.has('static');if(S)document.documentElement.classList.add('static');
const sl=[...document.querySelectorAll('.s')],N=sl.length;let cur=-1;const bar=document.getElementById('bar'),c=document.getElementById('c');
function go(i){{i=Math.max(0,Math.min(N-1,i));sl.forEach((s,k)=>s.classList.toggle('on',k===i));cur=i;sl[i].scrollTop=0;
 bar.style.width=((i+1)/N*100)+'%';c.textContent=(i+1)+' / '+N;history.replaceState(null,'','#'+(i+1));
 const im=sl[i].querySelector('img');return im.decode?im.decode().catch(()=>{{}}):Promise.resolve();}}
document.getElementById('p').onclick=()=>go(cur-1);document.getElementById('x').onclick=()=>go(cur+1);
document.getElementById('f').onclick=()=>{{const d=document.documentElement;(document.fullscreenElement?document.exitFullscreen():(d.requestFullscreen||d.webkitRequestFullscreen).call(d))}};
addEventListener('keydown',e=>{{if(['ArrowRight','PageDown',' '].includes(e.key))go(cur+1);else if(['ArrowLeft','PageUp'].includes(e.key))go(cur-1);
 else if(e.key==='Home')go(0);else if(e.key==='End')go(N-1)}});
let sx=0,sy=0,t0=0,m=false;addEventListener('touchstart',e=>{{sx=e.touches[0].clientX;sy=e.touches[0].clientY;t0=Date.now();m=e.touches.length>1}},{{passive:true}});
addEventListener('touchend',e=>{{if(m||(window.visualViewport&&visualViewport.scale>1.05))return;const t=e.changedTouches[0],dx=t.clientX-sx,dy=t.clientY-sy;
 if(Math.abs(dx)>50&&Math.abs(dx)>Math.abs(dy)*1.3&&Date.now()-t0<900)go(cur+(dx<0?1:-1))}},{{passive:true}});
document.querySelectorAll('.s img').forEach(im=>im.addEventListener('click',e=>{{const x=e.clientX/innerWidth;go(cur+(x<.33?-1:1))}}));
window.DECK={{get count(){{return N}},get index(){{return cur}},go:(i)=>go(i),replay(){{}},audit(){{return[]}}}};
go((parseInt(location.hash.slice(1))||parseInt(q.get('slide'))||1)-1);}})();
</script></body></html>"""


def convert(src: Path, out: Path, dpi: int = 160, notes: bool = True, quality: int = 86) -> dict:
    t0 = time.time()
    info = inspect_deck(src)
    r = office.render_slides(src, dpi=dpi)
    parts = []
    for i, p in enumerate(r["images"]):
        im = Image.open(p).convert("RGB")
        buf = io.BytesIO()
        im.save(buf, "WEBP", quality=quality, method=4)
        uri = "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode()
        sd = info["slides"][i] if i < len(info["slides"]) else {}
        title = sd.get("title") or f"Слайд {i + 1}"
        texts = [sh.get("text", "") for sh in sd.get("shapes", []) if sh.get("text")]
        body = (sd.get("notes") or "").strip() if notes else ""
        if not body:  # no notes → slide text for comfortable reading on a phone
            body = "\n".join(t for t in texts if t.strip() and t.strip() != title)[:1500]
        parts.append(f'<section class="s"><img src="{uri}" alt="{html.escape(title)}" width="{im.width}" height="{im.height}">'
                     f'<div class="n"><b>{i + 1}. {html.escape(title)}</b>{html.escape(body)}</div></section>')
    doc = PAGE.format(title=html.escape(info.get("core", {}).get("title") or src.stem), slides="".join(parts))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(doc, encoding="utf-8")
    return {"out": str(out), "slides": len(parts), "kb": round(out.stat().st_size / 1024, 1),
            "ms": round((time.time() - t0) * 1000), "rendered": len(r.get("rendered", []))}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("deck")
    ap.add_argument("-o", "--out")
    ap.add_argument("--dpi", type=int, default=160, help="160 ≈ 2130 px по ширине слайда (чётко на телефоне)")
    ap.add_argument("--quality", type=int, default=86)
    ap.add_argument("--no-notes", action="store_true", help="не показывать заметки докладчика под слайдом")
    a = ap.parse_args(argv)
    src = Path(a.deck)
    out = Path(a.out) if a.out else ROOT / "presentations" / (src.stem + ".html")
    res = convert(src, out, a.dpi, not a.no_notes, a.quality)
    print(res)
    return 0


if __name__ == "__main__":
    sys.exit(main())
