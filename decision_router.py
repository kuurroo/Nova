# nova/decision_router.py
from __future__ import annotations
from typing import Dict, List, Tuple
from .orchestrator import answer as run_answer
from .core.router import warm_model as warm_model

def run_chat(history: List[Dict], *, model: str, trace: bool=False) -> Tuple[str, Dict]:
    # pick last user message
    q=""
    for m in reversed(history):
        if m.get("role")=="user":
            q=(m.get("content") or "").strip()
            break
    if not q: return "…", {"route":"empty"}
    t,m = run_answer(q, model=model, trace=trace)
    return t, m or {}
