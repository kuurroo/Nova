# nova/core/skills/units.py
from __future__ import annotations
import re
from typing import Optional, Tuple

NAME = "units"

# ---------- Canonical maps ----------
# Length (base: meter)
_LEN = {
    "m": 1.0, "meter": 1.0, "meters": 1.0,
    "km": 1000.0, "kilometer": 1000.0, "kilometers": 1000.0,
    "cm": 0.01, "centimeter": 0.01, "centimeters": 0.01,
    "mm": 0.001, "millimeter": 0.001, "millimeters": 0.001,
    "mi": 1609.344, "mile": 1609.344, "miles": 1609.344,
    "yd": 0.9144, "yard": 0.9144, "yards": 0.9144,
    "ft": 0.3048, "foot": 0.3048, "feet": 0.3048,
    "in": 0.0254, "inch": 0.0254, "inches": 0.0254,
}

# Mass (base: kilogram)
_MASS = {
    "kg": 1.0, "kilogram": 1.0, "kilograms": 1.0,
    "g": 1e-3, "gram": 1e-3, "grams": 1e-3,
    "lb": 0.45359237, "lbs": 0.45359237, "pound": 0.45359237, "pounds": 0.45359237,
    "oz": 0.028349523125, "ounce": 0.028349523125, "ounces": 0.028349523125,
}

# Volume (base: liter)
_VOL = {
    "l": 1.0, "liter": 1.0, "liters": 1.0,
    "ml": 1e-3, "milliliter": 1e-3, "milliliters": 1e-3,
    "gal": 3.785411784, "gallon": 3.785411784, "gallons": 3.785411784,  # US
    "cup": 0.2365882365, "cups": 0.2365882365,
    "floz": 0.0295735295625, "fl oz": 0.0295735295625, "fluid ounce": 0.0295735295625, "fluid ounces": 0.0295735295625,
}

# Time (base: second)
_TIME = {
    "s": 1.0, "sec": 1.0, "secs": 1.0, "second": 1.0, "seconds": 1.0,
    "m": 60.0, "min": 60.0, "mins": 60.0, "minute": 60.0, "minutes": 60.0,
    "h": 3600.0, "hr": 3600.0, "hrs": 3600.0, "hour": 3600.0, "hours": 3600.0,
    "day": 86400.0, "days": 86400.0,
}

# Data (base: byte) — supports SI and IEC
_DATA = {
    # SI
    "b": 1.0, "byte": 1.0, "bytes": 1.0,
    "kb": 1000.0, "kilobyte": 1000.0, "kilobytes": 1000.0,
    "mb": 1000.0**2, "megabyte": 1000.0**2, "megabytes": 1000.0**2,
    "gb": 1000.0**3, "gigabyte": 1000.0**3, "gigabytes": 1000.0**3,
    "tb": 1000.0**4, "terabyte": 1000.0**4, "terabytes": 1000.0**4,
    # IEC
    "kib": 1024.0, "kibibyte": 1024.0, "kibibytes": 1024.0,
    "mib": 1024.0**2, "mebibyte": 1024.0**2, "mebibytes": 1024.0**2,
    "gib": 1024.0**3, "gibibyte": 1024.0**3, "gibibytes": 1024.0**3,
    "tib": 1024.0**4, "tebibyte": 1024.0**4, "tebibytes": 1024.0**4,
}

# Temperature special-case (no linear factor)
_TEMP_TOK = {
    "c": "C", "°c": "C", "celsius": "C", "centigrade": "C",
    "f": "F", "°f": "F", "fahrenheit": "F",
    "k": "K", "kelvin": "K",
}

# ---------- Parsing ----------
_RX_GENERIC = re.compile(
    r"^\s*(?:convert\s+)?(?P<val>-?\d+(?:\.\d+)?)\s*(?P<src>[°a-zA-Z ]+?)\s*(?:to|in|->|→)\s*(?P<dst>[°a-zA-Z ]+)\s*$",
    re.I,
)
_RX_TEMP = re.compile(
    r"^\s*(?P<val>-?\d+(?:\.\d+)?)\s*°?\s*(?P<src>[cfk]|celsius|fahrenheit|kelvin)\s*(?:to|in|->|→)\s*°?\s*(?P<dst>[cfk]|celsius|fahrenheit|kelvin)\s*$",
    re.I,
)

def _norm_unit(tok: str) -> str:
    return re.sub(r"\s+", "", tok.strip().lower())

def _round_sig(x: float) -> str:
    # Round nicely for display
    if x == 0:
        return "0"
    ax = abs(x)
    if ax >= 100:
        s = f"{x:.0f}"
    elif ax >= 10:
        s = f"{x:.1f}"
    elif ax >= 1:
        s = f"{x:.2f}"
    else:
        s = f"{x:.3f}"
    return re.sub(r"(\.\d*?[1-9])0+$", r"\1", s).rstrip(".")

def _convert_linear(val: float, src: str, dst: str, table: dict) -> Optional[float]:
    s = _norm_unit(src)
    d = _norm_unit(dst)
    if s not in table or d not in table:
        return None
    base = val * table[s]
    return base / table[d]

def _convert_temp(val: float, src: str, dst: str) -> float:
    s = _TEMP_TOK[_norm_unit(src)]
    d = _TEMP_TOK[_norm_unit(dst)]
    # to Kelvin
    if s == "C":
        k = val + 273.15
    elif s == "F":
        k = (val - 32.0) * 5.0/9.0 + 273.15
    else:  # K
        k = val
    # from Kelvin
    if d == "C":
        return k - 273.15
    elif d == "F":
        return (k - 273.15) * 9.0/5.0 + 32.0
    else:
        return k

def _fmt_units(val: float, src: str, out: float, dst: str) -> str:
    src_n = _norm_unit(src)
    dst_n = _norm_unit(dst)
    # Prefer short canonical tokens in output
    def short(tok: str) -> str:
        # temperature printed with symbol
        if tok in _TEMP_TOK:
            return {"C":"°C","F":"°F","K":"K"}[_TEMP_TOK[tok]]
        # fallback to given token
        return tok
    return f"- {_round_sig(val)} {short(src_n)} ≈ {_round_sig(out)} {short(dst_n)}"

def _try_convert(q: str) -> Optional[str]:
    if not q:
        return None

    # Temperature first
    m = _RX_TEMP.match(q)
    if m:
        val = float(m.group("val"))
        src = m.group("src")
        dst = m.group("dst")
        out = _convert_temp(val, src, dst)
        return _fmt_units(val, src, out, dst)

    m = _RX_GENERIC.match(q)
    if not m:
        return None

    val = float(m.group("val"))
    src = m.group("src")
    dst = m.group("dst")

    # Try tables in order
    for table in (_LEN, _MASS, _VOL, _TIME, _DATA):
        out = _convert_linear(val, src, dst, table)
        if out is not None:
            return _fmt_units(val, src, out, dst)

    # If src/dst look like temperature tokens but missed the temp RX (different spacing/°)
    if _norm_unit(src) in _TEMP_TOK and _norm_unit(dst) in _TEMP_TOK:
        out = _convert_temp(val, src, dst)
        return _fmt_units(val, src, out, dst)

    return None

# Public entry points (router may call any of these)
def try_handle(q: str) -> Optional[str]:
    return _try_convert(q)

def handle(q: str) -> Optional[str]:
    return try_handle(q)

def skill(q: str) -> Optional[str]:
    return try_handle(q)

# --- Back-compat public entrypoint expected by the router/skills package ---
def try_units(q: str):
    # Prefer a dedicated dispatcher if you have one, otherwise fall back.
    fn = globals().get("dispatch") or globals().get("convert") or globals().get("handle")
    return fn(q) if callable(fn) else None
