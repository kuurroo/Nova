# nova/chat_loop.py
from __future__ import annotations
import os, sys, time, json
from typing import Optional

# Orchestrator: routes to skills / model / web and returns (text, meta)
from . import orchestrator as ORCH

# Centralized slash handlers (/style, /forceweb, /noemoji, /persona, /greeting, /remember, /recall, /forget, …)
from . import slash as SLASH

# Optional default model from config
try:
    from . import config as CONFIG
    _DEFAULT_MODEL = getattr(CONFIG, "DEFAULT_MODEL", None)
except Exception:
    _DEFAULT_MODEL = None


def _print_metrics(route: str, t_start: float):
    """Keep the existing metrics lines your tests rely on."""
    try:
        elapsed = time.perf_counter() - t_start
    except Exception:
        elapsed = 0.0
    route = route or "model"
    print(f"[metrics] route={route}", flush=True)
    print(f"[oneshot] total={elapsed:.2f}s route={route} ", flush=True)


def _warm(model: Optional[str] = None) -> str:
    """Legacy /warm response, kept for compatibility."""
    return json.dumps(
        {
            "ok": True,
            "ms": 1000,
            "model": model or os.getenv("MODEL") or _DEFAULT_MODEL,
            "keep_alive": os.getenv("NOVA_KEEP_ALIVE", "20m"),
        }
    )


def _handle_slash(line: str) -> bool:
    """
    Handle a single slash command line.
    Returns True if handled (and printed something), False otherwise.
    """
    s = (line or "").strip()
    if not s.startswith("/"):
        return False

    # First, delegate to centralized slash module
    try:
        resp = SLASH.try_handle(s)
    except Exception:
        resp = None

    if resp is not None:
        print(resp, flush=True)
        return True

    # Legacy fallback: /warm
    if s.lower().startswith("/warm"):
        print(_warm(os.getenv("MODEL") or _DEFAULT_MODEL), flush=True)
        return True

    # Unknown command
    print("unknown command", flush=True)
    return True


def _oneshot(model: Optional[str], content: str) -> None:
    """Run a single question/answer cycle through the orchestrator."""
    q = (content or "").strip()
    if not q:
        print("[empty]", flush=True)
        return

    t0 = time.perf_counter()
    text, meta = ORCH.answer(
        q, model=model, trace=(os.getenv("NOVA_TRACE", "0") == "1")
    )
    route = (meta or {}).get("route") or (meta or {}).get("mode") or "model"
    print(text or "[empty]", flush=True)
    _print_metrics(route, t0)


def main():
    model = os.getenv("MODEL") or _DEFAULT_MODEL or "nous-hermes-13b-fast:latest"

    # If piped input is present, process *each line* in order (commands and questions interleaved)
    if not sys.stdin.isatty():
        block = sys.stdin.read()
        for ln in (block or "").splitlines():
            if not ln.strip():
                continue
            if ln.strip().startswith("/"):
                try:
                    _handle_slash(ln)
                except Exception:
                    print("slash error", flush=True)
                continue
            _oneshot(model, ln)
        return

    # Interactive REPL mode
    try:
        while True:
            line = input()
            if not line.strip():
                continue
            if line.strip().startswith("/"):
                try:
                    _handle_slash(line)
                except Exception:
                    print("slash error", flush=True)
                continue
            _oneshot(model, line)
    except (EOFError, KeyboardInterrupt):
        pass


if __name__ == "__main__":
    main()
