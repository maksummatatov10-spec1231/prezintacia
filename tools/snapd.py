#!/usr/bin/env python3
"""snapd — warm Chromium daemon: screenshots in ~50–200 ms instead of ~1 s (no browser start per call).

  python tools/snapd.py start                       # start in background (auto-started by `shot` anyway)
  python tools/snapd.py shot page.html -o out.png   # any file / URL / SVG / HTML deck
  python tools/snapd.py shot deck.html --slide 7 --viewport phone -o s7.png     # one slide of a pptkit HTML deck
  python tools/snapd.py shot https://example.com --viewport 1280x800 --full
  python tools/snapd.py html "<h1>Привет</h1>" -o h.png --viewport 800x200
  python tools/snapd.py status | stop

Format follows the extension: .png (lossless) | .jpg (fastest) | .webp.  Prints JSON {out, ms}.
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import _boot  # noqa: F401
from _boot import parse_viewport

from pptkit.env import CACHE

STATE = CACHE / "snapd.json"
DEFAULT_PORT = 8765


# ----------------------------------------------------------------------------- server
def serve(port: int):
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from pptkit.browser import Chrome, to_url

    chrome = Chrome().start()
    pages: dict[tuple, object] = {}

    def page(w, h, scale):
        key = (w, h, scale)
        if key not in pages:
            pages[key] = chrome.page(w, h, scale)
        return pages[key]

    def handle(req: dict) -> dict:
        t0 = time.perf_counter()
        w, h = req.get("w", 1600), req.get("h", 900)
        pg = page(w, h, req.get("scale", 1))
        out = Path(req["out"])
        if req.get("html") is not None:
            pg.set_content(req["html"], wait_until="load")
        else:
            url = to_url(req["target"])
            slide = req.get("slide")
            if slide:
                base = url.split("#")[0]
                if pg.url.split("#")[0].split("?")[0] != base or "static=1" not in pg.url:
                    pg.goto(base + "?static=1", wait_until="load")
                    pg.evaluate("document.fonts.ready")
                pg.evaluate(f"window.DECK.go({int(slide) - 1}, {{instant: true}})")
            else:
                pg.goto(url, wait_until=req.get("wait_until", "load"), timeout=60000)
        try:
            pg.evaluate("document.fonts && document.fonts.ready")
        except Exception:  # noqa: BLE001
            pass
        if req.get("wait_ms"):
            pg.wait_for_timeout(req["wait_ms"])
        out.parent.mkdir(parents=True, exist_ok=True)
        if req.get("selector"):
            pg.locator(req["selector"]).first.screenshot(path=str(out))
        elif req.get("full"):
            pg.screenshot(path=str(out), full_page=True)
        else:
            Chrome.capture(pg, out)
        return {"out": str(out), "ms": round((time.perf_counter() - t0) * 1000, 1)}

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):  # quiet
            pass

        def do_GET(self):
            self._send(200, {"ok": True, "pid": os.getpid(), "pages": len(pages)})

        def do_POST(self):
            req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            if req.get("cmd") == "stop":
                self._send(200, {"stopped": True})
                raise KeyboardInterrupt
            try:
                self._send(200, handle(req))
            except Exception as e:  # noqa: BLE001
                self._send(500, {"error": str(e).splitlines()[0]})

        def _send(self, code, data):
            body = json.dumps(data, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    srv = HTTPServer(("127.0.0.1", port), H)  # single thread: Playwright sync objects stay on this thread
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps({"port": port, "pid": os.getpid()}))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        chrome.close()
        STATE.unlink(missing_ok=True)


# ----------------------------------------------------------------------------- client
def _state():
    try:
        return json.loads(STATE.read_text())
    except Exception:  # noqa: BLE001
        return None


def _alive(st) -> bool:
    if not st:
        return False
    try:
        with socket.create_connection(("127.0.0.1", st["port"]), timeout=0.3):
            return True
    except OSError:
        return False


def start(port=DEFAULT_PORT, wait=True):
    st = _state()
    if _alive(st):
        return st
    log = open(CACHE / "snapd.log", "a")
    subprocess.Popen([sys.executable, __file__, "_serve", "--port", str(port)], stdout=log, stderr=log,
                     stdin=subprocess.DEVNULL, start_new_session=True)
    t = time.time()
    while wait and time.time() - t < 30:
        st = _state()
        if _alive(st):
            return st
        time.sleep(0.05)
    return _state()


def call(payload: dict) -> dict:
    st = start()
    req = urllib.request.Request(f"http://127.0.0.1:{st['port']}/", data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return json.loads(e.read())


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["start", "stop", "status", "shot", "html", "_serve"])
    ap.add_argument("target", nargs="?")
    ap.add_argument("-o", "--out")
    ap.add_argument("--viewport", default="desktop")
    ap.add_argument("--slide", type=int)
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--selector")
    ap.add_argument("--wait", type=int, default=0)
    ap.add_argument("--scale", type=float, default=1)
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    a = ap.parse_args(argv)
    if a.cmd == "_serve":
        serve(a.port)
        return 0
    if a.cmd == "start":
        t = time.time()
        st = start(a.port)
        print(json.dumps({**(st or {}), "ready_ms": round((time.time() - t) * 1000)}))
        return 0
    if a.cmd == "status":
        st = _state()
        print(json.dumps({"running": _alive(st), **(st or {})}))
        return 0
    if a.cmd == "stop":
        st = _state()
        if _alive(st):
            try:
                call({"cmd": "stop"})
            except Exception:  # noqa: BLE001
                pass
        print(json.dumps({"stopped": True}))
        return 0
    _, (w, h) = parse_viewport(a.viewport)
    out = a.out or str(CACHE.parent / "checks" / "latest" / f"snap.{'png'}")
    payload = {"w": w, "h": h, "scale": a.scale, "out": str(Path(out).resolve()), "full": a.full,
               "selector": a.selector, "wait_ms": a.wait, "slide": a.slide}
    if a.cmd == "html":
        payload["html"] = a.target
    else:
        t = a.target
        payload["target"] = t if str(t).startswith(("http://", "https://", "file:", "data:")) else str(Path(t).resolve())
    t0 = time.perf_counter()
    res = call(payload)
    res["total_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    print(json.dumps(res, ensure_ascii=False))
    return 0 if "error" not in res else 1


if __name__ == "__main__":
    sys.exit(main())
