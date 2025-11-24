from __future__ import annotations
import json
import urllib.request
# nova/core/skills/forex.py
import os
import re
from typing import Optional, Tuple
from .. import web_fetcher as WEB  # uses your existing web summarizer

_TRUE = {"1","true","yes","on"}

_TICKER_RE = re.compile(r'\b(?:price|quote)\s+([A-Za-z.\-]{1,10})\b', re.I)
_CCY_PAIR_RE = re.compile(r'\b([A-Za-z]{3})\s*/\s*([A-Za-z]{3})\b', re.I)
_CCY_CONV_RE = re.compile(r'\b(\d+(?:\.\d+)?)\s*([A-Za-z]{3})\s+(?:to|in|→|->)\s*([A-Za-z]{3})\b', re.I)
_SIMPLE_PRICE_RE = re.compile(r'\b([A-Za-z.\-]{1,10})\s+(?:price|quote)\b', re.I)
_CCY = r"(?:USD|EUR|JPY|GBP|AUD|CAD|CHF|NZD|CNY|HKD|SEK|NOK|DKK|SGD|MXN|INR|ZAR)"
_PAIR_RE = re.compile(
    rf"\b(?:{_CCY})[\/\s]?(?:{_CCY})\b", re.I
)
_PHRASE_RE = re.compile(
    rf"\b(quote|rate|price)\b.*?\b({_CCY})\b.*?\b(in|to|\/)\b.*?\b({_CCY})\b", re.I
)

def _want_web() -> bool:
    if os.getenv("NOVA_FORCE_WEB","0") in _TRUE: return True
    if os.getenv("NOVA_WEB","0").lower() in _TRUE: return True
    return False

def _summ(q: str) -> Optional[str]:
    try:
        text, meta = WEB.search_and_summarize(q, budget_tokens=600)
        return text.strip() if text and text.strip() else None
    except Exception:
        return None

def _offline_tip(topic: str) -> str:
    return (
        f"- {topic} lookup needs internet.\n"
        f"- Tip: enable /forceweb and ask again.\n"
        f"- Later: configure a market data API in config.py for higher reliability."
    )

def try_fxx(q: str) -> str | None:
    """
    Recognize simple FX phrases like:
      - "100 usd to eur"
      - "250 eur in usd"
      - "1,200 jpy -> usd"

    Behavior:
      * Parse amount + three-letter ISO currency codes.
      * Try live via _fx_live(...) if available; otherwise fall back to _fx_fixture(...).
      * Return a formatted single-line string or None if not an FX query.
    """
    import re

    s = (q or "").strip()
    ql = s.lower()

    # Hard block: don't hijack unrelated queries (weather, time, units, greetings, etc.)
    # Extend as needed.
    if any(tok in ql for tok in ("weather", "forecast", "time", "date", "hello", "hi")):
        return None

    # Only allow valid ISO-like currency codes (prevents catching "GiB → MiB", etc.)
    CODES = {
        "USD","EUR","GBP","JPY","AUD","CAD","CHF","CNY","INR","MXN","BRL","KRW",
        "SEK","NOK","NZD","ZAR","RUB","HKD","SGD","TRY"
    }

    # amount + code + (to|in|->|→) + code
    m = re.search(
        r'(?i)\b([0-9][0-9_,]*(?:\.[0-9]+)?)\s*([A-Z]{3})\s*(?:to|in|->|→)\s*([A-Z]{3})\b',
        s
    )
    if not m:
        return None

    amt_txt, src, dst = m.group(1), m.group(2).upper(), m.group(3).upper()
    if src not in CODES or dst not in CODES:
        return None

    # Normalize amount ("1,200.50" -> 1200.50)
    try:
        amt = float(amt_txt.replace(",", "").replace("_", ""))
    except Exception:
        return None

    if src == dst:
        # Trivial identity; still formatted like others for consistency
        return f"- {amt:.2f} {src} ≈ {amt:.2f} {dst} (fixture)"

    # Try live first; fall back to fixture. Both helpers are expected to
    # return a fully formatted string or a falsy value on failure.
    live = None
    try:
        # _fx_live may not exist in older snapshots; guard for NameError
        live = _fx_live(amt, src, dst)  # type: ignore[name-defined]
    except NameError:
        live = None
    except Exception:
        live = None

    if live:
        return live

    # Fixture fallback (must exist in this module)
    return _fx_fixture(amt, src, dst)

TICKER_RE = re.compile(r'\b([A-Z]{1,5})(?:\s+price|\b)', re.I)
def _tickers_from_query(q: str):
    m=TICKER_RE.findall((q or '').strip()); return list({t.upper() for t in m})

# --- offline FX recognizer (fixture) ---
import re  # keep on its own line
_FXX_RE = re.compile(r"(?i)\b(\d+(?:\.\d+)?)\s*(usd|eur|gbp|jpy)\b\s*(?:to|in|→)\s*(usd|eur|gbp|jpy)\b")
_FX_FIXTURE = {'usd':1.0,'eur':0.92,'gbp':0.79,'jpy':150.0}
def _fx_fixture(amount: float, src: str, dst: str) -> str:
    a = float(amount); s=src.lower(); d=dst.lower()
    rate = _FX_FIXTURE.get(d,1.0)/_FX_FIXTURE.get(s,1.0)
    out = a*rate
    up = {'usd':'USD','eur':'EUR','gbp':'GBP','jpy':'JPY'}
    return f"- {a:.2f} {up.get(s,s.upper())} ≈ {out:.2f} {up.get(d,d.upper())} (fixture)"


def _fx_live(amount: float, src: str, dst: str, timeout: float = 1.5):
    # Try live only if NOVA_WEB=1 (or true/yes). Otherwise None → fixture path.
    if os.getenv('NOVA_WEB', '0').lower() not in ('1','true','yes','on'):
        return None
    try:
        url = f"https://api.frankfurter.app/latest?amount={amount}&from={src.upper()}&to={dst.upper()}"
        with urllib.request.urlopen(url, timeout=timeout) as r:
            data = json.loads(r.read().decode('utf-8', 'ignore') or "{}")
        rates = (data.get('rates') or {})
        val = rates.get(dst.upper())
        if val is None:
            return None
        return f"- {amount:.2f} {src.upper()} ≈ {float(val):.2f} {dst.upper()} (live)"
    except Exception:
        return None
