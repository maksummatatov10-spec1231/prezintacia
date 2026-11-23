"""pptkit — fast, script-first toolkit for building, editing and checking presentations.

Modules
-------
env       paths / binaries (Chromium, LibreOffice-WASM, fonts)
units     length parsing & conversion (in, cm, mm, pt, px, emu, %)
imaging   image ops: cover/contain crop, focal zoom, optimize, contact sheets, diffs
browser   headless Chromium screenshots (HTML, URL, SVG, decks, animation filmstrips)
office    PPTX/DOCX/XLSX -> PNG/PDF via LibreOffice WASM (sha256 render cache)
inspect   deep PPTX analysis (shapes, geometry, text, fonts, images, notes, animations)
lint      QA rules (overflow, off-slide, overlaps, tiny fonts, contrast, low-res images...)
edit      editing API (move / resize / zoom / crop / replace / style / reorder / animate)
anim      PowerPoint transitions + entrance/emphasis animations (raw OOXML)
fonts     font install, variable->static instancing, EOT embedding into PPTX
report    run folders: screenshots + report.md + report.json + log.txt
"""
__version__ = "1.0.0"
