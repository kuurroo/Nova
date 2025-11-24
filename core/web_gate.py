# nova/core/web_gate.py
from __future__ import annotations
from ..config import WEB_FORCE
def looks_recency_sensitive(q: str) -> bool:
    ql=(q or "").lower()
    return any(w in ql for w in ("today","now","this week","latest","breaking","release","driver","earnings","price"))

def needs_fresh(q: str) -> bool:
    ql=(q or "").lower()
    return any(w in ql for w in ("current","up-to-date","newest"))

def wants_web(recency: bool, fresh: bool) -> bool:
    return WEB_FORCE or recency or fresh
