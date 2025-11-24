# nova/core/memory.py
from __future__ import annotations
import json, os, time, re
from typing import List, Dict, Optional

_DIR = os.path.expanduser("~/.nova")
_PATH = os.path.join(_DIR, "memory.jsonl")

def _ensure():
    os.makedirs(_DIR, exist_ok=True)
    if not os.path.exists(_PATH):
        with open(_PATH, "w", encoding="utf-8") as f: pass

def remember(text: str, tag: Optional[str] = None) -> Dict:
    _ensure()
    rec = {"id": str(int(time.time()*1000)), "ts": time.time(), "text": text, "tag": tag}
    with open(_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec

def load_all() -> List[Dict]:
    _ensure()
    out = []
    with open(_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line: continue
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    return out

def recall(q: Optional[str] = None, tag: Optional[str] = None, last: Optional[int] = None) -> List[Dict]:
    items = load_all()
    if tag:
        items = [r for r in items if r.get("tag")==tag]
    if q:
        rx = re.compile(re.escape(q), re.I)
        items = [r for r in items if rx.search(r.get("text","") or "")]
    items.sort(key=lambda r: r.get("ts",0), reverse=True)
    if last:
        items = items[:max(1,int(last))]
    return items

def forget(id_or_all: str) -> int:
    items = load_all()
    if id_or_all.lower() == "all":
        if os.path.exists(_PATH):
            os.remove(_PATH)
        _ensure()
        return 0
    kept = [r for r in items if r.get("id") != id_or_all]
    with open(_PATH, "w", encoding="utf-8") as f:
        for r in kept:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return len(items) - len(kept)
