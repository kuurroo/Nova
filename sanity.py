# Run with: python3 -m nova.sanity
import sys, importlib, json

def ok(msg): print("[OK]", msg)
def no(msg): 
    print("[FAIL]", msg)
    sys.exit(1)

# 1) wants_web heuristics
router = importlib.import_module("nova.core.router")
cases = [
    ("NVIDIA driver release notes 2025", True),
    ("CVE-2025-1234 details", True),
    ("price today for RTX 4090", True),
    ("explain heapsort", False),
]
for q, expect in cases:
    got = router.wants_web(q)
    if got != expect:
        no(f"wants_web({q!r}) == {got}, expected {expect}")
ok("wants_web heuristics")

# 2) router alias (orchestrator expects this)
if not hasattr(router, "skill_router"):
    no("router.skill_router alias missing (export skill_first as skill_router)")
ok("router.skill_router alias present")

# 3) quality helpers exist
quality = importlib.import_module("nova.quality")
for name in ("_split_sentences","BULLET_N_RE"):
    if not hasattr(quality, name):
        no(f"quality missing: {name}")
ok("quality helpers present")

# 4) slash handlers present
slash = importlib.import_module("nova.slash")
for n in ("cmd_persona","cmd_greeting","cmd_remember"):
    if not hasattr(slash, n):
        no(f"slash missing: {n}")
ok("slash handlers present")

# 5) persona state shape
persona = importlib.import_module("nova.core.persona")
state = persona._state()
if not isinstance(state, dict) or "layers" not in state or "greeting" not in state:
    no("persona state malformed (expect dict with 'layers', 'greeting')")
ok("persona state shape")

# 6) orchestrator optional greeting regex presence (not mandatory, just informative)
orch = importlib.import_module("nova.orchestrator")
print(json.dumps({"_GREETING_RE_present": hasattr(orch, "_GREETING_RE")}))
ok("orchestrator imports")

print("All sanity checks passed.")
