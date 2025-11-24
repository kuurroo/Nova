import os, json
from pathlib import Path
_CFG=Path.home()/".config/nova"; _CFG.mkdir(parents=True, exist_ok=True)
_FILE=_CFG/"prefs.json"
def load(): 
    try: return json.loads(_FILE.read_text())
    except Exception: return {}
def save(d):
    try: _FILE.write_text(json.dumps(d, indent=2)); return True
    except Exception: return False
def set_flag(key, on):
    st=load(); st[key]=bool(on); save(st); return st

# --- pinned tickers (for fxx) ---
def get_pinned_tickers():
    s=_state(); arr=s.get('pinned_tickers', [])
    return list(dict.fromkeys([str(t).strip().upper() for t in arr if str(t).strip()]))
def pin_tickers(items):
    s=_state(); cur=set([str(t).strip().upper() for t in s.get('pinned_tickers', [])])
    for t in (items or []):
        t=str(t).strip().upper()
        if t: cur.add(t)
    s['pinned_tickers']=sorted(cur); _save(s); return get_pinned_tickers()
def clear_tickers():
    s=_state(); s['pinned_tickers']=[]; _save(s); return []
