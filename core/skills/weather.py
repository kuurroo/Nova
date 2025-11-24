# nova/core/skills/weather.py
from __future__ import annotations
import re
from typing import Optional

# Primary attempt: use the project's web fetch/search summarizer
from .. import web_fetcher as WEB

# Fallback: direct HTTP to wttr.in (simple JSON)
import json, urllib.request, urllib.parse

NAME = "weather"

_RX_QUERY = re.compile(
    r"^\s*(?:what(?:'s| is)\s+)?(?:the\s+)?(weather|forecast)\s+(?:in|for|at)\s+(?P<place>.+?)\s*\??\s*$",
    re.I,
)
_RX_GENERIC = re.compile(r"^\s*(weather|forecast)\b\s*\??\s*$", re.I)

def _build_query(place: str) -> str:
    # Favor sources that show current + short forecast
    return f"current weather and 7-day forecast for {place} temperature precipitation wind humidity"

def _wttr_fetch(place: str, *, timeout: int = 8) -> Optional[str]:
    """
    Fallback: query wttr.in JSON and format concise bullets.
    """
    url = f"https://wttr.in/{urllib.parse.quote(place)}?format=j1"
    req = urllib.request.Request(url, headers={"User-Agent": "nova-weather/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8", "ignore"))
    except Exception:
        return None

    try:
        area = (data.get("nearest_area") or [{}])[0]
        loc = ", ".join(
            x["value"] for x in [
                *(area.get("areaName") or []),
                *(area.get("region") or []),
                *(area.get("country") or []),
            ] if isinstance(x, dict) and x.get("value")
        ).strip(", ")

        cur = (data.get("current_condition") or [{}])[0]
        temp_c = cur.get("temp_C")
        temp_f = cur.get("temp_F")
        feels_c = cur.get("FeelsLikeC")
        feels_f = cur.get("FeelsLikeF")
        wind_kph = cur.get("windspeedKmph")
        wind_mph = cur.get("windspeedMiles")
        hum = cur.get("humidity")
        desc = ((cur.get("weatherDesc") or [{}])[0]).get("value", "")
        precip_mm = cur.get("precipMM")
        # Next hours/day (optional)
        days = data.get("weather") or []
        hi_lo_line = ""
        if days:
            day0 = days[0]
            max_c = day0.get("maxtempC"); min_c = day0.get("mintempC")
            max_f = day0.get("maxtempF"); min_f = day0.get("mintempF")
            hi_lo_line = f"- Today: high {max_c}°C/{max_f}°F, low {min_c}°C/{min_f}°F"

        lines = []
        lines.append(f"- {loc or place}")
        lines.append(f"- Now: {temp_c}°C/{temp_f}°F (feels {feels_c}°C/{feels_f}°F); {desc}")
        if hum: lines.append(f"- Humidity: {hum}%")
        if wind_kph or wind_mph:
            lines.append(f"- Wind: {wind_kph} km/h ({wind_mph} mph)")
        if precip_mm is not None:
            lines.append(f"- Precip: {precip_mm} mm (last hour/forecast window)")
        if hi_lo_line:
            lines.append(hi_lo_line)
        return "\n".join(lines)
    except Exception:
        return None

def try_handle(q: str) -> Optional[str]:
    if not q:
        return None

    m = _RX_QUERY.match(q)
    if m:
        place = m.group("place").strip()

        # 1) Try your web_fetcher summarizer
        try:
            text, meta = WEB.search_and_summarize(_build_query(place), budget_tokens=400)
            if text and text.strip() != "(no web results)":
                return text  # already concise bullets w/ citations
        except Exception:
            pass

        # 2) Fallback to wttr.in (plain JSON)
        text = _wttr_fetch(place)
        if text:
            return text

        # 3) Friendly failure
        return (
            f"- Weather lookup for “{place}” did not return results.\n"
            f"- Tip: try a more specific place (e.g., city, state/country), "
            f"or enable a dedicated weather API later."
        )

    # If the user just typed “weather” w/o a place, let model or other skills handle.
    if _RX_GENERIC.match(q):
        return None

    return None

def handle(q: str) -> Optional[str]:
    return try_handle(q)

def skill(q: str) -> Optional[str]:
    return try_handle(q)
