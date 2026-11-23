"""Run folders: every tool invocation writes   checks/<YYYYmmdd-HHMMSS>-<tool>-<target>/
with log.txt, summary.md, result.json and the produced images; `checks/latest/` mirrors the
newest run (so it is always at the same path and can be committed / opened from a phone).
"""
from __future__ import annotations

import datetime as _dt
import json
import shutil
import sys
import time
from contextlib import contextmanager
from pathlib import Path

from .env import CHECKS_DIR


def _slug(s: str, n: int = 40) -> str:
    keep = "".join(c if c.isalnum() or c in "-_." else "-" for c in s)
    return "-".join(filter(None, keep.split("-")))[:n] or "run"


class Run:
    def __init__(self, tool: str, target: str | None = None, out: str | Path | None = None, quiet: bool = False,
                 latest: bool = True):
        stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        name = f"{stamp}-{tool}" + (f"-{_slug(Path(str(target)).stem)}" if target else "")
        self.dir = Path(out) if out else CHECKS_DIR / "runs" / name
        if self.dir.exists() and out:
            shutil.rmtree(self.dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.tool, self.target, self.quiet, self.latest = tool, target, quiet, latest
        self.t0 = time.perf_counter()
        self.steps: list[dict] = []
        self.data: dict = {"tool": tool, "target": str(target) if target else None,
                           "started": _dt.datetime.now().isoformat(timespec="seconds")}
        self._log = open(self.dir / "log.txt", "w", encoding="utf-8")
        self.md: list[str] = []
        self.log(f"run {name}  →  {self.dir}")

    # ------------------------------------------------------------------ logging
    def log(self, msg: str):
        ms = (time.perf_counter() - self.t0) * 1000
        line = f"[{ms:9.1f} ms] {msg}"
        self._log.write(line + "\n")
        self._log.flush()
        if not self.quiet:
            print(line, file=sys.stderr)

    @contextmanager
    def step(self, name: str):
        t = time.perf_counter()
        self.log(f"▶ {name}")
        rec = {"step": name}
        try:
            yield rec
            rec["ok"] = True
        except Exception as e:
            rec["ok"] = False
            rec["error"] = f"{type(e).__name__}: {e}"
            self.log(f"✖ {name}: {rec['error']}")
            raise
        finally:
            rec["ms"] = round((time.perf_counter() - t) * 1000, 1)
            self.steps.append(rec)
            self.log(f"■ {name} — {rec['ms']} ms")

    # ------------------------------------------------------------------ outputs
    def path(self, rel: str) -> Path:
        p = self.dir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def write(self, rel: str, text: str) -> Path:
        p = self.path(rel)
        p.write_text(text, encoding="utf-8")
        return p

    def write_json(self, rel: str, data) -> Path:
        p = self.path(rel)
        p.write_text(json.dumps(data, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
        return p

    def add_md(self, text: str):
        self.md.append(text)

    def finish(self, ok: bool = True) -> Path:
        total = round((time.perf_counter() - self.t0) * 1000, 1)
        self.data.update({"ok": ok, "total_ms": total, "steps": self.steps,
                          "files": sorted(str(p.relative_to(self.dir)) for p in self.dir.rglob("*") if p.is_file())})
        head = [f"# {self.tool}: {self.target or ''}\n",
                f"- Папка результата: `{self.dir}`",
                f"- Время: **{total} ms** · шаги: " + ", ".join(f"{s['step']} {s['ms']} ms" for s in self.steps), ""]
        self.write("summary.md", "\n".join(head + self.md) + "\n")
        self.write_json("result.json", self.data)
        self.log(f"готово за {total} ms → {self.dir / 'summary.md'}")
        self._log.close()
        if self.latest and CHECKS_DIR in self.dir.parents:
            latest = CHECKS_DIR / "latest"
            if latest.exists():
                shutil.rmtree(latest)
            shutil.copytree(self.dir, latest)
        return self.dir
