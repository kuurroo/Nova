# nova/orchestrator.py
from __future__ import annotations
import os
import time
from .cache import answers as ANSWERS
from typing import Tuple, List, Dict, Optional
from .core.router import run_ollama_chat
from .core import web_fetcher as WF
from .core.style import _EMOJI_RE
from .quality import AnswerQuality, ResponseMode, apply as quality_apply
from .core import prefs as PREFS
from .core import router as ROUTER
from .core import persona as PERSONA

import re

# --- persona-aware greeting override (lightweight rule, not a skill) ---
_GREET_RE = re.compile(r'^(hi|hello|hey|yo|hiya|howdy)[!. ]*$', re.I)

def _maybe_greeting_override(q: str) -> str | None:
    s = (q or "").strip()
    if _GREET_RE.fullmatch(s):
        g = PERSONA.get_greeting()
        return g if g else "Hi there!"
    return None
# --- end greeting override ---

# ------------- helpers / toggles -----------------
def _FW() -> bool:
    return os.getenv("NOVA_FORCE_WEB","0") in ("1","true","yes")

def _NE() -> bool:
    v = (os.getenv("NOVA_NOEMOJI","0") or os.getenv("NOVA_NO_EMOJI","0") or "0")
    return v.lower() in ("1","true","yes","on")

    if re.search(r'(define|what is|explain|how to|algorithm|guide)', ql):
        return False
    return bool(re.search(r'(latest|today|now|new|recent|release|notes|price|driver|patch|earnings)', ql))

def _final_scrub(s: str) -> str:
    if not s: return s
    if not _NE(): return s
    out = _EMOJI_RE.sub("", s)  # <-- must be _EMOJI_RE
    out = re.sub(r"[ \t]+", " ", out)
    out = re.sub(r" *\n *", "\n", out).strip()
    return out or "[empty]"

def _load_style_defaults() -> dict:
    # stored by /style set … ; harmless if missing
    try:
        st = PREFS.load() or {}
        return (st.get("style") or {})
    except Exception:
        return {}

# Use the unified skill router in core.router (units, mathx, timex, weather, fxx, …)
# centralized skills
from .core.router import skill_first as _skill_router

# ------------- web orchestrations ----------------
def _web_try(query: str, budget: int = 800) -> Tuple[str, Dict]:
    t0 = time.perf_counter()
    txt, meta = WF.search_and_summarize(query, budget_tokens=budget)
    if os.getenv("NOVA_TIMINGS","0")=="1":
        print(f"[timing] nova.orchestrator.web={time.perf_counter()-t0:.2f}s", flush=True)
    return txt, (meta or {})

def _web_with_adaptive_retry(query: str, budget: int = 800) -> Tuple[str, Dict]:
    # 1st pass
    txt, meta = _web_try(query, budget)
    links = (meta or {}).get("links") or []
    if txt and len(txt.strip())>0 and len(links)>0:
        return txt, meta

    # retry once with a refined query (site: & add version-ish tokens)
    q2 = WF.adaptive_requery(query)
    if q2 and q2 != query:
        if os.getenv("NOVA_DIAG","0")=="1":
            print(f"[web] retry with: {q2}", flush=True)
        txt2, meta2 = _web_try(q2, budget)
        links2 = (meta2 or {}).get("links") or []
        if txt2 and len(txt2.strip())>0 and len(links2)>0:
            return txt2, meta2

    # give back empty; caller will decide fallback
    return txt or "", meta or {}


# --- curated answers module loader (lazy) ---
def _get_answers_module():
    try:
        from .cache import answers as ANSW
        return ANSW
    except Exception:
        return None
# ------------- model run -------------------------

def _model_answer(q: str, model: Optional[str]) -> Tuple[str, Dict]:
    # Base messages
    sys_rules = PERSONA.compose_system_rules()
    try:
        import time
        sys_rules = f"{sys_rules}\n\n(Current date/time: {time.strftime('%Y-%m-%d %H:%M %Z')})"
    except Exception:
        pass
    messages = [
      {"role": "system", "content": sys_rules},
      {"role": "user", "content": q},
    ]

    # OPTIONAL: exact-count + topic/format nudges when explicitly requested
    try:
        from .quality import BULLET_N_RE, SENT_N_RE
        import re as _re

        ql = (q or "").lower()
        hints: list[str] = []

        # exact N bullets / sentences
        bm = BULLET_N_RE.search(ql)
        sm = SENT_N_RE.search(ql)
        if bm:
            n = int(bm.group(1))
            hints.append(
                f"Return exactly {n} bullet points. One short clause per bullet. "
                "No preamble or conclusion. Output only the bullet points. "
                "Do not repeat these instructions."
            )
        if sm:
            n = int(sm.group(1))
            hints.append(
                f"Write exactly {n} sentences. No lead-in or wrap-up. "
                "Output only the sentences. Do not repeat these instructions."
            )

        # steps request (format nudge)
        if _re.search(r"\bsteps?\b", ql):
            hints.append(
                "Return exactly 5 numbered steps. One action per step. "
                "No preamble or wrap-up. Output only the steps. Do not repeat these instructions."
            )

        # derive a topic anchor by stripping format directives
        topic = _re.sub(r"\b(?:in|with)\s+\d+\s+(?:bullets?|sentences?)\b", "", q, flags=_re.I)
        topic = _re.sub(r"\b(code only|tl;dr|tldr|summary|steps?)\b", "", topic, flags=_re.I).strip()
        if topic:
            hints.append(f"Stay strictly on topic: {topic}. Do not include unrelated content.")

        if hints:
            # insert right after the base system message
            messages.insert(1, {"role": "system", "content": " ".join(hints)})
    except Exception:
        # if quality module changes, skip the nudge silently
        pass

    text, meta = run_ollama_chat(
        messages,
        model=model or os.getenv("MODEL", "nous-hermes-13b-fast:latest"),
        stream=(os.getenv("NOVA_STREAM", "0") == "1"),
    )
    meta = meta or {}
    meta.setdefault("route", "model")
    return text or "", meta

# ------------- public API ------------------------
def router_warm(model: str) -> Dict:
    # a cheap, one-token warmup that lets Ollama spin up
    t0 = time.perf_counter()
    _ = run_ollama_chat([{"role":"user","content":"."}], model=model, stream=False)
    return {"ms": int((time.perf_counter()-t0)*1000)}

def _looks_recency_sensitive(q: str) -> bool:
    """Returns True if the query likely needs fresh web info."""
    import re as _re
    ql = (q or "").lower().strip()

    # Strong recency cues — ALWAYS true even if short
    if _re.search(r"\b(20(2[0-9]|3[0-9]))\b", ql):                        # years 2020–2039
        return True
    if _re.search(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)\b", ql):
        return True
    if _re.search(r"\b(today|now|latest|breaking|release\s+notes|driver|price|cve|security)\b", ql):
        return True

    # Short generic asks → NOT recency-sensitive (word boundaries)
    if len(ql.split()) <= 6 and _re.search(r"\b(explain|what\s+is|how|code|example)\b", ql):
        return False

    # Conservative default: offline unless explicit cues appear
    return False


_GREETING_RE = re.compile(r"^(hi|hello|hey|hiya|yo|sup|howdy)[!. ]*$", re.I)

def answer(q: str, model: Optional[str] = None, trace: bool = False) -> Tuple[str, Dict]:
    if trace:
        print("[orchestrator] enter answer()")

    q_s = (q or "").strip()

    # ---- code-only fast-path (no model) ----
    qs_low = (q_s or "").lower()
    if qs_low.startswith("code only:") or qs_low.startswith("code-only:") or " code only:" in qs_low:
        try:
            payload = q_s.split(":", 1)[1].strip()
        except Exception:
            payload = q_s
        fence = "```python\n" if any(k in payload for k in ("def ", "import ", "print(", "class ", "lambda ")) else "```\n"
        return f"{fence}{payload}\n```", {"route": "code-only"}

    # 0) persona greeting intercept (not a skill)
    if _GREET_RE.fullmatch(q_s):
        g = PERSONA.get_greeting()
        if g:
            return g, {"route": "persona-greeting"}

    # 1) core skills (units, mathx, timex, weather, fxx, …)
    try:
        skill_txt = _skill_router(q_s)
    except Exception:
        skill_txt = None
    if skill_txt:
        return _final_scrub(skill_txt), {"route": "skill"}

    # 2) web path if allowed & wanted (recency/price/etc.)
    env_web = (os.getenv("NOVA_WEB", "0").lower() in ("1", "true", "yes")) or _FW()
    try:
        wants_web = ROUTER.wants_web(q_s)
    except Exception:
        wants_web = False

    web_txt = ""
    web_meta: Dict = {}
    if env_web and (wants_web or _FW()):
        web_txt, web_meta = _web_with_adaptive_retry(q_s, budget=800)
        links = (web_meta or {}).get("links") or []
        if web_txt and web_txt.strip() and links:
            shaped = quality_apply(web_txt, q_s, _load_style_defaults())
            return _final_scrub(shaped), {"route": "web", **web_meta}
        print("(no useful web signal: empty/blocked) → falling back to model", flush=True)

    # 3) curated answers (A3) — pinned/local facts win
    try:
        curated = ANSW.maybe(q_s)
        if curated:
            return curated, {"route": "answers"}
    except Exception:
        pass

    # 4) model answer
    # curated answers layer: short-circuit if a pinned answer exists
    ANSW = _get_answers_module()
    if ANSW:
        try:
            try:
                q_line = q_s  # prefer stripped alias if present
            except NameError:
                q_line = q
            curated = ANSW.maybe(q_line)
            if curated:
                return curated, {"route": "answers"}
        except Exception:
            pass

    mdl_txt, mdl_meta = _model_answer(q_s, model)

    # 5) code-only guard: skip shaping if explicitly requested
    if "code only" in q_s.lower():
        return mdl_txt, {"route": "model"}

    # 6) quality shaping (respect /style defaults)
    try:
        shaped = quality_apply(mdl_txt, q_s, _load_style_defaults())
        if shaped:
            mdl_txt = shaped
    except Exception:
        pass

    # 7) Final honesty if we wanted web but it returned nothing
    if env_web and wants_web and not (web_txt and web_txt.strip()):
        return (
            "(online info unavailable) — could not fetch reliable results right now. "
            "Try again with /forceweb, or be more specific.",
            {"route": "model", "note": "web-empty"},
        )

    return _final_scrub(mdl_txt), {"route": "model"}
