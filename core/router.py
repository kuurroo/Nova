# nova/core/router.py
from __future__ import annotations
import json, time, os, urllib.request
from typing import List, Tuple, Dict, Any
from ..logging import diag, timing
from .skills import units, mathx, timex
OLLAMA = os.getenv("OLLAMA_HOST", "http://localhost:11434")

OLLAMA_TIMEOUT_S=int(os.getenv('NOVA_OLLAMA_TIMEOUT','45'))
# Skills (module-centric)
try:
    from .skills import weather  # optional; may not exist yet
except Exception:
    weather = None
# Optional skills
try:
    from .skills import fxx  # forex
except Exception:
    fxx = None

try:
    from .skills import weather
except Exception:
    weather = None
# --- Generic skill pass: call the first skill that handles the query ---

import os
_TRACE = os.getenv("NOVA_TRACE","0") == "1"

def _call_try_handle(mod, q: str):
    for fn_name in ("try_handle", "handle", "skill"):
        f = getattr(mod, fn_name, None)
        if callable(f):
            try:
                out = f(q)
                if out:
                    if _TRACE:
                        # e.g. [skill] weather.try_handle
                        print(f"[skill] {getattr(mod, '__name__', mod)}.{fn_name}", flush=True)
                    return out
            except Exception:
                if _TRACE:
                    print(f"[skill-error] {getattr(mod, '__name__', mod)}.{fn_name}", flush=True)
                # swallow so other skills can try
                pass
    return None

def skill_first(q: str) -> Optional[str]:
    """
    Try lightweight skills before we even consider model/web.
    Returns already-formatted text if a skill handled it, else None.
    """
    # collect available skill modules in order of preference
    modules = []

    # FX first if present
    if fxx:      modules.append(fxx)
    # fast number/unit/time handlers
    from .skills import units, mathx, timex
    modules += [units, mathx, timex]
    # weather last (can be online/offline internally)
    if weather:  modules.append(weather)

    for mod in modules:
        try:
            out = mod.try_handle(q)  # each module exposes try_handle(q)->str|None
        except AttributeError:
            # legacy modules export specific names, fall back
            for name in ("try_units", "try_mathx", "try_timex", "try_weather", "try_forex", "try_fxx"):
                f = getattr(mod, name, None)
                if f:
                    out = f(q)
                    break
        if out:
            return out

    try:

        out = fxx.try_fxx(q)

        if out:

            return out

    except Exception:

        pass

    return None

def _post(path: str, payload: dict) -> dict:
    req = urllib.request.Request(f"{OLLAMA}{path}",
                                 data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=OLLAMA_TIMEOUT_S) as r:
        return json.loads(r.read().decode("utf-8"))

def warm_model(model: str) -> dict:
    t0=time.perf_counter()
    try:
        # Ollama "generate" with keep_alive is a quick warm
        _post("/api/generate", {"model": model, "prompt": " ", "stream": False, "keep_alive": "20m"})
        out={"ok": True, "ms": int((time.perf_counter()-t0)*1000), "model": model, "keep_alive":"20m"}
        diag(f"[router] warm {model}: {out['ms']}ms")
        return out
    except Exception as e:
        return {"ok": False, "error": repr(e)}

def run_ollama_chat(messages: List[Dict[str,str]], *, model: str, stream: bool=False, options: dict|None=None) -> Tuple[str, dict]:
    t0 = time.perf_counter()
    # Convert to "prompt" for /generate to keep things simple
    prompt = ""
    for m in messages:
        role = m.get("role")
        content = m.get("content") or ""
        if role == "system": prompt += f"[SYS] {content}\n"
        elif role == "user": prompt += f"[USER] {content}\n"
        else: prompt += f"[ASSISTANT] {content}\n"
    res = _post("/api/generate", {"model": model, "prompt": prompt, "stream": False})
    text = (res.get("response") or "").strip()
    meta = {k:res.get(k) for k in ("created_at","total_duration","load_duration",
                                   "prompt_eval_count","prompt_eval_duration",
                                   "eval_count","eval_duration")}
    if os.getenv("NOVA_TIMINGS","0")=="1":
        pe, ge = meta.get("prompt_eval_duration"), meta.get("eval_duration")
        pec, gec = meta.get("prompt_eval_count"), meta.get("eval_count")
        ptps = (pec/pe*1e9) if (pec and pe) else None
        gtps = (gec/ge*1e9) if (gec and ge) else None
        extra = (f" prompt_tps~{ptps:.1f}" if ptps else "") + (f" gen_tps~{gtps:.1f}" if gtps else "")
        timing(f"[model] total={time.perf_counter()-t0:.2f}s{extra}")
    diag("[router] run_ollama_chat ok")
    return text, meta or {}


def build_prompt(messages):
    """Very small prompt builder: turn a chat list into a plain prompt for /api/generate."""
    lines = []
    for m in messages or []:
        role = m.get("role","user").strip().lower()
        content = (m.get("content","") or "").strip()
        if role == "system":
            lines.append(f"[SYS] {content}")
        elif role == "assistant":
            lines.append(f"Assistant: {content}")
        else:
            lines.append(f"User: {content}")
    lines.append("Assistant:")
    return "\n".join(lines)

__all__ = ["skill_first", "run_ollama_chat", "route_message"]

# export alias expected by orchestrator
skill_router = skill_first

# --- NOVA recency heuristic (append) -----------------------------------------
import re as _re_router_q

# Strong recency/news/prices/etc. cues (word boundary)
_RECENCY_RE = _re_router_q.compile(
    r"\b("
    r"latest|today|tonight|now|this\s+(week|month)|"
    r"release\s*notes|changelog|driver|patch|update|"
    r"cve-\d{4}-\d+|vuln(?:erability)?|"
    r"price\s*today|stock\s*price|"
    r"outage|status|schedule|"
    r"forecast|weather|"
    r"ranking|standings|score|results?"
    r")\b",
    _re_router_q.I,
)

def wants_web(q: str) -> bool:
    """Return True only for prompts that clearly need fresh/online data."""
    ql = (q or "").lower().strip()

    # Very short "teach me X" asks should stay offline for speed
    if len(ql.split()) <= 6 and ql.startswith(("explain", "what", "code", "example", "show")):
        return False

    # Clear recency keywords
    if _RECENCY_RE.search(ql):
        return True

    # Year cues (often imply recency: 2024, 2025, …)
    if _re_router_q.search(r"\b20(2\d|3\d)\b", ql):
        return True

    return False

# Export alias some call-sites expect
try:
    skill_router  # already defined elsewhere (your existing order/logic)
except NameError:
    try:
        # common name in your tree
        skill_router = skill_first   # type: ignore[name-defined]
    except Exception:
        pass
# --------------------------------------------------------------------------- end
