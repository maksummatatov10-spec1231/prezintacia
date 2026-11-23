#!/usr/bin/env python3
"""Extract the headless Chromium shipped in the npm package @sparticuz/chromium into .cache/chromium.

Works where apt / `playwright install` are blocked (only registry.npmjs.org is needed). Pure Python
(brotli + tarfile); the package's own extractor only works on AWS Lambda.
"""
from __future__ import annotations

import io
import shutil
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "node_modules" / "@sparticuz" / "chromium" / "bin"
DST = ROOT / ".cache" / "chromium"


def _untar_br(name: str, dest: Path):
    import brotli
    data = brotli.decompress((SRC / name).read_bytes())
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(data)) as tf:
        tf.extractall(dest)  # (no filter= : not supported by Python 3.11.2)


def main(force: bool = False) -> int:
    import brotli
    if not SRC.exists():
        print("✖ нет node_modules/@sparticuz/chromium — сначала npm install", file=sys.stderr)
        return 1
    exe = DST / "chromium"
    if exe.exists() and not force:
        print(f"✔ Chromium уже есть: {exe}")
        return 0
    DST.mkdir(parents=True, exist_ok=True)
    exe.write_bytes(brotli.decompress((SRC / "chromium.br").read_bytes()))
    exe.chmod(0o755)
    _untar_br("al2023.tar.br", DST / "al2023")
    _untar_br("swiftshader.tar.br", DST / "swiftshader")
    for f in (DST / "swiftshader").rglob("*"):
        if f.is_file():  # SwiftShader (software GPU) must sit next to the binary
            shutil.copy2(f, DST / f.name)
    _untar_br("fonts.tar.br", DST / "fonts")
    print(f"✔ Chromium распакован: {exe}")
    return 0


if __name__ == "__main__":
    sys.exit(main(force="--force" in sys.argv))
