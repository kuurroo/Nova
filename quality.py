# nova/quality.py
from __future__ import annotations

import re
from typing import Optional, TypedDict, Literal, Dict

# -----------------------------
# Types
# -----------------------------
Verbosity = Literal["brief", "normal", "detailed"]
OutFormat = Literal["plain", "bullets", "steps", "code", "mixed"]

class ResponseMode(TypedDict):
    verbosity: Verbosity
    format: OutFormat
    max_words: Optional[int]           # None → no forced cap
    bullet_count: Optional[int]        # Only honored when explicitly requested
    sentence_cap: Optional[int]        # Only honored when explicitly requested

# -----------------------------
# Heuristics & helpers
# -----------------------------
BULLET_N_RE = re.compile(r"\b(?:in|with)?\s*(\d+)\s*bullets?\b", re.I)
SENT_N_RE   = re.compile(r"\b(\d+)\s*sentences?\b", re.I)

_WORDY = re.compile(r"\b(tl;dr|tldr)\b", re.I)

def _strip_leading_markers(line: str) -> str:
    # Strip -, *, •, 1., 1), Step 1:, etc.
    return re.sub(r"^\s*(?:[-*•]\s*|\d+[.)]\s*|step\s*\d+\s*:\s*)", "", line, flags=re.I).strip()

def _split_sentences(text: str):
    # Keep it simple and safe for code-free prose
    return [t.strip() for t in re.split(r"(?<=[.!?])\s+", text) if t.strip()]

def _clean_step_line(s: str) -> str:
    # strip obvious noise/artifacts the model sometimes emits
    x = (s or "").strip()

    # remove things like ['1.   or ["1.   at the start
    x = re.sub(r"^\s*\[?['\"]?\s*\d+\.\s*", "", x)

    # remove "- " or "* " bullet markers
    x = re.sub(r"^\s*[-*]\s+", "", x)

    # remove prefixes like: Step 1: / Step 2) / 1) / 1- etc
    x = re.sub(r"^\s*(?:step\s*\d+[:.)-]\s*|\d+[:.)-]\s*)", "", x, flags=re.I)

    # drop noisy tags like [SYS] that occasionally sneak in
    x = re.sub(r"^\s*\[?\s*sys\s*\]?\s*", "", x, flags=re.I)

    # final trim of leftover bracket/quote fluff
    x = x.strip("[]'\" ").strip()
    return x

# -----------------------------
# Core
# -----------------------------
class AnswerQuality:
    def __init__(self, text: str):
        self.text = text or ""

    # Merge explicit choices with defaults; do NOT force bullets/sentences if not asked
    def merge_with_defaults(self, mode: ResponseMode, defaults: Optional[Dict] = None) -> ResponseMode:
        if not defaults:
            return mode
        out: ResponseMode = {
            "verbosity": mode["verbosity"],
            "format": mode["format"],
            "max_words": mode.get("max_words"),
            "bullet_count": mode.get("bullet_count"),
            "sentence_cap": mode.get("sentence_cap"),
        }  # type: ignore
        if out.get("max_words") is None and defaults.get("max_words") is not None:
            out["max_words"] = defaults.get("max_words")  # type: ignore
        # Never force bullet_count/sentence_cap from defaults
        return out

    def render(self, t: str, mode: ResponseMode) -> str:
        fmt = mode["format"]

        # --- explicit formats first ---
        if fmt == "bullets":
            # Normalize incoming lines (strip any existing markers and filler)
            lines = [ln for ln in (ln.strip() for ln in (t or "").splitlines()) if ln]
            lines = [_strip_leading_markers(ln) for ln in lines]
            lines = [ln for ln in lines if not ln.lower().startswith(("to explain", "we can", "here are", "the following"))]
            bc = mode.get("bullet_count")
            if bc and bc > 0:
                lines = lines[:bc]
            return "\n".join(f"- {ln}" for ln in lines)

        elif fmt == "steps":
                # Robust steps shaping: sentences → clauses → scrub artifacts → cap → number
                src = (t or "").replace("\n", " ").strip()

                # start by splitting on sentence ends; fall back to clause-ish joins
                sents = _split_sentences(src)
                if len(sents) < 3:
                        sents = re.split(r'(?:;|\s+then\s+|\s+and\s+)', src)

                # scrub/normalize each line and drop empties or generic fluff
                cleaned = []
                for x in sents:
                        x2 = _clean_step_line(x)
                        if not x2:
                                continue
                        # filter a few boilerplate lead-ins
                        if x2.lower().startswith(("here are", "to explain", "we can", "in this")):
                                continue
                        cleaned.append(x2)

                # sentence cap (defaults to 5 if not set by the mode)
                cap = (mode.get("sentence_cap") or 5)
                cleaned = cleaned[:cap] if cap and cap > 0 else cleaned

                # graceful fallback
                if not cleaned and src:
                        cleaned = [_clean_step_line(src)]

                return "\n".join(f"{i+1}. {ln}" for i, ln in enumerate(cleaned))

        elif fmt == "code":
            body = t or ""
            # If not fenced, wrap; label as python if it looks like Python
            looks_py = any(k in body for k in ("def ", "import ", "print(", "lambda ", "for ", "while ", "class "))
            if "```" not in body:
                fence = "```python\n" if looks_py else "```\n"
                return f"{fence}{body.strip()}\n```"
            return body

        # --- plain/mixed (sentence cap can apply) ---
        text = t or ""

        # sentence cap (only if explicitly requested and no code fences)
        sc = mode.get("sentence_cap")
        if sc and sc > 0 and fmt in ("plain", "mixed") and "```" not in text:
            sents = _split_sentences(text)
            if sents:
                text = " ".join(sents[:sc])

        # word cap last (if provided)
        mw = mode.get("max_words")
        if isinstance(mw, int) and mw > 0:
            words = text.split()
            if len(words) > mw:
                text = " ".join(words[:mw]).rstrip() + "…"

        return text


# -----------------------------
# Policy: infer mode from the ask + defaults
# -----------------------------
def _infer_word_caps(q_line: str) -> Optional[int]:
    # We keep this conservative; users can set /style or ask for a cap directly
    if _WORDY.search(q_line or ""):
        return 40
    return None

def decide_response_mode(q_line: str, defaults: Optional[Dict] = None) -> ResponseMode:
    ql = (q_line or "").strip()
    ql_lower = ql.lower()

    # Base guesses
    fmt: OutFormat = "plain"
    verb: Verbosity = "normal"

    # Detect "in N steps" → prefer steps format + cap (can be overridden by explicit targets below)
    sc_steps: Optional[int] = None
    try:
        m_steps_n = re.search(r"\b(\d+)\s*steps?\b", ql_lower)
        if m_steps_n:
            sc_steps = int(m_steps_n.group(1))
    except Exception:
        sc_steps = None

    # Inline format hints
    if "code only" in ql_lower or ql_lower.startswith("code only:") or ql_lower.startswith("code-only:"):
        fmt = "code"
    elif " in steps" in ql_lower or ql_lower.startswith("steps:"):
        fmt = "steps"
    elif " in bullets" in ql_lower or ql_lower.startswith("bullets:"):
        fmt = "bullets"
    elif ql_lower.startswith("tl;dr") or " tl;dr" in ql_lower:
        verb = "brief"
        fmt = "plain"

    # explicit targets
    bc: Optional[int] = None
    sc: Optional[int] = None

    m_b = BULLET_N_RE.search(ql)
    if m_b:
        fmt = "bullets"
        try:
            bc = int(m_b.group(1))
        except Exception:
            bc = None

    m_s = SENT_N_RE.search(ql)
    if m_s:
        fmt = "plain"
        try:
            sc = int(m_s.group(1))
        except Exception:
            sc = None

    # Apply steps-count preference only if no explicit sentence target already set
    if sc is None and sc_steps is not None and fmt != "code":
        fmt = "steps"
        sc = sc_steps

    mode: ResponseMode = {
        "verbosity": verb,
        "format": fmt,
        "max_words": _infer_word_caps(ql),
        "bullet_count": bc,
        "sentence_cap": sc,
    }

    # merge-only defaults (do not force bullets/sentences)
    if defaults:
        aq = AnswerQuality("")
        mode = aq.merge_with_defaults(mode, defaults)

    return mode

# -----------------------------
# External entry
# -----------------------------
def apply(text: str, q_line: str, style_defaults: Optional[Dict] = None) -> str:
    mode = decide_response_mode(q_line, style_defaults)
    aq = AnswerQuality(text)
    shaped = aq.render(text, mode)

    # Optional friendly lead-ins (toggle via prefs.style.leadins = True/False)
    try:
        from .core import prefs as PREFS
        st = PREFS.load() or {}
        lead = (st.get('style') or {}).get('leadins', False)
        if lead and mode.get('format') != 'code' and shaped:
            tag = (
                'steps' if mode.get('format') == 'steps'
                else 'bullets' if mode.get('format') == 'bullets'
                else 'plain'
            )
            head = (
                'Sure — here are the steps:' if tag == 'steps' else
                'Sure — here are some quick bullets:' if tag == 'bullets' else
                "Sure — here’s a quick answer:"
            )
            if not shaped.lstrip().lower().startswith(('sure ', 'sure—', 'sure,')):
                shaped = head + '\n' + shaped
    except Exception:
        pass

    return shaped


def _clamp_bullets(n: int, lo: int=2, hi: int=10) -> int:
    try: return max(lo, min(hi, int(n)))
    except: return 5


def _tidy_steps(text: str, default_n: int = 5) -> str:
    t = (text or '').strip()
    if not t:
        return t
    if re.search(r'^\s*\d+\.', t, re.M):
        return t  # already numbered
    parts = re.split(r'(?<=[.!?])\s+|;\s+|\s+then\s+', t)
    parts = [p.strip() for p in parts if p.strip()]
    parts = parts[:default_n] if len(parts) > default_n else parts
    return '\n'.join(f"{i+1}. {p}" for i, p in enumerate(parts))


def enforce_shape(q_line: str, text: str, style_defaults=None) -> str:
    try:
        return apply(text, q_line, style_defaults)
    except Exception:
        return text
