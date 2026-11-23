"""Shared bootstrap for tools/*.py: makes `import pptkit` work from any cwd and re-executes the
script inside the project venv when it is started with a system python."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_venv_py = ROOT / ".venv" / "bin" / "python"
if _venv_py.exists() and Path(sys.prefix).resolve() != (ROOT / ".venv").resolve() and not os.environ.get("PPTKIT_NO_REEXEC"):
    os.environ["PPTKIT_NO_REEXEC"] = "1"
    os.execv(str(_venv_py), [str(_venv_py), *sys.argv])


def parse_pages(spec: str | None) -> list[int] | None:
    """'1,3,5-7' -> [1, 3, 5, 6, 7]"""
    if not spec:
        return None
    out: list[int] = []
    for part in str(spec).split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-")
            out += list(range(int(a), int(b) + 1))
        elif part:
            out.append(int(part))
    return out


def parse_viewport(v: str):
    from pptkit.browser import VIEWPORTS
    if v in VIEWPORTS:
        return v, VIEWPORTS[v]
    w, h = v.lower().split("x")
    return v, (int(w), int(h))
