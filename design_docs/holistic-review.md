# RoundTable 4.1 — Holistic Architecture Review

> **Status:** Internal working doc. **Gitignored — do not commit.**
> **Date:** 2026-06-21
> **Method:** Multi-agent audit (17 agents) across every subsystem + OSS-landscape research, then three
> independent synthesis passes and an adversarial completeness check. Load-bearing claims re-verified
> against source by hand (see *Verification notes* at the end — several audit claims were corrected).

---

## Executive summary

The bones are more real than the docs admit, and the OSS instincts are mostly right: you *bought* the
frameworks (Socket.IO, FastAPI, LangGraph, Zustand, Firebase, Pydantic, SQLAlchemy) and only *built* the
genuinely app-specific parts. But the project is at roughly **20–25% of the stated promise** ("a fully
playable Tomb of the Serpent Kings with all D&D mechanics, spells, actions, scenes, and events, played
with an AI DM and AI + human companions"), and the missing ~75% is gated by **infrastructure, not
content**. The instinct to "encode the rest of the module next" is the single most expensive wrong move:
the engine, persistence, and broadcast layers underneath can't yet express traps, saves, hidden
information, AoE, or atomic multi-entity effects. Harden the foundation, make rules resolution
data-driven, *then* the module becomes a content-authoring task instead of an open-ended pile of bespoke
Python.

---

## Q1 — Are you leveraging open-source standards? (And: should you have built your own chat?)

**Mostly yes.** The consistent pattern: you pick the right *transport/framework* OSS and reinvent the
*schema / coordination / rules-math* layer — often duplicating logic across the Python/TS boundary.

### Scorecard

| Layer | What you use | Verdict |
|---|---|---|
| API / realtime transport | FastAPI, python-socketio (rooms by campaign) | ✅ Correct |
| State delta format | `jsonpatch` + `fast-json-patch` (RFC 6902) | ✅ Format correct / ⚠️ full-blob diffing strategy is the weak part |
| Client state | Zustand | ✅ Correct |
| Agent orchestration | LangGraph + LangChain | ✅ Correct — keep it |
| LLM providers | langchain-google-genai / -openai (reused for OpenRouter + local Ollama) | ✅ Clean dispatch |
| Auth / validation / ORM | Firebase, Pydantic v2, SQLAlchemy 2 + asyncpg | ✅ Correct |
| Turn serialization | Postgres advisory locks | ✅ Strongest piece of the sync layer |
| Memory retrieval | Postgres FTS (deferred pgvector) | ✅ Good judgment, not a gap |
| SRD content data | Hand-authored JSON in `backend/json_data/` | ❌ Reinvented — clearest "adopt OSS now" win |
| Grid math + BFS | Hand-rolled twice (`gridMath.ts` + `pathfinding_service.py`) | ❌ Reinvented & duplicated |
| AC / point-buy math | Hand-rolled ~3× across FE/BE | ❌ Same disease across the language boundary |
| Migrations | Alembic scaffolded but **inert**; real path is ad-hoc `ALTER TABLE` in `init_db.py` | ❌ Ambiguous; `schema.py`/`schema.sql` have drifted |
| Presence / DM-busy lock | In-process module dicts | ❌ Should be Redis; breaks past one worker |
| Vector memory | Claimed (ChromaDB in `architecture.md`) but absent from code & requirements | 👻 Phantom — delete the claim |

### Should you have built your own chat system?

**Yes — keep it. Do not buy Stream / SendBird / Matrix.** What you call "chat" isn't a messaging
surface; it's the game's **command bus + AI-orchestration layer + the LLM's conversational memory**, fused
together (`backend/app/socket/handlers/chat.py`): it parses `@move`/`@attack`/`@dm`, wakes AI companions
via `@mention`, enforces the `dm_busy` lock, and feeds the last N rows into the prompt as LangChain
messages. A managed chat SaaS is MAU-priced, gives you channels/reactions/moderation you don't need, and
would force you to intercept its pipe to extract commands and mirror everything back into your own DB
anyway. The transport you actually need is Socket.IO rooms — which you already use. **The transport was
bought; only the game logic was built. That's correct.**

What you got wrong is the *commodity* half — all in the schema, not the transport:

1. **No persisted message-kind.** Type is inferred from `sender_id` + a wire-only `message_type` that's
   never saved; the `is_tool_output` column exists and is never read/written.
2. **Two transports, opposite persistence.** `chat_message` is saved; `system_message` (moves, equips,
   errors) is ephemeral — so after refresh the combat narrative has holes.
3. **Naive-local-time ordering, no sequence; no server idempotency; pagination built but unused.**
4. **The LLM-context filter matches on UI error strings** instead of a kind enum.

The fix is a **typed event log**, not a vendor.

### Other build-vs-buy calls

- **SRD data → ADOPT NOW** (one-time importer from `5e-bits/5e-database`, CC-BY-4.0). *Gated by the
  proficiency/stat-key bugs — fix those first or imported NPCs still mis-resolve.*
- **Rules engine → KEEP IN-HOUSE.** No production-grade, license-clean *Python* 5e engine exists.
- **State-sync → KEEP & HARDEN.** Do NOT adopt Colyseus/Convex/CRDT (Node-only or wrong model for
  server-authoritative turn-based). Redis-back the broadcast cache + wire the existing `version` field.
- **Vector memory → DEFER, then pgvector** (not Chroma; you already run Postgres).
- **Battlemap → KEEP bespoke SVG now, PixiJS later** (when fog-of-war / AoE / image-maps / many tokens land).

---

## Q2 — The gap between the promise and reality

**Where it really is today:** you can log in, join the seeded encounter, and play **one tactical combat
room** — move on a square grid, make weapon attacks, cast ~40 single-target spells, with an AI DM
narrating and AI companions taking deterministic turns. Walk into an adjacent authored room and the
walkable grid drops and no enemies spawn. Traps, scripted events, AoE, reactions, death saves,
XP/leveling, and ~85% of the module don't exist in runnable form. **A polished vertical slice of one
combat room, not a playable module.**

| Pillar | Exists today | Completion |
|---|---|---|
| **Mechanics & spells** | Initiative, to-hit/AC, damage, crits, adv/dis, ~13 conditions, concentration, slots, healing; ~40 of 319 spells. No damage-type resist/vuln/immunity, death saves, reactions, AoE, upcasting, class features. Weapon to-hit omits proficiency. | **~30%** |
| **Actions** | Two booleans (`has_acted`, `has_moved`). Attack/Cast/Move/EndTurn only. No bonus action, reaction, object interaction; Dash/Dodge/Disengage/Help/Hide/Search/Grapple/Shove = none. OAs deal no damage. | **~20%** |
| **Scenes/events of ToSK** | 8 of 52 rooms encoded (Level 1); 1 fully playable. 0 of 11 traps, 0 of 6 set-pieces mechanized. | **~10%** |
| **AI DM + companions + multiplayer** | Best-built pillar: deterministic combat AI, narration, banter, multiplayer sync, thoughtful memory system. But DM is reactive-only (no director/pacing/events), DM game-tools are mock stubs that fabricate stats, companions can't cast, persistent memory shipped OFF. | **~40%** |

**Named spells:** Fire Bolt resolves correctly. **Magic Missile is wrong** — one `3d4+3` auto-hit lump,
not 3 separately-targetable `1d4+1` darts, no upcast (and a test currently *asserts* this wrong behavior:
`test_spell_service.test_magic_missile_resolves_as_auto_hit`). **Shield doesn't exist** — no reaction
system, and the seeder doesn't even grant it.

**ToSK coverage:** ~15% of rooms encoded, ~2% runnable, **0% of traps**, **0% of set-pieces**. Levels 2–3
(rooms 9–52) exist only as prose. Because ToSK is a save-and-trap-driven OSR dungeon, even the encoded
rooms would play as empty boxes with narration.

**Fair to the team:** the in-repo spec (`tosk-poc-build-spec.md`) deliberately scoped a **Level-1
one-combat POC** with death→memory and loot→memory demos — and that target was hit. The gap is between
that POC and the promise *as stated*, not between the POC and its own spec. **Blended: ~20–25% of the
stated promise.**

---

## Q3 — Do the bones support growth? Sequenced plan.

### Verdict per layer

| Layer | Verdict | Why |
|---|---|---|
| Data model / persistence | **NEEDS-REFACTOR** | JSON-blob + drifting shadow columns, no clear source of truth, non-transactional multi-table saves, append-log selected by timestamp |
| Rules engine | **NEEDS-REPLACE (resolution core)** | Hardcoded 4-branch interpreter behind a ~46-spell whitelist; no damage-type pipeline, death saves, AoE, or effect/resource abstraction; dead duplicate in `game_engine/resolvers/` |
| Content pipeline | **OK (authoring) / BLOCKED (reachability)** | Loader lets a designer add rooms/NPCs/items as data — real strength — but traps/events have no data model and the move path drops the grid |
| AI orchestration | **FOUNDATION-OK** | LangGraph + deterministic-Python-combat split is the right architecture; gaps are additive |
| Real-time sync | **NEEDS-REFACTOR** | Full-blob diff per mutation, single broadcast to all clients (fog-of-war structurally impossible), `version` never checked, single-worker only |
| Frontend / battlemap | **OK / one renderer swap later** | Sound architecture; real debts are FE/BE rules duplication and an SVG renderer that will fight fog/AoE |

### The single decision everything hangs on

**Stop hand-rolling resolution and full-state broadcasting. Make state authoritative + transactional,
make rules resolution declarative/data-driven, and make broadcasts per-viewer — THEN encode the module as
data.** Otherwise every trap, save-or-suck monster, and boss spell becomes bespoke Python you'll rewrite
when the engine changes.

### Roadmap (re-sequenced per the adversarial review)

- **Phase 0 — Foundation hardening & truth-telling.** Combat correctness (proficiency on weapon attacks;
  harden `get_mod`); multi-room reachability + the `LocationGeometry` crash; delete confirmed dead code;
  resolve the migration ambiguity; fix the lying docs; tighten CI (vitest + ruff); security (re-enable
  secret scanning, stop caching plaintext keys). *See the separate Phase 0 implementation plan.*
- **Phase 1 — Persistence as a single transactional source of truth.** One transaction per save; one
  source of truth (derive from the JSON blob, stop shadow-column drift); upsert one `game_states` row per
  campaign; harden hydration; normalize inventory shape.
- **Phase 2 — Sync correctness + Redis.** Version-gate patches; `AsyncRedisManager`; move
  presence/`dm_busy`/broadcast-cache to Redis; targeted resync. *Defer per-viewer projection to
  co-sequence with Phase 3.*
- **Phase 3 — Data-driven rules engine.** Typed damage pipeline; declarative effect + duration system;
  saving throws first-class; death saves; real action economy + reaction window; AoE templates; upcast
  scaling; trap-resolution + skill checks; AI casting branch. Co-locate per-viewer projection here.
- **Phase 4 — Content completion.** Data-driven trap/event schema; encode rooms 9–52 + monsters/items;
  XP/leveling loop; quest-state machine; cursed-item/regen/morale via the effect system.
- **Phase 5 — DM "runs the game" + renderer.** Director/proactive layer; replace mock DM tools with real
  `CombatService` wrappers (or make DM narration-only); turn on persistent memory; server-authoritative
  reachability/AC (delete duplicated FE math); PixiJS swap when fog/AoE arrive.

### Do NOT do yet

Colyseus/Nakama/Convex/CRDTs; any chat SaaS; Chroma/pgvector now; preemptive PixiJS; any external Python
rules engine; restructuring LangGraph; horizontal multi-campaign scale before one module plays end-to-end.

---

## Verification notes (code-confirmed; corrects the raw audit)

These were checked by hand against source; some audit claims were wrong or overstated:

- ✅ **Weapon to-hit omits proficiency** — confirmed. `engine.py` computes `hit_mod` from ability mod only
  (`backend/game_engine/engine.py:57-66`, applied at `:80`/`:118`); `proficiency` never appears in
  `engine.py`. Spell attacks/DCs *do* add proficiency (`character_sheet.py:184-204`), so only weapon
  attacks are affected.
- ⚠️ **"Every JSON NPC attacks at +0" — OVERSTATED.** `monsters.json` statblocks use full-name stat keys
  (`"strength": 21`), and `Stats` has `str`→`strength` aliases (`models.py:66`), so `get_mod` resolves for
  shipping content. The *fragility* is real (`character_sheet.py:22` falls back to score 10 → +0 on any key
  it can't match), but the shipping skeletons aren't at +0 — they're just missing proficiency.
- ✅ **`version` bumped but never read** — confirmed. `state_service.py:69` increments it; no occurrence of
  `version` anywhere in `frontend/src`.
- ✅ **`LocationGeometry` crash is real** — `Location` (models.py:172) has no `geometry` field and
  `LocationGeometry` doesn't exist, yet `resolution_move` imports it (`game_service.py:299`) and passes
  `geometry=` (`:308`). Guarded by `if geometry_data:`, which is currently always falsy for ToSK rooms
  (their location data stores `walkable_cells`/`party_locations` directly, not `geometry`), so it hasn't
  fired yet — but it's a live landmine and the move drops `walkable_cells` regardless.
- ✅ **`ConnectionService` and `game_engine/resolvers/` are unreferenced** — confirmed dead.
- ⚠️ **"No CI / vitest not gating" — PARTLY WRONG.** `.github/workflows/ci.yml` exists and runs backend
  `pytest -m "not integration"` plus frontend `tsc`/`eslint`/`vite build`. What's missing: frontend CI
  doesn't run `vitest`, and backend has no lint (ruff/mypy) step.
- ✅ **Plaintext API keys cached** — `_dm_graph_cache` is keyed on `(api_key, model, provider)`
  (`agents/dm_agent.py:14-19`), retaining raw keys in a module dict for process lifetime.
- ℹ️ **`prompts/*.txt` and `db/schema.sql` are unreferenced** — narration prompts are built inline in
  `ai_service.py`; only `dm_rules.py` reads a prompt file. Low-value cleanup; noted, not urgent.

---

## Provenance

Generated by workflow `roundtable-holistic-architecture-review` (run `wf_d5a80dbe-927`): 10 subsystem
audit agents, 3 OSS-research agents, 3 synthesis agents, 1 adversarial critic. One audit agent
(content-pipeline) failed; its ground was covered by the content/module and data-persistence audits.
Full raw output retained in the session transcript.
