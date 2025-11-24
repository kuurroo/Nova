#!/usr/bin/env bash
set -euo pipefail

# Ensure we run from the repo root no matter where you call this from.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

pass(){ printf "PASS   %s\n" "$1"; }
note(){ printf "--     %s\n" "$1"; }

echo "==> 0) Clean bytecode & compile"
find nova -name '__pycache__' -type d -exec rm -rf {} + >/dev/null 2>&1 || true
python3 -m py_compile nova/*.py nova/core/*.py nova/core/skills/*.py && pass "syntax OK"

# Default web knobs (allowed but not forced)
export NOVA_WEB="${NOVA_WEB:-1}"
export NOVA_FORCE_WEB="${NOVA_FORCE_WEB:-0}"

echo "==> 1) /style show / set / show"
printf "/style show\n" | python3 -m nova.chat_loop
printf "/style set verbosity=brief format=bullets max_words=None\n" | python3 -m nova.chat_loop
printf "/style show\n" | python3 -m nova.chat_loop

echo "==> 2) core skills happy paths (should all be route=skill)
python3 -m nova.chat_loop <<<"1 GiB to MiB"
python3 -m nova.chat_loop <<<"1 GB to MB"
"
python3 -m nova.chat_loop <<<"10 km to miles"
python3 -m nova.chat_loop <<<"2 hours in minutes"
python3 -m nova.chat_loop <<<"32 F to C"
python3 -m nova.chat_loop <<<"2+2"
python3 -m nova.chat_loop <<<"what day is 2025-12-25"
python3 -m nova.chat_loop <<<"add 2h 15m to 13:20"

echo "==> 3) weather skill"
python3 -m nova.chat_loop <<<"weather in San Diego"

echo "==> 4) bullets / steps / code-only / sentence-cap"
echo "Explain binary search in 3 bullets" | python3 -m nova.chat_loop
echo "Explain Dijkstra in steps" | python3 -m nova.chat_loop
echo "Give a Python function to reverse a string; code only" | python3 -m nova.chat_loop
echo "Explain quicksort in 2 sentences" | python3 -m nova.chat_loop

echo "==> 5) persona + greeting (model path)"
printf "/persona add anime_girlfriend\n" | python3 -m nova.chat_loop
printf "/greeting set Hello, sir.\n" | python3 -m nova.chat_loop
python3 -m nova.chat_loop <<<"hi"

echo "==> 6) wants_web heuristics (expect web-interest for recency/price)"
python3 - <<'PY'
from nova.core.router import wants_web
for t in [
  "NVIDIA driver release notes 2025",
  "CVE-2025-1234 details",
  "price today for RTX 4090",
  "explain heapsort",
]:
    print(f"{t!r} -> wants_web={wants_web(t)}")
PY

echo "==> 7) model-only generic ask (no web)"
python3 -m nova.chat_loop <<<"explain heapsort"

echo "==> 8) force web toggle sanity"
printf "/forceweb on\nexplain heapsort\n" | python3 -m nova.chat_loop
printf "/forceweb off\n" | python3 -m nova.chat_loop

echo "All smoke commands executed."

echo "==> 9) forex"
python3 -m nova.chat_loop <<<"100 usd to eur"

echo "==> curated answers layer"
python3 - <<'PY2'
from nova.cache import answers as ANSW
ANSW.add_persistent("what is nova?", "Nova is your local-first assistant — short curated answer.")
print("[seeded curated entry]")
PY2
python3 -m nova.chat_loop <<<"what is nova?"


echo "==> 9b) forex route guard"
out="$(python3 -m nova.chat_loop <<<"100 usd to eur")"
echo "$out"
echo "$out" | grep -q "\[metrics\] route=skill" && echo "PASS   fx via skill" || echo "FAIL   fx did not route to skill"
echo "==> 10) forex offline fixture"
unset NOVA_WEB NOVA_FORCE_WEB
python3 -m nova.chat_loop <<<"100 usd to eur"

echo "==> 11) forex live (if reachable)"
export NOVA_WEB=1 NOVA_FORCE_WEB=0
python3 -m nova.chat_loop <<<"100 usd to eur"
unset NOVA_WEB NOVA_FORCE_WEB

echo "==> code-only + steps shaping"
python3 -m nova.chat_loop <<<"code only: print('hi')"
python3 -m nova.chat_loop <<<"Explain Dijkstra in 4 steps"
