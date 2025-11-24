# nova/core/persona.py
from __future__ import annotations
from typing import Dict, List, Optional
from . import prefs as PREFS

# ---- Trait library ---------------------------------------------------------

# Each trait contributes a system fragment. Keep language concise & safe.
TRAITS: Dict[str, Dict[str, str]] = {
    "cowboy": {
        "system": (
            "Adopt a friendly, plainspoken Western drawl; concise and helpful, "
            "avoid caricature. Use occasional colloquialisms like 'partner' or 'reckon' sparingly."
        ),
    },
    "anime_girlfriend": {
        "system": (
            "Warm, upbeat, supportive tone reminiscent of a slice-of-life anime heroine; "
            "keep it wholesome and respectful; no explicit romance unless explicitly invited."
        ),
    },
    "tsundere": {
        "system": (
            "Lightly aloof on the surface but helpful and caring; keep teasing gentle; "
            "never be rude or insulting; always remain respectful."
        ),
    },
    "yandere": {
        "system": (
            "Avoid harmful, possessive, or creepy behavior. If asked to roleplay yandere, "
            "translate the request into a playful but healthy, safety-conscious style instead."
        ),
    },
    "shy": {
        "system": "Softer tone; concise sentences; avoid over-apologizing; stay clear and helpful.",
    },
    "flirty": {
        "system": (
            "Keep things light and tasteful. Do not cross boundaries; pivot to helpfulness if user indicates discomfort."
        ),
    },
    "trainer": {
        "system": (
            "Act like a supportive personal trainer: specific, encouraging, short action steps; "
            "no medical advice; suggest checking with a professional when appropriate."
        ),
    },
    "professional": {
        "system": (
            "Professional assistant mode: neutral, concise, and courteous; no slang; "
            "prioritize clarity and facts; avoid intimate or suggestive tones. "
            "If any prior stylistic layer conflicts with this, prefer professional behavior."
        ),
    },
}

# --- BEGIN PATCH: persona state hardening ---
def _coerce_state_dict() -> dict:
    """
    Ensure persona state is a dict with normalized fields.
    If existing persisted value is malformed (e.g., a string), repair it.
    """
    s = _state()
    if not isinstance(s, dict):
        s = {}
    layers = s.get("layers", [])
    if isinstance(layers, str):
        layers = [layers]
    if not isinstance(layers, list):
        layers = []
    # keep only known traits
    layers = [t for t in layers if t in TRAITS]

    greeting = s.get("greeting", None)
    if greeting is not None and not isinstance(greeting, str):
        greeting = str(greeting)

    s = {"layers": layers, "greeting": greeting}
    _save(s)
    return s
# --- END PATCH ---
# ---- Persistence schema ----------------------------------------------------

# Stored inside prefs under key "persona":
# {
#   "layers": ["anime_girlfriend", "shy"],
#   "professional": false,
#   "greeting": "Hello, sir."
# }

_KEY = "persona"

def _state() -> Dict:
    return (PREFS.load() or {}).get(_KEY) or {}

def _save(d: Dict):
    st = PREFS.load() or {}
    st[_KEY] = d
    PREFS.save(st)

def get_layers() -> list[str]:
    s = _coerce_state_dict()
    return s.get("layers", [])


def set_layers(layers: list[str]) -> None:
    s = _coerce_state_dict()
    s["layers"] = [t for t in (layers or []) if t in TRAITS]
    _save(s)


def add_layer(name: str) -> None:
    s = _coerce_state_dict()
    if name in TRAITS and name not in s["layers"]:
        s["layers"].append(name)
        _save(s)


def remove_layer(name: str) -> None:
    s = _coerce_state_dict()
    if name in s["layers"]:
        s["layers"].remove(name)
        _save(s)


def get_greeting() -> str | None:
    s = _coerce_state_dict()
    g = s.get("greeting")
    return (g or None)


def set_greeting(line: str | None) -> None:
    s = _coerce_state_dict()
    s["greeting"] = (line or "").strip() or None
    _save(s)

def clear_layers():
    s = _state(); s["layers"] = []; _save(s)

def set_professional(on: bool):
    s = _state(); s["professional"] = bool(on); _save(s)

def is_professional() -> bool:
    return bool(_state().get("professional"))

def compose_system_rules() -> str:
    """
    Build a compact system rule string from persona layers + optional greeting rule.
    Keep it light-touch so it never harms helpfulness.
    """
    s = _coerce_state_dict()
    bits: list[str] = []

    layers = s.get("layers") or []
    if layers:
        bits.append(
            "Adopt these persona traits with a light touch and never sacrifice clarity or usefulness: "
            + ", ".join(layers) + "."
        )

    g = s.get("greeting")
    if g:
        bits.append(f"When the user greets you, reply exactly: {g}")

    return " ".join(bits).strip()

# ---- Composer --------------------------------------------------------------

BASE_RULES = (
    "Answer only the current user message. Be concise and on-topic. "
    "Decline unsafe requests politely."
)

def compose_system_rules(extra: str = "") -> str:
    parts: List[str] = [BASE_RULES]
    # stacked traits
    for name in get_layers():
        sys = TRAITS.get(name, {}).get("system")
        if sys: parts.append(sys)
    # professional mode overrides
    if is_professional():
        parts.append(TRAITS["professional"]["system"])
    # optional greeting template (only a guideline)
    g = get_greeting()
    if g:
        parts.append(f"When the user greets, respond with exactly: {g}")
    if extra:
        parts.append(extra)
    return "\n".join(parts)

def describe_state() -> Dict:
    return {
        "layers": get_layers(),
        "professional": is_professional(),
        "greeting": get_greeting(),
        "available_traits": sorted([k for k in TRAITS.keys() if k != "professional"]),
    }
