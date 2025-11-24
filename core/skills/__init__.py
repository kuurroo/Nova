# nova/core/skills/__init__.py
from __future__ import annotations

from typing import Optional, Callable

# Import modules (not symbols) so we can provide back-compat shims.
from . import units as _units
from . import mathx as _mathx
from . import timex as _timex

try:
    from . import weather as _weather  # optional
except Exception:
    _weather = None  # type: ignore[assignment]

try:
    from . import fxx as _fxx  # optional: forex
except Exception:
    _fxx = None  # type: ignore[assignment]


def _attach_if_missing(mod, public_name: str, candidates: list[str]) -> None:
    """
    If `mod` does not have `public_name`, but has one of `candidates`,
    attach a thin wrapper so external callers can keep using `public_name`.
    """
    if mod is None or hasattr(mod, public_name):
        return
    fn: Optional[Callable[[str], Optional[str]]] = None
    for cand in candidates:
        cand_fn = getattr(mod, cand, None)
        if callable(cand_fn):
            fn = cand_fn  # first match wins
            break
    if fn is None:
        # Nothing we can do; leave it missing.
        return

    def _shim(q: str) -> Optional[str]:
        try:
            return fn(q)
        except Exception:
            return None

    setattr(mod, public_name, _shim)


# Provide stable public entrypoints expected elsewhere in Nova
_attach_if_missing(_units,  "try_units",  ["try_units", "dispatch", "convert", "handle", "try_convert"])
_attach_if_missing(_mathx,  "try_mathx",  ["try_mathx", "handle", "eval_expr", "calculate"])
_attach_if_missing(_timex,  "try_timex",  ["try_timex", "handle", "parse_time", "compute"])
if _weather is not None:
    _attach_if_missing(_weather, "try_weather", ["try_weather", "handle", "lookup", "fetch"])
if _fxx is not None:
    _attach_if_missing(_fxx, "try_fxx", ["try_fxx", "handle", "quote", "lookup"])

# Re-export module aliases so callers can do: from .skills import units, mathx, timex, ...
units = _units
mathx = _mathx
timex = _timex
weather = _weather
fxx = _fxx

# And also re-export the stable callables at package level (optional convenience)
def try_units(q: str) -> Optional[str]:
    return getattr(units, "try_units")(q) if hasattr(units, "try_units") else None  # type: ignore[attr-defined]

def try_mathx(q: str) -> Optional[str]:
    return getattr(mathx, "try_mathx")(q) if hasattr(mathx, "try_mathx") else None  # type: ignore[attr-defined]

def try_timex(q: str) -> Optional[str]:
    return getattr(timex, "try_timex")(q) if hasattr(timex, "try_timex") else None  # type: ignore[attr-defined]

def try_weather(q: str) -> Optional[str]:
    return getattr(weather, "try_weather")(q) if weather and hasattr(weather, "try_weather") else None  # type: ignore[attr-defined]

def try_fxx(q: str) -> Optional[str]:
    return getattr(fxx, "try_fxx")(q) if fxx and hasattr(fxx, "try_fxx") else None  # type: ignore[attr-defined]
