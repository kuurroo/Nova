# nova/diagnostics.py
from __future__ import annotations
import os, time, functools, inspect, traceback
from .config import DIAG, TIMINGS

def _loc():
    f = inspect.currentframe()
    if f and f.f_back and f.f_back.f_back:
        code = f.f_back.f_back.f_code
        return f"{code.co_filename}:{code.co_firstlineno}"
    return "?:?"

def trace(fn):
    @functools.wraps(fn)
    def wrapper(*a, **kw):
        if DIAG: print(f"[trace] enter {fn.__module__}.{fn.__name__} @{_loc()}", flush=True)
        t0 = time.perf_counter()
        try:
            out = fn(*a, **kw)
            return out
        except Exception as e:
            tb = traceback.format_exc(limit=3)
            print(f"[trace] EXC in {fn.__module__}.{fn.__name__}: {e!r}\n{tb}", flush=True)
            raise
        finally:
            if TIMINGS:
                dt = time.perf_counter() - t0
                print(f"[timing] {fn.__module__}.{fn.__name__}={dt:.2f}s", flush=True)
    return wrapper

def pretty_exc(e: Exception) -> str:
    return f"{e.__class__.__name__}: {e}"
