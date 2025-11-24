# nova/core/web_fetcher.py
from __future__ import annotations

import os
import re
import time
import json
import html
import urllib.request
import urllib.parse
from typing import List, Tuple, Dict, Optional

# ---------- configuration ----------
UA = os.getenv(
    "NOVA_HTTP_USER_AGENT",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
)
WEB_TIMEOUT_S = int(os.getenv("NOVA_WEB_TIMEOUT", "30"))
WEB_MAXDOCS   = int(os.getenv("NOVA_WEB_MAXDOCS", "6"))

# ---------- tiny utils ----------
def _tlog(tag: str, t0: float):
    if os.getenv("NOVA_TIMINGS", "0") == "1":
        print(f"[web] {tag}={time.perf_counter()-t0:.2f}s", flush=True)

def _http_get(url: str, timeout: int = WEB_TIMEOUT_S) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

def _clean_bytes(b: bytes, max_chars: int = 400_000) -> str:
    """
    Light cleaner:
      - unescape
      - keep basic structure by turning <h1..h3> into newlines
      - drop script/style/noscript
      - strip the rest of tags
      - collapse whitespace
    """
    if not b:
        return ""
    s = b.decode("utf-8", "ignore")
    s = html.unescape(s)

    # keep headings as line breaks (so sectioning survives stripping)
    s = re.sub(r"(?is)<h[1-3][^>]*>", "\n", s)
    s = re.sub(r"(?is)</h[1-3]>", "\n", s)

    # drop non-content blocks
    s = re.sub(r"(?is)<script.*?</script>", " ", s)
    s = re.sub(r"(?is)<style.*?</style>", " ", s)
    s = re.sub(r"(?is)<noscript.*?</noscript>", " ", s)

    # remove all other tags
    s = re.sub(r"(?is)<[^>]+>", " ", s)

    # whitespace tidy
    s = re.sub(r"[ \t\r\f\v]+", " ", s)
    s = re.sub(r" +\n", "\n", s).strip()
    return s[:max_chars]

def _extract_title(text: str) -> str:
    m = re.search(r"(?im)^\s*(.+?)\s*$", (text or "").strip())
    return (m.group(1) if m else "").strip()[:120]

def _join_chars(chunks: List[str], max_chars: int) -> str:
    s = "\n\n".join(chunks)
    return s if len(s) <= max_chars else s[:max_chars]

# ---------- search engines (DuckDuckGo only) ----------
def ddg_html(query: str, k: int = WEB_MAXDOCS) -> List[Tuple[str, str]]:
    base = "https://html.duckduckgo.com/html/"
    q = urllib.parse.quote_plus(query)
    url = f"{base}?q={q}"
    b = _http_get(url)
    s = b.decode("utf-8", "ignore")
    links: List[Tuple[str, str]] = []
    # parse anchors
    for m in re.finditer(r'(?is)<a[^>]+?href="([^"]+)"[^>]*>(.*?)</a>', s):
        href = html.unescape(m.group(1))
        txt  = re.sub(r"(?is)<.*?>", "", m.group(2)).strip()
        if href.startswith("http") and "duckduckgo.com" not in href:
            links.append((txt[:120] or href, href))
            if len(links) >= k:
                break
    # fallback: plain URLs from cleaned text
    if not links:
        cleaned = _clean_bytes(b)
        for m in re.finditer(r"(https?://[^\s\"']+)", cleaned):
            u = m.group(1)
            if "duckduckgo" in u:
                continue
            links.append((u[:80], u))
            if len(links) >= k:
                break
    return links[:k]

def ddg_lite(query: str, k: int = WEB_MAXDOCS) -> List[Tuple[str, str]]:
    base = "https://duckduckgo.com/lite/"
    q = urllib.parse.quote_plus(query)
    url = f"{base}?q={q}"
    b = _http_get(url)
    s = b.decode("utf-8", "ignore")
    links: List[Tuple[str, str]] = []
    for m in re.finditer(r'(?is)<a[^>]+?href="([^"]+)"[^>]*>(.*?)</a>', s):
        href = html.unescape(m.group(1))
        txt  = re.sub(r"(?is)<.*?>", "", m.group(2)).strip()
        if href.startswith("http") and "duckduckgo.com" not in href:
            links.append((txt[:120] or href, href))
            if len(links) >= k:
                break
    return links[:k]

# ---------- recency hints & adaptive requery ----------
_RECENT_HINTS = [
    r"\b(latest|new|today|now|this week|this month|recent|recently|update|updated)\b",
    r"\b(release\s*notes?|changelog|patch\s*notes|what'?s\s*new|version)\b",
    r"\b(price|earnings|schedule|driver|gpu|nvidia|amd|cuda|python)\b",
]

def looks_recency_sensitive(q: str) -> bool:
    s = (q or "").lower()
    return any(re.search(p, s) for p in _RECENT_HINTS)

def adaptive_requery(q: str) -> str:
    """One conservative refinement: site: scope & 'version' hint."""
    s = (q or "").strip()
    low = s.lower()
    if "nvidia" in low and "site:" not in low:
        s += " site:nvidia.com"
    if ("release notes" in low) and "site:" not in low:
        s += " site:github.com OR site:docs.nvidia.com"
    if ("release" in low or "notes" in low) and "version" not in low:
        s += " version"
    return s

# ---------- known-source fastpaths ----------
_KNOWN_FAST = {
    "nvidia linux driver": [
        "https://www.nvidia.com/en-us/drivers/unix/",
        "https://docs.nvidia.com/datacenter/tesla/tesla-release-notes-580-95-05/index.html",
    ],
    "python 3.13 release notes": [
        "https://docs.python.org/3.13/whatsnew/changelog.html",
        "https://docs.python.org/3.13/whatsnew/3.13.html",
    ],
    "cuda releases": [
        "https://docs.nvidia.com/cuda/cuda-toolkit-release-notes/index.html",
    ],
}

def _fastpath_urls(q: str) -> List[str]:
    x = (q or "").lower()
    if "nvidia" in x and "linux" in x and ("driver" in x or "release" in x or "notes" in x):
        return _KNOWN_FAST["nvidia linux driver"]
    if "python" in x and "3.13" in x and ("release" in x or "notes" in x or "what's new" in x):
        return _KNOWN_FAST["python 3.13 release notes"]
    if "cuda" in x and any(w in x for w in ("release", "notes", "what's new", "changelog", "changed")):
        return _KNOWN_FAST["cuda releases"]
    return []

def _fastpath_links(q: str, k: int = WEB_MAXDOCS) -> List[Tuple[str,str]]:
    urls = _fastpath_urls(q)
    if urls:
        print("[web] search=0.00s", flush=True)
        return [(u, u) for u in urls[:k]]
    return []

# ---------- fetch & synth ----------
def fetch_and_clean(url: str) -> str:
    try:
        return _clean_bytes(_http_get(url))
    except Exception:
        return ""

# --- STRICT WEB SYNTH --- replace the whole function in nova/core/web_fetcher.py
def synthesize_answer(
    docs: List[Tuple[str, str]], query: str, *, budget_tokens: int = 800
) -> Tuple[str, Dict]:
    """Summarize using local model. Returns (text, meta).
       STRICT: refuses off-topic extracts; if query has a version (e.g. 12.6),
       require that version to appear in the combined extracts or return (no web results)."""
    from .router import run_ollama_chat

    if not docs:
        return "", {"web_used": False, "links": []}

    # Fetch small extracts per doc
    extracts: List[str] = []
    clean_docs: List[Tuple[str, str]] = []
    for title, url in docs[:WEB_MAXDOCS]:
        txt = fetch_and_clean(url)
        if not txt:
            continue
        clean_docs.append((title, url))
        extracts.append(f"[{title}] {txt[:1200]}")

    if not extracts:
        return "", {"web_used": False, "links": [u for _, u in docs]}

    # Off-topic guard (weak keyword match must pass)
    if not _weak_match_guard(query, extracts):
        return "", {"web_used": False, "links": [u for _, u in clean_docs], "reason": "weak_match"}

    # Version guard (if the query contains X.Y, enforce it appears in extracts)
    m = re.search(r"\b(\d+\.\d+)\b", (query or ""))
    if m:
        ver = m.group(1)
        joined = " ".join(extracts)
        if ver not in joined:
            return "", {"web_used": False, "links": [u for _, u in clean_docs], "reason": "version_not_present"}

    cites = "\n".join(f"[{i+1}] {t} ({u})" for i, (t, u) in enumerate(clean_docs))
    body = _join_chars(extracts, max(400, budget_tokens * 8))

    prompt = (
        "You are a strict, concise researcher.\n"
        "Use ONLY the Extracts. If they don't clearly answer, reply exactly: (no web results)\n"
        "Output: 3-6 short bullets with [#] citations. No fluff.\n\n"
        f"Question: {query}\n\nSources:\n{cites}\n\nExtracts:\n{body}\n"
    )
    text, meta = run_ollama_chat(
        [{"role": "user", "content": prompt}],
        model=os.getenv("MODEL", "nous-hermes-13b-fast:latest"),
        stream=(os.getenv("NOVA_STREAM", "0") == "1"),
    )
    text = (text or "").strip()

    # If the model ignored instructions, force a clean fallback
    if not text or text == "(no web results)":
        return "", {"web_used": False, "links": [u for _, u in clean_docs], "reason": "model_no_result"}

    # Ensure at least one [#] cite (otherwise it's likely hallucinated)
    if not re.search(r"\[\d+\]", text):
        return "", {"web_used": False, "links": [u for _, u in clean_docs], "reason": "no_citations"}

    meta = meta or {}
    meta["web_used"] = True
    meta["links"] = [u for _, u in clean_docs]
    meta["route"] = "web"
    return text, meta

# ---------- internal search orchestration ----------
def _engine_search(query: str, k: int = WEB_MAXDOCS) -> List[Tuple[str,str]]:
    # Try html, then lite (both DDG). We keep it simple & robust.
    links: List[Tuple[str,str]] = []
    try:
        links.extend(ddg_html(query, k=k))
    except Exception:
        pass
    if len(links) < k:
        try:
            need = k - len(links)
            links.extend(ddg_lite(query, k=need))
        except Exception:
            pass
    return links[:k]

# ---------- public API ----------
def search_and_summarize(query: str, *, budget_tokens: int = 800) -> Tuple[str, Dict]:
    t0 = time.perf_counter()

    # 0) known-source fastpath (no engine hits)
    links_pairs = _fastpath_links(query, k=WEB_MAXDOCS)
    if not links_pairs:
        # 1) search (with DDG html→lite)
        links_pairs = _engine_search(query, k=WEB_MAXDOCS)
    _tlog("search", t0)

    # 2) fetch & clean → keep only readable docs
    f0 = time.perf_counter()
    docs: List[Tuple[str, str]] = []
    for title, url in links_pairs[:WEB_MAXDOCS]:
        txt = fetch_and_clean(url)
        if txt:
            docs.append((title or _extract_title(txt) or url, url))
    _tlog("fetch+clean", f0)

    if not docs:
        # Orchestrator will decide about fallbacks/retries
        return "", {"web_used": False, "links": links_pairs}

    # 3) synthesize
    ans, meta = synthesize_answer(docs, query, budget_tokens=budget_tokens)
    if (ans or '').strip() == '(no web results)':
        return '', {'web_used': False, 'links': [u for _,u in docs], 'reason': 'no_useful_extracts'}
    return ans, meta

def search_and_read(query: str, budget_tokens: int = 800, sites=None):
    """Back-compat alias expected by orchestrator."""
    return search_and_summarize(query, budget_tokens=budget_tokens)

def dbg_list_web_symbols() -> Dict:
    return {
        "symbols": sorted([k for k in globals().keys() if not k.startswith("_")]),
        "engines": "ddg_html,ddg_lite",
        "timeout": str(WEB_TIMEOUT_S),
    }


def _weak_match_guard(query: str, texts: list[str]) -> bool:
    q = query.lower(); kws = [w for w in re.findall(r'\w+', q) if len(w)>3][:6]
    if not kws: return True
    hits = sum(any(k in t.lower() for k in kws) for t in texts)
    return hits >= 1
