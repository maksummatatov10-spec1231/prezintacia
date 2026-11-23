"""Headless Chromium (serverless build from npm) driven by Playwright.

    with Chrome() as c:
        c.shot("page.html", "out.png", width=1600, height=900)
        c.deck_shots("deck.html", "shots/", viewports={"desktop": (1600, 900), "phone": (390, 844)})
        c.frames("deck.html", slide=3, times=[0, 300, 800, 2000], out="film.png")

A warm instance answers in ~100-200 ms; `tools/snapd.py` keeps one alive between commands.
"""
from __future__ import annotations

import time
from pathlib import Path
from urllib.parse import urlencode

from .env import CHROMIUM, CHROMIUM_ARGS, chromium_env

VIEWPORTS = {
    "desktop": (1600, 900),
    "laptop": (1366, 768),
    "fullhd": (1920, 1080),
    "tablet": (1024, 768),
    "phone": (390, 844),            # iPhone 12-15 portrait
    "phone-landscape": (844, 390),
    "android": (412, 915),          # Pixel 7 portrait
}


def to_url(target: str | Path) -> str:
    s = str(target)
    if s.startswith(("http://", "https://", "file://", "data:", "about:")):
        return s
    p = Path(s).resolve()
    if not p.exists():
        raise FileNotFoundError(f"файл не найден: {s}")
    return p.as_uri()


class Chrome:
    def __init__(self, headless: bool = True):
        self.headless = headless
        self._pw = None
        self.browser = None

    # -- lifecycle
    def __enter__(self):
        return self.start()

    def __exit__(self, *exc):
        self.close()

    def start(self):
        from playwright.sync_api import sync_playwright
        if not CHROMIUM.exists():
            raise RuntimeError("Chromium is not installed — run ./setup_env.sh")
        self._pw = sync_playwright().start()
        self.browser = self._pw.chromium.launch(executable_path=str(CHROMIUM), args=CHROMIUM_ARGS,
                                                headless=self.headless, env=chromium_env(), timeout=60000)
        return self

    def close(self):
        try:
            if self.browser:
                self.browser.close()
        finally:
            if self._pw:
                self._pw.stop()
            self.browser = self._pw = None

    def page(self, width=1600, height=900, scale: float = 1, mobile: bool | None = None):
        if mobile is None:
            mobile = width < 700
        ctx = self.browser.new_context(viewport={"width": width, "height": height}, device_scale_factor=scale,
                                       is_mobile=mobile, has_touch=mobile, reduced_motion="no-preference",
                                       ignore_https_errors=True)  # sandbox/corporate TLS proxies
        pg = ctx.new_page()
        pg._pptkit_ctx = ctx
        return pg

    @staticmethod
    def capture(pg, out, quality: int | None = None) -> Path:
        """Fast viewport capture through CDP (skips Playwright's extra waits). Format from the extension:
        .png (lossless) | .jpg/.jpeg (≈5× faster for photo-heavy slides) | .webp."""
        import base64
        out = Path(out)
        out.parent.mkdir(parents=True, exist_ok=True)
        fmt = {".jpg": "jpeg", ".jpeg": "jpeg", ".webp": "webp"}.get(out.suffix.lower(), "png")
        cdp = getattr(pg, "_pptkit_cdp", None)
        if cdp is None:
            cdp = pg._pptkit_cdp = pg.context.new_cdp_session(pg)
        args = {"format": fmt, "captureBeyondViewport": False}
        if fmt != "png":
            args["quality"] = quality or 92
        else:
            args["optimizeForSpeed"] = True
        out.write_bytes(base64.b64decode(cdp.send("Page.captureScreenshot", args)["data"]))
        return out

    @staticmethod
    def _close(pg):
        try:
            pg._pptkit_ctx.close()
        except Exception:
            pass

    # -- single screenshot of anything
    def shot(self, target, out, width=1600, height=900, scale: float = 1, full_page=False, selector=None,
             wait_ms: int = 0, html: str | None = None, mobile: bool | None = None, wait_until="load") -> dict:
        t = time.time()
        pg = self.page(width, height, scale, mobile)
        try:
            if html is not None:
                pg.set_content(html, wait_until=wait_until)
            else:
                pg.goto(to_url(target), wait_until=wait_until, timeout=60000)
            try:
                pg.evaluate("document.fonts && document.fonts.ready")
            except Exception:
                pass
            if wait_ms:
                pg.wait_for_timeout(wait_ms)
            Path(out).parent.mkdir(parents=True, exist_ok=True)
            if selector:
                pg.locator(selector).first.screenshot(path=str(out))
            else:
                pg.screenshot(path=str(out), full_page=full_page)
            errors = []
        finally:
            self._close(pg)
        return {"out": str(out), "ms": int((time.time() - t) * 1000), "errors": errors}

    # -- HTML decks built by pptkit (window.DECK API)
    def deck_shots(self, html, out_dir, viewports: dict | None = None, slides=None, static=True,
                   scale: float = 1, settle_ms: int = 0, fmt: str = "jpg") -> dict:
        """Screenshot every slide of a pptkit HTML deck for each viewport.
        static=True finishes all entrance animations instantly (final state)."""
        out_dir = Path(out_dir)
        viewports = viewports or {"desktop": VIEWPORTS["desktop"], "phone": VIEWPORTS["phone"]}
        res = {"viewports": {}, "console": [], "page_errors": []}
        base = to_url(html)
        for name, (w, h) in viewports.items():
            t = time.time()
            pg = self.page(w, h, scale)
            pg.on("console", lambda m: res["console"].append(f"[{m.type}] {m.text}") if m.type in ("error", "warning") else None)
            pg.on("pageerror", lambda e: res["page_errors"].append(str(e)))
            q = urlencode({"static": "1"}) if static else ""
            pg.goto(base + ("?" + q if q else ""), wait_until="load")
            pg.evaluate("document.fonts.ready")
            n = pg.evaluate("window.DECK ? window.DECK.count : 0")
            idx = slides or list(range(1, n + 1))
            files = []
            (out_dir / name).mkdir(parents=True, exist_ok=True)
            overflow = []
            for i in idx:
                pg.evaluate(f"window.DECK.go({i - 1}, {{instant: true}})")
                if settle_ms:
                    pg.wait_for_timeout(settle_ms)
                f = out_dir / name / f"slide-{i:02d}.{fmt}"
                self.capture(pg, f)
                files.append(f)
                # layout audit of THIS slide (overflow, off-screen, clipped chips …)
                overflow += [f"слайд {i}: {a}" for a in
                             pg.evaluate("window.DECK && window.DECK.audit ? window.DECK.audit() : []")]
            self._close(pg)
            res["viewports"][name] = {"files": files, "count": n, "ms": int((time.time() - t) * 1000),
                                      "audit": overflow, "size": (w, h)}
        return res

    def frames(self, html, slide: int, times=(0, 250, 600, 1200, 2500), out=None, viewport=(1600, 900)) -> list:
        """Capture an animation at several moments (ms after the slide is shown) -> filmstrip."""
        from .imaging import filmstrip
        pg = self.page(*viewport)
        pg.goto(to_url(html), wait_until="load")
        pg.evaluate("document.fonts.ready")
        pg.evaluate(f"window.DECK.go({slide - 1}, {{instant: true}})")
        pg.wait_for_timeout(100)
        pg.evaluate("window.DECK.replay()")
        start = time.time()
        shots = []
        tmpdir = Path(out).parent if out else Path(".")
        for k, ms in enumerate(times):
            wait = ms / 1000 - (time.time() - start)
            if wait > 0:
                time.sleep(wait)
            f = tmpdir / f"_frame_{slide}_{k}.png"
            pg.screenshot(path=str(f))
            shots.append(f)
        self._close(pg)
        if out:
            filmstrip(shots, out, height=300)
            for f in shots:
                f.unlink(missing_ok=True)
            return [Path(out)]
        return shots

    def pdf(self, target, out, width="1600px", height="900px") -> dict:
        pg = self.page(1600, 900)
        pg.goto(to_url(target) + "?static=1&print=1", wait_until="load")
        pg.evaluate("document.fonts.ready")
        pg.pdf(path=str(out), width=width, height=height, print_background=True)
        self._close(pg)
        return {"out": str(out)}
