# nova/slash.py
from __future__ import annotations
import os
import json
import re
from typing import Optional

# Persisted preferences
from .core import prefs as PREFS

# Persona + memory layers (create persona.py and memory.py in nova/core if you haven't yet)
from .core import persona as PERSONA
from .core import memory as MEMORY


# ---------- helpers ----------
def _json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)

def _parse_kv(s: str) -> dict:
    out = {}
    for tok in s.split():
        if "=" in tok:
            k, v = tok.split("=", 1)
            out[k.strip()] = v.strip()
    return out

def _bool_word(s: str) -> Optional[bool]:
    s = (s or "").strip().lower()
    if s in ("1", "true", "on", "yes"):  return True
    if s in ("0", "false", "off", "no"): return False
    return None

def _style_defaults() -> dict:
    st = PREFS.load() or {}
    return st.get("style") or {}


# ---------- /style ----------
def cmd_style(args: str) -> str:
    a = (args or "").strip()
    if not a or a == "show":
        return _json({"style": _style_defaults()})

    if a.startswith("set"):
        kv = _parse_kv(a[3:].strip())
        st = _style_defaults()

        if "verbosity" in kv:
            st["verbosity"] = kv["verbosity"]
        if "format" in kv:
            st["format"] = kv["format"]
        if "max_words" in kv:
            v = kv["max_words"]
            if v.lower() in ("none", "null"):
                st["max_words"] = None
            else:
                try:
                    st["max_words"] = int(v)
                except Exception:
                    pass

        allprefs = PREFS.load() or {}
        allprefs["style"] = st
        PREFS.save(allprefs)
        return _json({"style": st})

    return 'usage: /style show | /style set verbosity=<brief|normal|detailed> format=<plain|bullets|steps|code|mixed> max_words=<int|None>'


# ---------- /forceweb ----------
def cmd_forceweb(args: str) -> str:
    a = (args or "").strip()
    val = _bool_word(a)
    if val is None:
        return 'usage: /forceweb on|off'
    os.environ["NOVA_FORCE_WEB"] = "1" if val else "0"

    prefs = PREFS.load() or {}
    prefs["forceweb"] = bool(val)
    PREFS.save(prefs)
    return f'forceweb: {"ON" if val else "OFF"}'


# ---------- /noemoji ----------
def cmd_noemoji(args: str) -> str:
    a = (args or "").strip()
    val = _bool_word(a)
    if val is None:
        return 'usage: /noemoji on|off'
    os.environ["NOVA_NOEMOJI"] = "1" if val else "0"

    prefs = PREFS.load() or {}
    prefs["noemoji"] = bool(val)
    PREFS.save(prefs)
    return f'noemoji: {"ON" if val else "OFF"}'


# ---------- /persona ----------
def cmd_persona(args: str) -> str:
    a = (args or "").strip().split()
    if not a or a[0] == "show":
        return _json({"layers": PERSONA.get_layers(), "greeting": PERSONA.get_greeting()})
    if a[0] == "add" and len(a) >= 2:
        PERSONA.add_layer(a[1])
        return _json({"layers": PERSONA.get_layers()})
    if a[0] == "remove" and len(a) >= 2:
        PERSONA.remove_layer(a[1])
        return _json({"layers": PERSONA.get_layers()})
    if a[0] == "clear":
        PERSONA.set_layers([])
        return _json({"layers": PERSONA.get_layers()})
    return 'usage: /persona show|add <trait>|remove <trait>|clear'

# ---------- /greeting ----------
def cmd_greeting(args: str) -> str:
    a = (args or "").strip()
    if not a or a == "show":
        return _json({"greeting": PERSONA.get_greeting()})
    if a.startswith("set "):
        PERSONA.set_greeting(a[4:].strip())
        return _json({"greeting": PERSONA.get_greeting()})
    if a == "clear":
        PERSONA.set_greeting(None)
        return _json({"greeting": None})
    return 'usage: /greeting show|set <text>|clear'


# ---------- memory: /remember, /recall, /forget ----------
def cmd_remember(args: str) -> str:
    a = (args or "").strip()
    if not a:
        return 'usage: /remember <text> [tag=mytag]'
    tag = None
    if "tag=" in a:
        left, right = a.split("tag=", 1)
        a = left.strip()
        tag = (right.strip() or None)
    rec = MEMORY.remember(a, tag=tag)
    return _json({"ok": True, "saved": rec})

def cmd_recall(args: str) -> str:
    a = (args or "").strip()
    tag = None; q = None; last = None
    if a:
        for tok in a.split():
            if tok.startswith("tag="):
                tag = tok.split("=", 1)[1]
            elif tok.startswith("last="):
                try:
                    last = int(tok.split("=", 1)[1])
                except Exception:
                    last = None
            else:
                q = f"{q} {tok}".strip() if q else tok
    items = MEMORY.recall(q=q, tag=tag, last=last)
    return _json({"items": items})

def cmd_forget(args: str) -> str:
    a = (args or "").strip()
    if not a:
        return 'usage: /forget <id>|all'
    removed = MEMORY.forget(a)
    return _json({"removed": removed})


# ---------- dispatcher ----------
def try_handle(line: str) -> Optional[str]:
    """
    If `line` is a slash command, return a response string.
    If unknown, return None so chat_loop can handle other fallbacks (e.g., /warm).
    If not a slash command, return None.
    """
    s = (line or "").strip()
    if not s.startswith("/"):
        return None

    if s.startswith("/style"):
        args = (s.split(" ", 1)[1:] or ["show"])[0].strip()
        return cmd_style(args)

    if s.startswith("/forceweb"):
        args = (s.split(" ", 1)[1:] or [""])[0].strip()
        return cmd_forceweb(args)

    if s.startswith("/noemoji"):
        args = (s.split(" ", 1)[1:] or [""])[0].strip()
        return cmd_noemoji(args)

    if s.startswith("/persona"):
        args = (s.split(" ", 1)[1:] or ["show"])[0].strip()
        return cmd_persona(args)

    if s.startswith("/answers"): return cmd_answers(args)
    if s.startswith("/greeting"):
        return cmd_greeting(args)
    if s.startswith("/tickers"):
        return cmd_tickers(args)
        args = (s.split(" ", 1)[1:] or ["show"])[0].strip()
        return cmd_greeting(args)

    if s.startswith("/remember"):
        args = (s.split(" ", 1)[1:] or [""])[0]
        return cmd_remember(args)

    if s.startswith("/recall"):
        args = (s.split(" ", 1)[1:] or [""])[0]
        return cmd_recall(args)

    if s.startswith("/forget"):
        args = (s.split(" ", 1)[1:] or [""])[0]
        return cmd_forget(args)

    # unknown → let chat_loop try other fallbacks (like /warm)
    return None

# ---------- /tickers ----------
def cmd_tickers(args: str) -> str:
    from .core import prefs as PREFS
    a=(args or '').strip()
    if a.startswith('pin'):
        items=[t for t in re.split(r'[\s,]+', a[3:].strip()) if t]
        return _json({'pinned': PREFS.pin_tickers(items)})
    if a.startswith('show'):
        return _json({'pinned': PREFS.get_pinned_tickers()})
    if a.startswith('clear'):
        return _json({'pinned': PREFS.clear_tickers()})
    return 'usage: /tickers pin AAPL,TSLA | show | clear'

# ---------- /answers ----------
def cmd_answers(args: str) -> str:
    from .cache import answers as ANSW
    a=(args or '').strip()
    if a.startswith('add '):
        try:
            k,v = a[4:].split('|',1)
            ANSW.add_persistent(k.strip(), v.strip()); return '{"ok":true,"action":"add"}'
        except Exception:
            return 'usage: /answers add <question>|<answer>'
    if a.startswith('rm '):
        return '{"removed":%s}' % (ANSWER.remove(a[3:].strip()))
    return 'usage: /answers add <q>|<a>  |  /answers rm <q>'

