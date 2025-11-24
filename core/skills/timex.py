# nova/core/skills/timex.py
from __future__ import annotations
from datetime import datetime, timedelta, date, time
import re
from typing import Optional

NAME = "timex"

# Basic patterns: "days until YYYY-MM-DD", "what day is 2025-10-21", "add 2h 30m to 14:10"
_RX_UNTIL = re.compile(r"^\s*days?\s+until\s+(\d{4}-\d{2}-\d{2})\s*$", re.I)
_RX_WEEKDAY = re.compile(r"^\s*what\s+day\s+is\s+(\d{4}-\d{2}-\d{2})\s*$", re.I)
_RX_ADD_TIME = re.compile(r"^\s*add\s+((?:\d+\s*h)?\s*(?:\d+\s*m)?\s*(?:\d+\s*s)?)\s+to\s+(\d{1,2}:\d{2})\s*$", re.I)
_RX_NOW = re.compile(r"^\s*(?:what(?:'s| is)\s+)?(?:the\s+)?time\s*(?:now)?\s*\?*\s*$", re.I)
_RX_TODAY = re.compile(r"^\s*(?:what(?:'s| is)\s+)?(?:the\s+)?date\s*(?:today)?\s*\?*\s*$", re.I)

def _parse_hms(s: str) -> timedelta:
    h = m = sec = 0
    m1 = re.search(r"(\d+)\s*h", s, re.I)
    m2 = re.search(r"(\d+)\s*m", s, re.I)
    m3 = re.search(r"(\d+)\s*s", s, re.I)
    if m1: h = int(m1.group(1))
    if m2: m = int(m2.group(1))
    if m3: sec = int(m3.group(1))
    return timedelta(hours=h, minutes=m, seconds=sec)

def _try_timex(q: str) -> Optional[str]:
    if not q: return None

    m = _RX_NOW.match(q)
    if m:
        now = datetime.now()
        return f"- now: {now.strftime('%Y-%m-%d %H:%M:%S')}"

    m = _RX_TODAY.match(q)
    if m:
        today = date.today()
        return f"- today: {today.isoformat()}"

    m = _RX_UNTIL.match(q)
    if m:
        try:
            tgt = date.fromisoformat(m.group(1))
            delta = tgt - date.today()
            return f"- days until {tgt.isoformat()}: {delta.days}"
        except Exception:
            return None

    m = _RX_WEEKDAY.match(q)
    if m:
        try:
            d = date.fromisoformat(m.group(1))
            return f"- {d.isoformat()} is a {d.strftime('%A')}"
        except Exception:
            return None

    m = _RX_ADD_TIME.match(q)
    if m:
        dur = _parse_hms(m.group(1))
        hh, mm = map(int, m.group(2).split(":"))
        base = datetime.combine(date.today(), time(hh % 24, mm % 60))
        out = (base + dur).time()
        return f"- {m.group(2)} + {m.group(1).strip()} = {out.strftime('%H:%M:%S')}"

    return None

def try_handle(q: str) -> Optional[str]:
    return _try_timex(q)

def handle(q: str) -> Optional[str]:
    return try_handle(q)

def skill(q: str) -> Optional[str]:
    return try_handle(q)
