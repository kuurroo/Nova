# nova/cache/store.py
from __future__ import annotations
import hashlib, json, os, time
from typing import Tuple, Dict, Any

_CACHE: dict[str, Tuple[str, Dict[str, Any]]] = {}  # key -> (text, meta)

def _key(q: str, style: dict, model: str, recency: bool, fresh: bool) -> str:
    blob = json.dumps({"q":q.strip(), "m":model, "s":style.get("mode","brief"),
                       "r":bool(recency), "f":bool(fresh)}, sort_keys=True)
    return hashlib.sha1(blob.encode('utf-8')).hexdigest()

def get(q: str, style: dict, model: str, recency: bool, fresh: bool):
    k = _key(q, style, model, recency, fresh)
    val = _CACHE.get(k)
    if val: return val
    return None

def set(q: str, style: dict, model: str, recency: bool, fresh: bool, text: str, meta: dict):
    if not text: return
    k = _key(q, style, model, recency, fresh)
    _CACHE[k] = (text, dict(meta or {}, cached_at=int(time.time())))
