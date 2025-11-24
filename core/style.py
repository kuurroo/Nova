# nova/core/style.py
from __future__ import annotations
import re, os
from ..config import NO_EMOJI

_EMOJI_RE = re.compile(
    r"[\U0001F1E6-\U0001F1FF]" # flags
    r"|[\U0001F300-\U0001F5FF]" # symbols & pictographs
    r"|[\U0001F600-\U0001F64F]" # emoticons
    r"|[\U0001F680-\U0001F6FF]" # transport & map
    r"|[\U0001F700-\U0001F77F]"
    r"|[\U0001F780-\U0001F7FF]"
    r"|[\U0001F800-\U0001F8FF]"
    r"|[\U0001F900-\U0001F9FF]"
    r"|[\U0001FA00-\U0001FA6F]"
    r"|[\U0001FA70-\U0001FAFF]"
    r"|[\uFE00-\uFE0F]"         # variation selectors
    r"|[\u200D]"                # zero-width joiner
, re.UNICODE)

def infer_style(q: str, sizing: dict|None=None) -> dict:
    s = dict(sizing or {})
    s.setdefault("mode", "brief")
    s.setdefault("tone", "neutral")
    s.setdefault("length", "medium")
    s.setdefault("web_budget", 800)
    s["no_emoji"] = NO_EMOJI or s.get("no_emoji", False)
    return s

def post_format(text: str, style: dict) -> str:
    out = (text or "")
    if style.get("no_emoji"):
        out = _EMOJI_RE.sub("", out)
    return out.strip()

def scrub_emoji_live(piece: str, style: dict) -> str:
    if not piece: return ""
    return _EMOJI_RE.sub("", piece) if style.get("no_emoji") else piece
