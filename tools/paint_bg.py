"""paint_bg.py — generate a slowly drifting, soft "paint blobs" backdrop (video for PowerPoint, poster for HTML).

The look: a warm cream canvas with 4 subdued paint colours (terracotta, mustard, sage, dusty rose) that
drift and breathe like blurred watercolour.  Everything is low-saturation and low-alpha, so text stays readable.

The video is a seamless loop: every blob moves along a Lissajous path with an integer number of cycles per
loop, so frame 0 == frame N.  In PowerPoint each slide plays the clip automatically and loops, so the
background simply keeps flowing while the presenter talks.

    python tools/paint_bg.py out/preview.mp4 --seconds 48 --fps 25
    python tools/paint_bg.py out/preview.mp4 --still out/poster.png --size 1600x900

Report (frames, timings, size, fps) is written next to the output: <name>.log.md and checks/latest.
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _boot  # noqa: F401  (re-execs inside .venv)

from PIL import Image

# cream canvas + four paints (RGB) — the palette of the doll's skirt
BASE = (255, 245, 227)
PAINTS = [(228, 84, 66), (243, 170, 45), (126, 168, 92), (238, 148, 140)]

# blob = (colour index, centre x/y (0..1), orbit amplitude x/y, cycles x/y, phase, radius x/y, angle, amp, pulses)
BLOBS = [
    # ci, cx, cy, ax, ay, kx, ky, phase, rx, ry, angle, amp, pulses — rounder, watercolour-like patches
    (0, 0.12, 0.18, 0.10, 0.08, 1, 2, 0.7, 0.30, 0.28, -18, 0.58, 1),
    (1, 0.78, 0.14, 0.09, 0.10, 2, 1, 2.1, 0.26, 0.30, 24, 0.52, 2),
    (2, 0.88, 0.76, 0.09, 0.09, 1, 1, 4.0, 0.30, 0.27, -32, 0.46, 1),
    (3, 0.20, 0.86, 0.11, 0.08, 2, 3, 5.2, 0.28, 0.25, 12, 0.50, 2),
    (1, 0.50, 0.50, 0.14, 0.10, 1, 2, 3.3, 0.20, 0.19, 40, 0.26, 3),
    (0, 0.38, 0.06, 0.12, 0.06, 2, 2, 1.1, 0.18, 0.17, -8, 0.26, 2),
    (3, 0.62, 0.94, 0.10, 0.06, 1, 3, 0.3, 0.22, 0.16, 30, 0.30, 2),
]


def render(t: float, w: int, h: int, intensity: float = 1.0, falloff: float = 1.35) -> np.ndarray:
    """One frame at phase t∈[0,1). Returns uint8 HxWx3."""
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    x = (xs + 0.5) / w
    y = (ys + 0.5) / h
    out = np.empty((h, w, 3), np.float32)
    out[:] = BASE
    tau = 2 * math.pi
    for ci, cx, cy, ax, ay, kx, ky, ph, rx, ry, ang, amp, pulses in BLOBS:
        # torus-wrapped centre → the pattern is seamless when shifted by one canvas in x or y
        px = (cx + ax * math.sin(tau * (kx * t) + ph)) % 1.0
        py = (cy + ay * math.cos(tau * (ky * t) + ph * 1.7)) % 1.0
        # work in "height units" so a blob with rx≈ry looks round on a 16:9 slide
        ar = w / h
        dx = (((x - px + 0.5) % 1.0) - 0.5) * ar
        dy = ((y - py + 0.5) % 1.0) - 0.5
        th = math.radians(ang + 18 * math.sin(tau * t + ph))
        ca, sa = math.cos(th), math.sin(th)
        xr = dx * ca + dy * sa
        yr = -dx * sa + dy * ca
        pulse = 1 + 0.14 * math.sin(tau * pulses * t + ph)
        d = (xr / (rx * pulse)) ** 2 + (yr / (ry * pulse)) ** 2
        a = amp * np.exp(-falloff * d) * intensity
        col = np.array(PAINTS[ci], np.float32)
        out *= (1 - a[..., None])
        out += a[..., None] * col
    # very soft light from the top-left, keeps the canvas from looking flat
    sheen = (0.5 - 0.28 * x - 0.18 * y)[..., None]
    out += sheen * 26
    return np.clip(out, 0, 255)


def _ffmpeg() -> str:
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def make_video(dst: Path, seconds: float, fps: int, size: tuple[int, int], crf: int, sim: int, poster: Path | None,
               falloff: float = 1.35, intensity: float = 1.0):
    dst.parent.mkdir(parents=True, exist_ok=True)
    w, h = size
    sw, sh = sim, round(sim * h / w)
    n = int(round(seconds * fps))
    cmd = [_ffmpeg(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{sw}x{sh}",
           "-r", str(fps), "-i", "-",
           "-vf", f"scale={w}:{h}:flags=bicubic,gblur=sigma=1.2,format=yuv420p",
           "-c:v", "libx264", "-profile:v", "high", "-crf", str(crf), "-g", str(fps * 2), "-preset", "medium",
           "-movflags", "+faststart", str(dst)]
    t0 = time.time()
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    rng = np.random.default_rng(7)
    for i in range(n):
        fr = render(i / n, sw, sh, intensity=intensity, falloff=falloff)
        fr += rng.normal(0, 1.1, fr.shape)  # dither: kills the banding in smooth gradients
        proc.stdin.write(np.clip(fr, 0, 255).astype(np.uint8).tobytes())
    proc.stdin.close()
    err = proc.stderr.read().decode()
    if proc.wait() != 0:
        raise RuntimeError(f"ffmpeg failed: {err[-800:]}")
    if poster:
        img = Image.fromarray(np.clip(render(0.0, w // 2, h // 2, falloff=falloff) + rng.normal(0, 1.0, (h // 2, w // 2, 3)), 0, 255)
                              .astype(np.uint8)).resize((w, h), Image.BICUBIC)
        poster.parent.mkdir(parents=True, exist_ok=True)
        img.save(poster, quality=92, optimize=True)
    return {"frames": n, "sim": (sw, sh), "render_s": round(time.time() - t0, 1),
            "mb": round(dst.stat().st_size / 1048576, 2)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dst", type=Path)
    ap.add_argument("--seconds", type=float, default=48)
    ap.add_argument("--fps", type=int, default=25)
    ap.add_argument("--size", default="1600x900")
    ap.add_argument("--crf", type=int, default=30)
    ap.add_argument("--sim", type=int, default=480, help="simulation width; the blobs are blurred, upscaling is free")
    ap.add_argument("--still", type=Path, help="also write a poster PNG/JPG")
    ap.add_argument("--frames", type=int, default=0, help="write N preview frames as a contact strip")
    ap.add_argument("--intensity", type=float, default=1.0, help="colour strength")
    ap.add_argument("--falloff", type=float, default=1.35, help="larger = crisper edges (less blur); ~2.1 is 'paint'")
    ap.add_argument("--quality", type=int, default=92)
    a = ap.parse_args()
    w, h = (int(v) for v in a.size.lower().split("x"))
    if a.seconds <= 0:  # still only
        rng = np.random.default_rng(7)
        img = Image.fromarray(np.clip(render(0.0, w, h, intensity=a.intensity, falloff=a.falloff) + rng.normal(0, 0.8, (h, w, 3)), 0, 255)
                              .astype(np.uint8))
        a.dst.parent.mkdir(parents=True, exist_ok=True)
        img.save(a.dst, quality=a.quality, optimize=True, subsampling=0)
        info = {"size": [w, h], "mb": round(a.dst.stat().st_size / 1048576, 2), "falloff": a.falloff}
        if a.still:
            img.save(a.still, quality=a.quality, optimize=True, subsampling=0)
        print(json.dumps(info, ensure_ascii=False))
        return 0
    info = make_video(a.dst, a.seconds, a.fps, (w, h), a.crf, a.sim, a.still, falloff=a.falloff, intensity=a.intensity)
    if a.frames:
        sheet = Image.new("RGB", (w // 2, (h // 2) * a.frames))
        for i in range(a.frames):
            fr = render(i / a.frames, w // 2, h // 2) + np.random.default_rng(i).normal(0, 1, (h // 2, w // 2, 3))
            sheet.paste(Image.fromarray(np.clip(fr, 0, 255).astype(np.uint8)), (0, (h // 2) * i))
        sheet.save(a.dst.with_suffix(".frames.jpg"), quality=88)
        info["frames_sheet"] = str(a.dst.with_suffix(".frames.jpg"))
    log = a.dst.with_suffix(".log.md")
    log.write_text("# paint_bg\n\n```json\n" + json.dumps(info, ensure_ascii=False, indent=2) + "\n```\n", encoding="utf-8")
    print(json.dumps(info, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
