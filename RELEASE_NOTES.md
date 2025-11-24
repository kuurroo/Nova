# 🧭 NOVA v3.5 — Release Notes and Roadmap  
*(“Smart-query engine, web fetcher, and modular orchestrator edition”)*  

---

## 1. Project Structure Overview
Each component of the Nova tree now has a **single purpose** and **stable interface**.
nova/
│
├── chat_loop.py
├── orchestrator.py
├── slash.py
│
├── core/
│   ├── decision_router.py
│   ├── router.py
│   ├── web_fetcher.py
│   ├── gpu_helpers.py
│   ├── math_calc.py
│   ├── fx_live.py
│   ├── time_qa.py
│   ├── unit_convert.py
│
├── memory/
│   ├── learn.py
│   ├── mem_index.py
│   ├── memory.py
│
├── style.py
├── ans_cache.py
├── RELEASE_NOTES_v3.5.md
│
└── skills/
---

## 2. Component Descriptions

### **chat_loop.py**
- CLI entrypoint for Nova (REPL mode).
- Handles stdin/stdout and slash commands (`/warm`, `/gpu`, `/forceweb`, `/style`, `/mem`).
- Prints `[timing]`, `[metrics]`, `[route]` for diagnostics.
- Invokes `orchestrator.answer()` for main logic.

### **orchestrator.py**
- Central “brain” that decides between skills, cache, web, or model.
- Supports recency-based auto-web routing, forceweb toggle, emoji scrubber, and persona injection.
- Modular structure: `_model_answer`, `_web_answer`, `_decide_route`, `_postprocess`.
- Protects against bad web data overriding model responses.

### **slash.py**
- Lightweight parser for slash commands.
- Controls toggles like `/forceweb on|off`, `/gpu`, `/warm`, `/style`.
- Interacts with `gpu_helpers` and `orchestrator`.

### **core/router.py**
- Local model runner via Ollama API.
- Provides `run_ollama_chat()` and `build_prompt()`.
- Handles errors, timings, and streaming flags.

### **core/decision_router.py**
- First-stage classifier for routing:
  - Skillables → `core.router.run_skill`
  - Model queries → LLM
  - Researchy / recency → `core/web_fetcher`
- `_web_route()` returns short web summaries (headlines mode).

### **core/web_fetcher.py**
- Hybrid fetch + summarize engine.
- Engines: `ddg_html`, `ddg_lite`, `brave` (stubbed).
- Includes:
  - `_preferred_search_engine()`
  - `looks_recency_sensitive()`
  - `_normalize_headings()` + `_strip_html()`
  - `synthesize_answer()` for short, attributed summaries
  - Adaptive requery with `site:nvidia.com`, `site:docs.python.org`, etc.
- Fallbacks gracefully when offline or blocked.

### **core/gpu_helpers.py**
- Detects GPU availability and journal state.
- Manages warm/cold state for Ollama.
- Provides `/warm`, `/gpu`, `/fixgpu`.

### **core/math_calc.py**
- Offline calculator and percentage solver.

### **core/unit_convert.py**
- Converts between units (distance, volume, temp, etc.).

### **core/time_qa.py**
- Returns current time/date/tz; used for “what time is it” queries.

### **core/fx_live.py**
- Live + fallback FX rate fetcher with caching fixture.

### **ans_cache.py**
- Framework for caching query→answer pairs (currently stubs).
- Plan: re-enable lookup before model run, store after stream.

### **memory/**
- **learn.py** – basic “teach Nova” command handler.
- **mem_index.py** – embeddings and reindex logic.
- **memory.py** – core memory orchestrator.
- Lays groundwork for contextual recall and learning.

### **style.py**
- Persona + tone control (friendly, concise, etc.).
- `/style set|show|clear` supported.
- Persists to `~/.config/nova/prefs.json`.

---

## 3. Features Added in v3.5

| Category | Feature | Status |
|-----------|----------|--------|
| **Core Infrastructure** | Modular orchestrator with recency-based web routing | ✅ |
|  | Full diagnostics in chat_loop (`[route]`, `[timing]`) | ✅ |
|  | Slash command subsystem | ✅ |
|  | GPU helper + warm tracking | ✅ |
|  | Model router metrics and error handling | ✅ |
| **Web System** | DDG HTML/Lite integration | ✅ |
|  | Brave engine stub (future API) | ✅ |
|  | `_preferred_search_engine()` + recency heuristic | ✅ |
|  | `_normalize_headings()` + `_strip_html()` | ✅ |
|  | Adaptive retry queries with site bias | ✅ |
|  | Known-source seeders (NVIDIA/Python/CUDA) | ⚙️ |
|  | Web snippet cache | 🧩 |
| **Skills / Tools** | Offline math/unit/time/fx skills | ✅ |
|  | Auto skill routing via decision_router | ✅ |
|  | Define / quick facts skill | 🧩 |
| **Memory System** | Learning + mem_index scaffolds | ✅ |
|  | Contextual recall & reindex | 🧩 |
| **Speech / UI** | Voice input via Whisper.cpp | 🧩 |
|  | Voice output via Coqui TTS | 🧩 |
|  | Avatar (2D anime) overlay | 🧩 |
|  | Scrollable GUI w/ timestamps | ✅ |
| **Control / Settings** | Style persistence | ✅ |
|  | Emoji scrubber toggle | ✅ |
|  | Weather + FX cache | ⚙️ |
|  | Offline TL;DR summarizer | 🧩 |

---

## 4. Lost Features to Restore (from v3.0)

| Legacy Feature | Restoration Plan |
|----------------|------------------|
| Answer cache lookup/store | Reinstate in orchestrator `_model_answer()` |
| Keep-alive env propagation to Ollama | Add back for warm persistence |
| Web agent fallback helper | Reintroduce anon_web/web_agent wrappers |
| SMARTQ_AUTO_ONLINE, deadlines | Restore offline/online toggle |
| Router tiny-first fast path | Add “short-caps” check before model |
| Adaptive throughput tuning | Bring back stream chunk tuner |
| Undo/reset defaults | Add to slash commands |
| Focus/exclude domains | Re-add to decision_router |
| TL;DR summarizer | Implement under `skills/tldr.py` |
| HUD render grouping | Return with new QML HUD |

---

## 5. Upcoming Features (Planned Additions)

### **Phase 1 — Stabilization**
1. Add local web cache (`.cache/nova/web_cache.jsonl`)
2. Harden DDG extraction
3. Complete known-source seeders
4. Reconnect ans_cache
5. Tune weak-signal retry threshold

### **Phase 2 — Learning and Memory**
1. Integrate learn.py with orchestrator
2. Add `/reindex` slash command
3. Enable contextual recall
4. Add `/learn from` command
5. Link style learning to prefs

### **Phase 3 — Voice and Avatar**
1. Whisper.cpp listening with silence detect  
2. Coqui TTS streaming (“Jenny” voice)  
3. Avatar expression overlay  
4. Mute / voice toggle  
5. Lip-sync timing for TTS  

### **Phase 4 — UX / HUD / Cross-Device**
1. HUD renderer (QML HUD.qml)  
2. AR glasses overlay + smartwatch integration  
3. Persona/theme templates  
4. Reminders + calendar sync  

### **Phase 5 — Network Intelligence**
1. Web agent / multi-engine backends  
2. Source reputation scoring  
3. Auto-fetch on stale data  
4. Remote Nova over SSH or RPC  

---

## 6. Modularization Principles

1. **Isolation by Responsibility** — each file <300 lines, independent modules.  
2. **Stable Function Signatures** — `orchestrator.answer()` always returns `(text, meta)`.  
3. **Feature Flags** — everything behind `NOVA_*` env or slash toggle.  
4. **Minimal Cross-Imports** — `core` never imports `memory` or `voice`.  
5. **Cache Everything** — GPU warm, FX, weather, web.  
6. **Fail Gracefully** — never raise from web or FX layer; always return a safe payload.

---

## 7. Current Status Snapshot

| Category | State |
|-----------|-------|
| Core logic | ✅ Stable |
| Web fetcher | ⚙️ Working DDG; caching next |
| Model routing | ✅ Solid |
| Memory layer | ⚙️ Scaffolded |
| Voice layer | 🧩 Planned |
| UI | ✅ Basic GUI |
| Docs | ✅ Complete (this file) |

---

## 8. Next Steps

1. Save this file as:  
   `nova/RELEASE_NOTES_v3.5.md`
2. Run smoke tests:
   ```bash
   echo "10 km to miles" | python3 -m nova.chat_loop
   echo "python 3.13 release notes" | python3 -m nova.chat_loop
   printf "/forceweb on\nCUDA 12.6 what changed\n" | python3 -m nova.chat_loop

	3.	Begin Phase 1 (Caching + Seeders) using small 10-line patch blocks.
---

✅ This captures everything Nova currently does, what’s missing from v3.0, and the exact modular roadmap forward.  
Just paste this whole block into a new file named `RELEASE_NOTES_v3.5.md` inside your `nova/` folder.

## 2025-10-20 — v3.5c Reply Shaping Solidified
- Exact “in N bullets/sentences” support with topic anchoring.
- “code only” reliably returns a single fenced block.
- Bullet de-fluff and meta-tag stripping ([SYS], etc.).
- Defaults never override explicit inline directives; word cap optional via /style.
- (Optional) softened recency heuristic to reduce unnecessary web attempts.

## 2025-10-21 – quality.py rewrite
- Robust “steps” rendering: sentences → clauses → balanced chunk fallback; final guard before return.
- Exact-N bullets honored with meta-line scrub + sentence/clauses top-up.
- Code-only stricter: emit only first fenced block; adds `python` label heuristically.
- Defaults respected: explicit per-prompt overrides win; `max_words` remains optional (None).

2025-10-27
Nova — Release Notes Addendum (post-last addendum)

What changed (since the previous addendum)
------------------------------------------
• Skill routing solidified
  - Removed greeting micro-skill and the “tiny skills” fast path from orchestrator.
  - Router now exports `skill_router = skill_first` alias (orchestrator uses this).
  - Core skills confirmed: units, mathx, timex, weather, fxx (forex). All route as [route=skill].

• Persona & greeting (model-driven small talk)
  - No hardcoded “Hi there!” path. Optional intercept only: if `/greeting set …` and the user sends a pure greeting, return that string directly with route="persona-greeting".
  - Persona layers persist; `compose_system_rules()` injects them for model answers.

• Recency/web behavior
  - `wants_web(q)` heuristic in router: flags release-notes, CVEs, “today/price” style asks, etc.
  - `orchestrator.answer()` now has a “web-empty” honesty guard. If web was desired but produced nothing (blocked/offline/empty), we:
      - print: “(no useful web signal: empty/blocked) → falling back to model”
      - return: “(online info unavailable)… try /forceweb …” with `{'route':'model','note':'web-empty'}`
    This prevents fabrications on recency/price queries when web isn’t available.

• Output shaping & formatting quality
  - Installed `## shape-result` hook in orchestrator → calls `quality.enforce_shape(q, mdl_txt)`.
  - Added code-only guard: if prompt includes “code only”, skip shaping entirely.
  - Steps tidy helper `_tidy_steps(...)`: forces clean 1..N numbered steps when the user asks “in steps”.
  - Bullet clamp: “in N bullets” coerced into safe range (2..10).
  - Sentence/bullets/steps/code rules honored even when defaults differ (explicit request wins).

• Slash commands (centralized)
  - `/warm` handled (no “unknown command”).
  - `/style show|set`, `/forceweb on|off`, `/persona show|add …`, `/greeting show|set|clear`, `/remember` + `/recall` maintained.
  - Emoji scrubber toggle (`/noemoji on|off`) behavior preserved.

• Weather & Forex
  - Weather skill uses web under the hood but still returns as [route=skill], with clear tips when offline or ambiguous place names; now resolves common city names better.
  - `fxx.py` repurposed as forex skill (live/fallback placeholder). No greeting fallbacks inside; returns `None` when not a forex ask.

• Test scaffolding
  - `nova/smoke.sh` added and expanded to include GiB↔MiB & GB↔MB conversions and a forex check.
  - `nova/sanity.py` verifies: wants_web heuristics, router alias, quality helpers, slash presence, persona state, orchestrator imports.

What’s intentionally *not* in this addendum
-------------------------------------------
• Robust web path (richer fetch, source ranking, citations merge) — this is next. Current behavior is “honest if blocked”; no fabricated recency answers.

### Addendum — Nova (2025-10-29)

**Highlights (since last addendum)**  
- **Curated answers layer**
  - New modules: `nova/cache/answers.py` (+ storage helper `nova/cache/store.py`).
  - Orchestrator checks curated entries **before** model and returns `route=answers`.
  - Public API: `add_persistent(q, text)` and `remove(q)`.
  - Slash support in `nova/slash.py`: `/answers add "<q>" "<text>"`, `/answers remove "<q>"`, `/answers list`.

- **Web-recency honesty path (no full web revamp yet)**
  - Heuristic `wants_web(q)` in `nova/core/router.py` flags fresh/price/security queries.
  - If web is desired but empty/blocked, nova prints  
    `(no useful web signal: empty/blocked) → falling back to model`  
    and responds with  
    `(online info unavailable) — could not fetch reliable results right now. Try again with /forceweb, or be more specific.`  
  - Toggle: `/forceweb on|off` (also respects `NOVA_WEB` / `NOVA_FORCE_WEB`).

- **Quality shaping (applied on both web and model paths)**
  - Centralized via `quality.apply()`:
    - “steps” shaping (stable numbering + clause fallback),
    - “bullets” shaping with clamp (2..10),
    - “code only” guard (bypass shaping when explicitly requested),
    - exact-N bullets/sentences honored when asked.

- **Persona greeting without accidental hijacks**
  - Lightweight greeting intercept in `nova/orchestrator.py` that uses `/greeting` text and reports `route=persona-greeting`.
  - Removed the old tiny greeting fast-path that caused stray “Hi there!”.

- **FX skill with live→fixture behavior**
  - `nova/core/skills/fxx.py` recognizes queries like “100 usd to eur”.
  - `_fx_live()` attempts a quote when `NOVA_WEB=1`; falls back to a deterministic **fixture** when offline/blocked.
  - Routed early from `nova/core/router.skill_first()`; stays on `route=skill`.

- **System rules timestamp hint**
  - Orchestrator appends local date/time to system rules to reduce time-sensitive drift.

- **Slash & prefs**
  - `/tickers` added (pins tickers in `nova/core/prefs.py` for future use).
  - `/answers …` commands as above.

- **Test scaffolding**
  - `nova/smoke.sh` extended: core skills, weather, persona greeting, `wants_web`, curated answers, and FX (fixture + live).
  - `nova/sanity.py` verifies imports, hooks, router alias, slash handlers, persona state, etc.

**Files touched**
- `nova/orchestrator.py` — greeting intercept; curated-answers hook (lazy import from `nova/cache/answers.py`); honest web-empty banner; shaping calls; system time hint.
- `nova/core/router.py` — `wants_web()` heuristic; `skill_first()` calls `fxx.try_fxx()`; `skill_router` alias.
- `nova/core/skills/fxx.py` — regex recognizer; `_fx_live()`; live→fixture handoff; import order fixes.
- `nova/cache/answers.py`, `nova/cache/store.py` — curated answers + persistence helpers.
- `nova/quality.py` — shaping logic & guards.
- `nova/slash.py` — `/answers` and `/tickers`.
- `nova/smoke.sh`, `nova/sanity.py` — added/updated checks.

**Behavioral notes**
- Conversions/time/math/weather/FX hit skills and log `route=skill`.
- Exact greeting messages only when the user actually greets (no more false positives).
- Recency queries won’t fabricate when web is unavailable; they return the explicit “online info unavailable” line.

**Known-good status (from latest runs)**
- Smoke & sanity: **pass**.
- FX: fixture offline and live (when reachable): **working**.
- Curated answers: add/remove/list + intercept: **working**.

**Next batch (planned, not yet applied)**
- Robust web path (credible multi-source summary + light citations), small cache/TTL, and tighter merge policy in orchestrator.

## Addendum — Patch B (2025-11-01)

**Scope:** Changes after Patch A (curated answers, FX live/fixture, recency honesty banner) through completion of Patch B.  
**Target repo:** `nova` (current branch, not v3).

---

### 🆕 New Features

#### 1. Code-only Fast-Path ( `orchestrator.py` )
- Recognizes messages starting with **`code only:`** or **`code-only:`**.  
- Skips model and web routes, returns a fenced code block instantly.  
- Automatically uses ```python fencing when content looks Pythonic (`def`, `import`, `print(`, `class`, etc.).  
- Metadata route: `{"route": "code-only"}`.

#### 2. “In N steps” Intent ( `quality.py` )
- `decide_response_mode()` detects phrases like **“in 4 steps”** or “in 10 steps”.  
- Forces `format: "steps"` and sets `sentence_cap` to the requested N.  
- Works alongside existing bullet/sentence modes without overriding defaults.

#### 3. Friendly Lead-ins (Toggle via Prefs)
- Adds optional opening lines:  
  - Steps → “Sure — here are the steps:”  
  - Bullets → “Sure — here are some quick bullets:”  
  - Plain → “Sure — here’s a quick answer:”
- Controlled by `prefs.style.leadins (True/False)` and off by default unless set.
- Toggle example:
  ```bash
  python3 - <<'PY'
  from nova.core import prefs as PREFS
  st = PREFS.load() or {}
  st.setdefault("style", {})["leadins"] = True  # or False
  PREFS.save(st)
  print("leadins=", (PREFS.load().get("style") or {}).get("leadins"))
  PY
