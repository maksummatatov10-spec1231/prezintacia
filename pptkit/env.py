"""Environment: paths, binaries and process env for the toolkit.

Everything heavy lives in `.cache/` (git-ignored) and is re-created by `./setup_env.sh`.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / ".cache"
CHROMIUM_DIR = CACHE / "chromium"
CHROMIUM = CHROMIUM_DIR / "chromium"
FONTS_DIR = CACHE / "fonts"            # all toolkit fonts (TTF), used by Chromium + LibreOffice
RENDER_CACHE = CACHE / "renders"       # sha256-keyed PPTX render cache (instant re-checks)
NODE_MODULES = ROOT / "node_modules"
CHECKS_DIR = ROOT / "checks"
JS_DIR = Path(__file__).resolve().parent / "js"

# Flags that make the serverless Chromium build happy inside a sandbox
CHROMIUM_ARGS = [
    "--no-sandbox", "--no-zygote", "--disable-setuid-sandbox", "--disable-dev-shm-usage",
    "--font-render-hinting=none", "--use-gl=angle", "--use-angle=swiftshader",
    "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist", "--in-process-gpu",
    "--no-first-run", "--hide-scrollbars", "--mute-audio", "--disable-background-timer-throttling",
    "--disable-renderer-backgrounding", "--allow-file-access-from-files",
]


def chromium_env() -> dict:
    env = dict(os.environ)
    libs = [str(CHROMIUM_DIR / "al2023" / "lib"), str(CHROMIUM_DIR)]
    old = env.get("LD_LIBRARY_PATH")
    env["LD_LIBRARY_PATH"] = ":".join(libs + ([old] if old else []))
    env.setdefault("HOME", str(Path.home()))
    return env


def node_bin() -> str:
    return shutil.which("node") or "node"


def check_env() -> dict:
    """Return a dict describing which parts of the environment are ready."""
    status = {
        "chromium": CHROMIUM.exists(),
        "libreoffice_wasm": (NODE_MODULES / "@deepseek-ai" / "libreoffice-kit-wasm").exists(),
        "fonts": FONTS_DIR.exists() and any(FONTS_DIR.rglob("*.ttf")),
        "node": shutil.which("node") is not None,
    }
    status["ok"] = all(status.values())
    return status


# extra font folders (e.g. a deck's own fonts/ dir) — searched by fonts.find_font and LibreOffice
EXTRA_FONT_DIRS: list[Path] = [Path(p) for p in os.environ.get("PPTKIT_FONT_DIRS", "").split(":") if p]


def font_dirs() -> list[str]:
    dirs = [str(d) for d in EXTRA_FONT_DIRS if Path(d).exists()]
    dirs += [str(FONTS_DIR)] if FONTS_DIR.exists() else []
    for d in ("/usr/share/fonts", str(Path.home() / ".local/share/fonts")):
        if Path(d).exists():
            dirs.append(d)
    return dirs
