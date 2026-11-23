"""Length units. Internally python-pptx works in EMU (English Metric Units).

1 in = 914400 EMU = 2.54 cm = 72 pt = 96 px(CSS)
"""
from __future__ import annotations

import re

EMU_PER_IN = 914400
EMU_PER_CM = 360000
EMU_PER_MM = 36000
EMU_PER_PT = 12700
EMU_PER_PX = 9525  # 96 dpi

_UNIT = {"in": EMU_PER_IN, "inch": EMU_PER_IN, '"': EMU_PER_IN, "cm": EMU_PER_CM, "mm": EMU_PER_MM,
         "pt": EMU_PER_PT, "px": EMU_PER_PX, "emu": 1}
_RX = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*(in|inch|cm|mm|pt|px|emu|%|\")?\s*$", re.I)


def to_emu(value, ref_emu: int | None = None, default_unit: str = "in") -> int:
    """Parse '2.5in', '3cm', '40%', '120px', 914400, 1.5 -> EMU.

    Percentages are relative to `ref_emu` (e.g. slide width for x/width, slide height for y/height).
    Bare numbers use `default_unit` unless they are big ints (>= 10000 -> already EMU).
    """
    if isinstance(value, (int,)) and abs(value) >= 10000:
        return int(value)
    if isinstance(value, (int, float)):
        return int(round(value * _UNIT[default_unit]))
    m = _RX.match(str(value))
    if not m:
        raise ValueError(f"Cannot parse length: {value!r} (use e.g. 2.5in, 3cm, 120px, 24pt, 40%)")
    num, unit = float(m.group(1)), (m.group(2) or default_unit).lower()
    if unit == "%":
        if ref_emu is None:
            raise ValueError(f"Percentage {value!r} needs a reference length")
        return int(round(ref_emu * num / 100.0))
    return int(round(num * _UNIT[unit]))


def emu_to(emu: int, unit: str = "cm", nd: int = 2) -> float:
    return round(emu / _UNIT[unit], nd)


def fmt_emu(emu: int) -> str:
    return f"{emu_to(emu, 'cm')}cm/{emu_to(emu, 'in')}in/{int(round(emu / EMU_PER_PX))}px"
