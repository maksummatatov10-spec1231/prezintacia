"""Vector maps from Natural Earth (public domain) → SVG (for HTML) and PNG (for PPTX via Chromium).

    m = MapSVG(bbox=(19.2, 34.5, 30.2, 41.6), width=1200)
    m.land(); m.city("Афины", 23.73, 37.98); m.label("Эгейское море", 25, 38.9, cls="sea")
    svg = m.svg()
"""
from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path

from .env import CACHE

NE = CACHE / "src" / "ne" / "geojson"


@lru_cache(maxsize=8)
def _features(name: str):
    return json.loads((NE / f"{name}.geojson").read_text())["features"]


class MapSVG:
    def __init__(self, bbox, width=1200, pad=0):
        self.lon0, self.lat0, self.lon1, self.lat1 = bbox
        self.latc = (self.lat0 + self.lat1) / 2
        self.s = width / ((self.lon1 - self.lon0) * math.cos(math.radians(self.latc)))
        self.W = width
        self.H = int(round(self.s * (self.lat1 - self.lat0)))
        self.layers: list[str] = []
        self.defs: list[str] = []
        self.css: list[str] = []

    def xy(self, lon, lat):
        return ((lon - self.lon0) * self.s * math.cos(math.radians(self.latc)), (self.lat1 - lat) * self.s)

    # ------------------------------------------------------------------ geometry
    def _ring_path(self, ring, margin=30, min_step=0.9):
        pts = []
        lastp = None
        for lon, lat in ring:
            x, y = self.xy(lon, lat)
            x = min(max(x, -margin), self.W + margin)
            y = min(max(y, -margin), self.H + margin)
            if lastp is None or abs(x - lastp[0]) + abs(y - lastp[1]) >= min_step:
                pts.append((x, y))
                lastp = (x, y)
        if len(pts) < 3:
            return ""
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        if (max(xs) - min(xs)) * (max(ys) - min(ys)) < 1.5:
            return ""
        if max(xs) < 0 or min(xs) > self.W or max(ys) < 0 or min(ys) > self.H:
            return ""
        d = [f"M{pts[0][0]:.1f} {pts[0][1]:.1f}"]
        px, py = pts[0]
        for x, y in pts[1:]:
            d.append(f"l{x - px:.1f} {y - py:.1f}")
            px, py = round(x, 1), round(y, 1)
            px, py = x, y
        return "".join(d) + "z"

    def paths(self, dataset="ne_10m_land", min_step=0.9, filt=None) -> str:
        out = []
        for f in _features(dataset):
            if filt and not filt(f["properties"]):
                continue
            g = f["geometry"]
            if not g:
                continue
            polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
            for poly in polys:
                ring = poly[0]
                lons = [p[0] for p in ring]
                lats = [p[1] for p in ring]
                if max(lons) < self.lon0 - 1 or min(lons) > self.lon1 + 1 or max(lats) < self.lat0 - 1 or min(lats) > self.lat1 + 1:
                    continue
                for r in poly:
                    p = self._ring_path(r, min_step=min_step)
                    if p:
                        out.append(p)
        return "".join(out)

    # ------------------------------------------------------------------ layers
    def add(self, svg: str):
        self.layers.append(svg)

    def land(self, datasets=("ne_10m_land", "ne_10m_minor_islands"), cls="land", halo=True, min_step=0.9):
        """Adds the land layer (path stored ONCE in <defs>, drawn via <use>). Returns the path id."""
        d = "".join(self.paths(ds, min_step=min_step) for ds in datasets)
        pid = f"{cls}{len(self.defs)}"
        self.defs.append(f'<path id="{pid}" d="{d}" fill-rule="evenodd"/>')
        if halo:
            self.layers.append(f'<use href="#{pid}" class="{cls}-halo"/>')
        self.layers.append(f'<use href="#{pid}" class="{cls}"/>')
        return pid

    def city(self, name, lon, lat, dx=10, dy=5, anchor="start", cls="city", r=6):
        x, y = self.xy(lon, lat)
        self.layers.append(f'<g class="{cls}"><circle cx="{x:.1f}" cy="{y:.1f}" r="{r}"/>'
                           f'<text x="{x + dx:.1f}" y="{y + dy:.1f}" text-anchor="{anchor}">{name}</text></g>')
        return x, y

    def label(self, text, lon, lat, cls="sea", anchor="middle", rotate=0):
        x, y = self.xy(lon, lat)
        tr = f' transform="rotate({rotate} {x:.1f} {y:.1f})"' if rotate else ""
        lines = text.split("\n")
        if len(lines) == 1:
            self.layers.append(f'<text class="{cls}" x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}"{tr}>{text}</text>')
        else:
            sp = "".join(f'<tspan x="{x:.1f}" dy="{0 if i == 0 else 1.15}em">{t}</tspan>' for i, t in enumerate(lines))
            self.layers.append(f'<text class="{cls}" x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}"{tr}>{sp}</text>')

    def arc(self, a, b, bend=0.2, cls="route"):
        (x1, y1), (x2, y2) = self.xy(*a), self.xy(*b)
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        dx, dy = x2 - x1, y2 - y1
        cx, cy = mx - dy * bend, my + dx * bend
        self.layers.append(f'<path class="{cls}" d="M{x1:.1f} {y1:.1f}Q{cx:.1f} {cy:.1f} {x2:.1f} {y2:.1f}"/>')

    def svg(self, css: str = "", bg: str | None = None, cls: str = "map", font_face: str = "") -> str:
        style = f"<style>{font_face}{css}{''.join(self.css)}</style>" if (css or self.css or font_face) else ""
        defs = f"<defs>{''.join(self.defs)}</defs>" if self.defs else ""
        bgr = f'<rect class="sea-bg" width="{self.W}" height="{self.H}"/>' if bg is None else bg
        return (f'<svg xmlns="http://www.w3.org/2000/svg" class="{cls}" viewBox="0 0 {self.W} {self.H}" '
                f'preserveAspectRatio="xMidYMid slice">{style}{defs}{bgr}{"".join(self.layers)}</svg>')
