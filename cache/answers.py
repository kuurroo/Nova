import json
import hashlib
import time
import os
from pathlib import Path
CACHE_PATH = Path.home()/".cache"/"nova"/"answer_cache.jsonl"
CACHE_TTL_DEFAULT = int(os.getenv("NOVA_CACHE_TTL","3600"))
def _ensure(): CACHE_PATH.parent.mkdir(parents=True, exist_ok=True); CACHE_PATH.exists() or CACHE_PATH.touch()
def _now(): return int(time.time())
def key_for(query, intent=None):
    q=" ".join((query or "").split()).lower().strip()
    salt=json.dumps({"intent":intent or "","vers":os.getenv("NOVA_VERSION","dev")},sort_keys=True)
    return hashlib.sha256((q+"|"+salt).encode()).hexdigest()[:16]
def get(query,intent=None,ttl=CACHE_TTL_DEFAULT):
    _ensure(); k=key_for(query,intent); hit=None
    for line in CACHE_PATH.read_text(encoding="utf-8").splitlines():
        try:
            obj=json.loads(line)
            if obj.get("k")==k: hit=obj
        except Exception: pass
    if hit and (_now()-hit.get("t",0) <= ttl): return hit.get("text"), hit.get("meta",{})
    return None, None
def put(query,text,meta=None,intent=None):
    _ensure(); rec={"k":key_for(query,intent),"t":_now(),"text":text,"meta":meta or {}}
    with CACHE_PATH.open("a",encoding="utf-8") as f: f.write(json.dumps(rec,ensure_ascii=False)+"\n")
    return True


# --- curated answers: minimal API ---
import os
import json
import re
_EPHEMERAL = {}
_PERSIST = os.path.expanduser('~/.cache/nova/curated_answers.json')
def _norm(t: str) -> str:
    return ' '.join((t or '').lower().split())
def _load_persist() -> dict:
    try:
        with open(_PERSIST, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

def _save_persist(d: dict) -> None:
    os.makedirs(os.path.dirname(_PERSIST), exist_ok=True)
    with open(_PERSIST, 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
def add_ephemeral(q: str, text: str) -> None:
    _EPHEMERAL[_norm(q)] = text or ''
def add_persistent(q: str, text: str) -> None:
    d = _load_persist(); d[_norm(q)] = text or ''
    _save_persist(d)
def maybe(q: str):
    n = _norm(q); d = _load_persist()
    return _EPHEMERAL.get(n) or d.get(n)


def remove(key: str) -> bool:
    """Remove a curated entry (best-effort).
    Clears ephemeral and overwrites persistent with an empty string (treated as absent)."""
    k = (key or '').strip().lower()
    try:
        _ephemeral.pop(k, None)
    except Exception:
        pass
    try:
        add_persistent(k, '')
        return True
    except Exception:
        return False
