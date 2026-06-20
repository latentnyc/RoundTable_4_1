# RoundTable Memory & Narrative Architecture

*Lead Architect synthesis — final build spec*

## Thesis

RoundTable's memory spine is **not a RAG bolt-on; it is a write-side discipline.** The deterministic engine already computes every fact worth remembering (kills, defeats, loot rarity, downed-to-zero saves, quest flips, disposition shifts); the existing rolling summary already produces narrative recollection but throws its detail away once it ages out. The correct architecture **captures those deterministic facts and aged-out summaries into a durable, append-only store, then retrieves them as clearly-fenced narrative reference** — never as authoritative state.

We ship a deliberately small first sprint: structured episodic memory, ranked in SQL by salience + recency + full-text keyword, with **no embeddings and no pgvector**. At one-campaign scale a scan over a few thousand rows is sub-10ms, and the team already rejected premature vector RAG. pgvector, lore, relationships, markdown campaigns, and the system-agnostic seam are layered on **only when corpus size or a product feature earns them**. Guardrails (DM persona, combat protocol, conditions, social register) stay always-on and direct-injected; episodic memory and lore are the only legitimate retrieval targets, and they are always labeled *"reference only — the engine owns the numbers."*

## Layered Architecture

```
                         ┌───────────────────────────────────────────────────────┐
                         │  AUTHORITATIVE DETERMINISTIC ENGINE  (source of truth) │
                         │  game_engine/engine.py · combat_service · spell_service │
                         │  condition_service · loot_service · quest_service       │
                         │  → HP, positions, conditions, inventory, currency,      │
                         │    turn_order, quest flags, relationship NUMBERS        │
                         └───────────────┬───────────────────────────┬───────────┘
                                         │ direct call after commit   │ reads live state
                                         │ memory_service.record_event│
                                         ▼                            │
   ┌────────────────────┐   ┌──────────────────────┐                 │
   │ EPISODIC MEMORY     │   │ RELATIONSHIP STATE   │  ← authoritative │
   │ memory_episodes     │   │ relationships table  │    (own table,   │
   │ (append-only facts  │   │ affinity/trust/resp  │     hydrated)    │
   │  + aged summaries)  │   └──────────┬───────────┘                 │
   └─────────┬──────────┘              │                              │
             │                          │ derive tier                  │
   ┌─────────▼──────────┐   ┌───────────▼───────────┐                 │
   │ SEMANTIC / LORE     │   │ REGISTER SELECTOR     │ (pure fn,       │
   │ memory_facts +      │   │ tension×tier→directive│  direct-inject) │
   │ lore_chunks (RAG)   │   └───────────┬───────────┘                 │
   └─────────┬──────────┘               │                             │
             │ retrieve (top-k, fenced)  │                             │
             ▼                           ▼                             ▼
   ┌──────────────────────────────────────────────────────────────────────────┐
   │  CONTEXT ASSEMBLY  (context_builder + ai_service injection)                │
   │  ───────────────────────────────────────────────────────────────────────  │
   │  [always-on guardrails: DM persona, combat protocol, conditions, register] │ ← DIRECT
   │  STORY SO FAR (rolling summary)                          ← existing        │
   │  RELEVANT MEMORIES / LORE (reference only, never state)  ← RETRIEVED       │
   │  ACTIVE QUESTS · OPEN PROMISES                           ← deterministic    │
   │  RELATIONSHIP + SOCIAL REGISTER                          ← deterministic    │
   │  SYSTEM CONTEXT (REFERENCE ONLY): PARTY STATUS / ENEMIES ← LIVE, AUTHORITY  │
   └──────────────────────────────────┬───────────────────────────────────────┘
                                       ▼
                         ┌──────────────────────────────┐
                         │  LLM (BYOK, multi-provider)   │  NARRATES ONLY.
                         │  dm_agent · character_agent    │  No tool writes HP/gold/state.
                         └──────────────────────────────┘
```

**Ordering invariant in the prompt:** durable past → relevant recalls → quest/register → **live authoritative state last, labeled current**. The block that appears last and is labeled "current" wins; everything above it is past-tense reference. This is the single anti-hallucination lever and it reuses the existing `SYSTEM CONTEXT (REFERENCE ONLY)` register the model already understands (`ai_service.py:269`).

**The system-agnostic firewall is a data shape, not a framework.** Memory rows carry a generic `facts` dict (`{damage, hp_after, item_id, rarity}`) — never `dexterity`/`gp`. That generic payload is the entire portability seam; it requires no pub-sub bus to enforce.

---

## Reconciled Decisions

Six analysis dimensions converged on the same spine but conflicted on concrete points. Resolutions, with the critique panel folded in:

### Conflict 1 — One memory table or many?
**ONE unified `memory_episodes` table for Sprint 1**, append-only, distinguished by a `kind` column (`summary|event|death|loot|quest|relationship|reflection`). Deterministic events, relationship beats, and aged summaries are the same fact log with different writers — not separate stores. A second physical table (`memory_facts`) earns its place **only at the reflection sprint**, when the LLM produces *distilled, supersedable* facts. The `relationships` table stays separate because it is **authoritative pairwise state** (numbers the engine mutates), not recollection.

### Conflict 2 — Sprint 1: embeddings or not?
**NO embeddings in Sprint 1.** Salience + recency + full-text keyword + entity-presence SQL only. At hundreds-to-low-thousands of rows per campaign, SQL ranking is sub-10ms; a vector index is premature MVP complexity. Embeddings, pgvector, and BYOK-dimension machinery move to **Sprint 3**, built when lore (a genuinely large semantic corpus) arrives. This is the central staging decision and what keeps Sprint 1 shippable in 1–2 weeks.

### Conflict 3 — Write seam: event bus or direct call?
**Direct call in Sprint 1; promote to an `EventBus` in Sprint 2** (per the over-engineering critique). Memory is the *sole* consumer at Sprint 1 and the three producers (`combat_service`, `loot_service`) can `import memory_service` directly. A pub-sub bus with fan-out, error isolation, and a startup hook earns its place only when multiple independent producers *and* consumers exist — which happens in Sprint 2 (quest, relationship, condition producers; memory + future analytics consumers). Sprint 1 keeps the `GameEvent` Pydantic model as the generic fact-payload type (it *is* the firewall and is cheap), but calls `await memory_service.record_event(...)` directly, wrapped in `try/except` so it fails open. **Error isolation is achieved by the try/except, not by a bus.**

### Conflict 4 — BYOK embedding dimensions (Sprint 3)
**Single unconstrained `vector` column + mandatory `embed_dim` WHERE-filter + per-campaign brute-force cosine** (no ANN index initially). A campaign has exactly one provider at a time (its key), so all its rows share a dimension; the `embed_dim` filter makes mixing 768-dim and 1536-dim vectors structurally impossible. Rejected: zero-padding to 1536 (introduces a silent never-renormalize invariant a contributor will break) and per-dimension partial HNSW indexes (premature; defer to a measured >10k-chunk campaign). Provider switch mid-campaign → old rows excluded by the dim filter (recall degrades, never wrong), backfilled by an explicit `reembed_campaign` job.

### Conflict 5 — Ranking formula
**Weighted SUM of normalized (similarity, importance, recency-decay), NOT a product.** A multiplicative score zeroes out *old-but-relevant* memories — exactly the cross-session callbacks the brief prizes. Default weights `w_sim=0.5, w_imp=0.25, w_rec=0.25`.

**Critical fix (feasibility):** the weighted sum must operate over a candidate **pool that includes high-importance candidates**, not a pool pre-filtered by cosine alone. A pure `ORDER BY embedding <=> :q LIMIT :pool` drops the old-but-relevant memory *before* the importance weight can resurface it. The pool is therefore a **UNION of (top-N by similarity) + (top-M by importance DESC) + (entity-presence matches)**, then re-ranked by weighted sum.

- **Sprint 1 (no embeddings):** the `similarity` slot is `0.6 * normalized_ts_rank(FTS) + 0.4 * entity_overlap_bonus`, where `normalized_ts_rank` is `ts_rank` of the FTS match scaled to 0..1 over the result set, and `entity_overlap_bonus` is `1.0` if any `subject_refs` id intersects the currently-present entity ids, else `0.0`. The pool already comes from salience+FTS, so it is correct by construction.
- **Sprint 3:** cosine swaps into the `similarity` slot; the pool-union fix above prevents the cosine-LIMIT defect.

### Conflict 6 — Markdown campaigns
**Markdown is an authoring FRONT-END that compiles to the exact `games/*.json` shape `campaign_loader` already consumes.** JSON remains a valid runtime input indefinitely. Zero runtime change ships markdown authoring; only a compiler + validator + the lore table are added. A `yaml` stat-fence (deterministic) vs prose (narrative/RAG) split inside each section enforces determinism-first at the authoring layer. Rejected: a bespoke markdown-native runtime (rewrites the verified, fragile hydration path for no benefit).

### Other consolidations
- **Salience ownership:** importance is assigned by the **writer** in Python, never by the retriever or an LLM at write time. (Sprint 4 reflection is a *deliberate, bounded exception* — see Decision #5.)
- **Fail-open:** missing BYOK key, flag off, or absent pgvector → memory no-ops and the engine degrades to *exactly today's behavior*. Memory is strictly additive.
- **pgvector image:** at the embedding sprint, swap `postgres:15-alpine` → `pgvector/pgvector:pg15` (drop-in, same PG15, volume preserved).

---

## Consolidated Data Model (DDL, idempotent `init_db.py` pattern)

All DDL goes inside `backend/db/init_db.py`, guarded by `try/except SQLAlchemyError + logger.warning`, mirroring the existing `ALTER TABLE ... IF NOT EXISTS` block. **Sprint 1 ships entirely without pgvector.**

> **Schema-divergence guard (must honor):** `memory_episodes`, `memory_facts`, `lore_chunks` are created by **raw DDL in `init_db.py` only**. Do **NOT** add them (or any `vector` column) to `schema.py` Core metadata — `metadata.create_all` would race the raw DDL and, post-Sprint-3, fail because the `vector` type loads after `create_all`. The scalar columns may be queried via raw `text()` or a read-only reflected table, never via `metadata.create_all`. The stale `backend/db/schema.sql` (Supabase-era `uuid` PKs, RLS, a phantom `lore_documents vector(1536)`) is **not the live schema**; confirm nothing at startup reads it, then delete it.

### Sprint 1 (NO pgvector) — episodic memory + provider columns + item rarity

```sql
-- ===== EPISODIC MEMORY (Sprint 1) — append-only fact + aged-summary log =====
CREATE TABLE IF NOT EXISTS memory_episodes (
    id            VARCHAR PRIMARY KEY,          -- sha256(campaign_id|kind|source_ref)[:32], idempotent
    campaign_id   VARCHAR NOT NULL REFERENCES campaigns(id),
    kind          VARCHAR NOT NULL DEFAULT 'summary',  -- summary|event|death|loot|quest|relationship|reflection
    content       TEXT    NOT NULL,             -- the narrative line injected into context
    facts         JSONB   NOT NULL DEFAULT '{}',-- verbatim deterministic payload {damage,is_crit,hp_after,item_id,rarity}
    subject_refs  JSONB   NOT NULL DEFAULT '[]',-- [{kind,id,name}] entities this is ABOUT
    witnessed_by  JSONB   NOT NULL DEFAULT '[]',-- entity ids present (answers "what does X remember")
    importance    REAL    NOT NULL DEFAULT 0.5, -- 0..1 salience, assigned by WRITER
    access_count  INTEGER NOT NULL DEFAULT 0,   -- read-reinforcement + cooldown
    last_surfaced_turn INTEGER,                 -- cooldown anchor (see callback mechanism)
    session_no    INTEGER,                       -- for "several sessions ago" recall
    src_from      TIMESTAMPTZ,                  -- aged-summary window start
    src_to        TIMESTAMPTZ,                  -- aged-summary window end
    -- embedding columns added in Sprint 3 via ALTER (NULL until then):
    -- embedding vector, embed_model VARCHAR, embed_dim INTEGER
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_mem_ep_camp_salience
    ON memory_episodes (campaign_id, importance DESC, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_mem_ep_subjects ON memory_episodes USING gin (subject_refs);
CREATE INDEX IF NOT EXISTS ix_mem_ep_fts
    ON memory_episodes USING gin (to_tsvector('english', content));

-- ===== PROVIDER + FLAG COLUMNS (Sprint 1; embed_model reserved for Sprint 3) =====
-- campaigns has api_key+model but NO provider column; provider lives wrongly on profiles.
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS llm_provider VARCHAR DEFAULT 'Gemini';
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS embed_model  VARCHAR;
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS memory_rag_enabled BOOLEAN DEFAULT FALSE;
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS session_no INTEGER NOT NULL DEFAULT 1;

-- ===== ITEM RARITY (Sprint 1 prerequisite for loot salience scaling) =====
-- Verified: loot items have no rarity field; without it loot salience collapses to the 0.2 floor.
ALTER TABLE items ADD COLUMN IF NOT EXISTS rarity VARCHAR DEFAULT 'common';
```

**Session counter (closes the `session_no` gap).** No session concept exists in the schema today. We add `campaigns.session_no` (above), incremented by **one** deterministic call: when `join_campaign` runs after a gap (server restart or first connect of the day, detected by `now() - last_activity_at > 6h`, reusing the existing connect path), `memory_service.bump_session(campaign_id, db)` does `UPDATE campaigns SET session_no = session_no + 1`. Every `record_event` and summary ingest stamps the current `campaigns.session_no` onto the row. This is the entire mechanism for "several sessions ago."

Quest/narrative runtime state rides the **existing** `game_states.state_data` JSON (so it flows over the existing JSON-Patch sync with no new sync path):

```jsonc
"narrative": {
  "quests": { "<quest_id>": { "status": "active", "current_stages": ["stg_eva"], "completed_stages": [] } },
  "revealed_facts": ["fact_eva_lineage"],   // ONLY written by deterministic quest advancement
  "variables": { "fear_level": 25 },
  "promises": [ { "id":"pr_1","to":"npc_blacksmith","text":"retrieve the stolen anvil","made_session":2,"status":"open" } ],
  "recently_surfaced": { "<episode_id>": 142 }  // episode_id -> turn last surfaced (callback cooldown)
}
```

### `source_ref` per writer (closes the idempotency-collision gap)

`id = sha256(f"{campaign_id}|{kind}|{source_ref}")[:32]` with `INSERT ... ON CONFLICT (id) DO NOTHING`. `source_ref` must be **stable and unique per real event** so retries dedup but distinct events don't collide:

| kind | `source_ref` |
|---|---|
| `event`/`death` | `f"{combat_event_seq}:{entity_id}"` — the combat resolution's monotonic event sequence + the affected entity. Two identical "5 damage" lines get distinct seqs. |
| `loot` | `f"take:{vessel_id}:{actor_id}:{','.join(sorted(item_ids))}:{game_state.turn_index}"` |
| `summary` | `f"summary:{src_to.isoformat()}"` — the aged window's end timestamp |
| `relationship`/`quest` (Sprint 2) | `f"{trigger_event_seq}:{from_id}:{to_id}"` / `f"{quest_id}:{stage_id}"` |

The combat resolution path already carries a per-attack ordering; expose it as `combat_event_seq` (a counter on the combat state) so deaths/crits get a monotonic discriminator. This is the feasibility critic's required fix.

### Sprint 3 (pgvector) — embeddings + lore RAG

```sql
-- Run in its OWN engine.begin() block, BEFORE metadata.create_all (extension-before-schema ordering):
CREATE EXTENSION IF NOT EXISTS vector;          -- requires pgvector/pgvector:pg15 image

-- Add embedding columns to the EXISTING episodic table (no new table for episodes):
ALTER TABLE memory_episodes ADD COLUMN IF NOT EXISTS embedding   vector;   -- UNCONSTRAINED dim
ALTER TABLE memory_episodes ADD COLUMN IF NOT EXISTS embed_model VARCHAR;
ALTER TABLE memory_episodes ADD COLUMN IF NOT EXISTS embed_dim   INTEGER;  -- 768|1536, BYOK

-- Lore corpus (markdown-authored worldbook prose), the legitimate large-RAG target:
CREATE TABLE IF NOT EXISTS lore_chunks (
    id            VARCHAR PRIMARY KEY,
    campaign_id   VARCHAR NOT NULL REFERENCES campaigns(id),
    source_id     VARCHAR,                       -- lore_tatyana
    title         VARCHAR,
    content       TEXT NOT NULL,
    tags          TEXT,                          -- JSON array
    gated_by      VARCHAR,                       -- NULL=always; else "quest_id:stage_id" | "fact_id"
    importance    REAL DEFAULT 0.6,
    embedding     vector,
    embed_model   VARCHAR,
    embed_dim     INTEGER,
    created_at    TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_lore_camp ON lore_chunks (campaign_id);
```

**pgvector codec registration (feasibility must-fix).** `db/session.py` creates a bare `create_async_engine` with no connect hook; asyncpg has no encoder for the `vector` OID until `register_vector` runs on each pooled connection. Sprint 3 adds, in `db/session.py`:

```python
from sqlalchemy import event
from pgvector.asyncpg import register_vector

@event.listens_for(engine.sync_engine, "connect")
def _register_vector(dbapi_conn, _):
    dbapi_conn.run_async(register_vector)   # runs against the raw asyncpg connection
```

**The documented primary query path binds the vector as a string literal** (`'[0.1,0.2,...]'::vector`), which needs no codec and works even if codec registration regresses. The codec is an optimization, not a correctness dependency.

**BYOK retrieval query (Sprint 3+), pool-union so importance contributes candidates, dim-scoped so providers never cross-compare:**

```sql
-- Pool = (top-N by cosine) ∪ (top-M by importance) ∪ (entity-presence), all dim-filtered.
WITH sim AS (
  SELECT id, 1 - (embedding <=> :q::vector) AS similarity
  FROM memory_episodes
  WHERE campaign_id = :cid AND embed_dim = :dim AND embedding IS NOT NULL
  ORDER BY embedding <=> :q::vector LIMIT :n
),
imp AS (
  SELECT id, NULL::float AS similarity
  FROM memory_episodes
  WHERE campaign_id = :cid AND importance >= :imp_floor
  ORDER BY importance DESC, created_at DESC LIMIT :m
)
SELECT DISTINCT id FROM (SELECT id FROM sim UNION SELECT id FROM imp) pool;
-- Hydrate the pooled rows, compute weighted sum in Python: w_sim*sim + w_imp*imp + w_rec*decay
```

### Sprint 4 (reflection) — semantic/distilled facts with evolution

```sql
CREATE TABLE IF NOT EXISTS memory_facts (
    id            VARCHAR PRIMARY KEY,
    campaign_id   VARCHAR NOT NULL REFERENCES campaigns(id),
    fact_type     VARCHAR NOT NULL,              -- relationship|lore|promise|trait
    content       TEXT NOT NULL,
    confidence    REAL DEFAULT 0.7,
    importance    REAL DEFAULT 0.6,              -- LLM-scored, clamped (see Decision #5)
    subject_refs  JSONB NOT NULL DEFAULT '[]',
    supersedes    VARCHAR,                       -- relationship evolution: points at replaced fact
    source_episode_ids JSONB NOT NULL DEFAULT '[]',
    valid         BOOLEAN NOT NULL DEFAULT TRUE, -- soft-supersede, never hard-delete
    embedding     vector, embed_model VARCHAR, embed_dim INTEGER,
    created_at    TIMESTAMPTZ DEFAULT now(), updated_at TIMESTAMPTZ DEFAULT now()
);
```

### Relationships (Sprint 2) — AUTHORITATIVE pairwise state, NOT recollection

```sql
CREATE TABLE IF NOT EXISTS relationships (
    id          VARCHAR PRIMARY KEY,
    campaign_id VARCHAR NOT NULL REFERENCES campaigns(id),
    from_id     VARCHAR NOT NULL,               -- NPC/companion/char id
    to_id       VARCHAR NOT NULL,               -- char id OR '__party__' sentinel
    affinity    INTEGER NOT NULL DEFAULT 0,     -- -100..100
    trust       INTEGER NOT NULL DEFAULT 0,
    respect     INTEGER NOT NULL DEFAULT 0,
    tier        VARCHAR NOT NULL DEFAULT 'neutral',  -- derived label (hostile|wary|neutral|warm|devoted)
    history     TEXT    NOT NULL DEFAULT '[]',  -- capped JSON [{reason,delta,tick}]
    updated_at  TIMESTAMPTZ DEFAULT now(),
    UNIQUE (campaign_id, from_id, to_id)
);
```

---

## Cross-Cutting Mechanisms (specified once, referenced by sprints)

### `record_event` opens its own session (feasibility must-fix)
`memory_service.record_event` must **not** borrow the caller's `AsyncSession` (it may already be committed/closed). It opens its own `AsyncSessionLocal()` (the pattern `create_test_campaign` uses at startup), runs the idempotent INSERT, and commits independently. It is `await`ed inline after the caller's state commit — the writes are tiny synchronous INSERTs (not embeds), so no `create_task` and no lifecycle owner is needed in Sprint 1.

### `witnessed_by` population (closes two gaps)
- **`combat_service` events:** the full combatant id list is in scope; snapshot it. For `death`, build the fact snapshot dict from the in-memory entity **before** `_handle_entity_death` deletes the row, and call `record_event` **after** the state commit (so the new session need not see uncommitted deletion context).
- **`loot_service.take_items`:** verified — only `actor` and `vessel` are in scope, **not the full party**. Fix: pass `game_state.party` ids (already loaded at `take_items` line 297) as `witnessed_by`; `subject_refs` = the actor + the item ids. Without this the entity-presence signal would be dead for loot.
- **Aged summaries (`kind=summary`):** a summary spans many turns with changing presence, so per-turn presence is meaningless. Set `witnessed_by = []` and `subject_refs` = the **union of party member ids over the window** (cheap: the party is stable within a session). Retrieval treats empty `witnessed_by` as "ambient" — eligible on recency+FTS+importance, never excluded by the presence gate. This makes summary episodes reachable.

### Callback surfacing + cooldown (closes the marquee-feature gap)
Sprint 1 ships **raw retrieval into the fenced block** — its Definition of Done claims only that. The **narrative callback** (presence-gate + cooldown) is a thin, fully-specified layer that also ships in Sprint 1 (it is cheap and is the marquee feature):
- **Presence gate:** an `event`/`death`/`loot` episode is eligible only if its `subject_refs` ∩ currently-present entity ids ≠ ∅. `summary` episodes are ambient (always eligible).
- **Cooldown:** before injecting, drop any episode whose id is in `game_states.narrative.recently_surfaced` with `turn_last_surfaced > current_turn - N` (default `N=12`). On inject, write `recently_surfaced[id] = current_turn` and `UPDATE memory_episodes SET access_count = access_count + 1, last_surfaced_turn = :turn`.
- **Budget:** top-k=6 after gating+cooldown, ~800-token cap, deduped against the working window (see below).

### Dedup vs working window (closes the underspecified-dedup gap)
The kept last-10 messages are injected verbatim. To avoid re-paying tokens for a memory that overlaps a still-in-window message, exclude any episode whose `src_to` (summary) or `created_at` (event) is **newer than `window_start`** = `created_at` of the oldest of the last-10 messages. Anything inside the working window is already present verbatim; only older episodes are eligible for retrieval.

### DM and companion injection (closes the path-coverage gap)
Sprint 1 injects `RELEVANT MEMORIES` into **both** `generate_chat_response` (DM, `ai_service.py`) **and** `generate_character_response` (AI party, `ai_service.py:302`). Companions must remember — the brief's "evolving relationships/banter" requires it. The fenced block and retrieval call are identical; only the presence-gate's "currently-present entities" set differs (for a companion, retrieval may bias toward that companion's `witnessed_by` via the `entity_overlap_bonus`).

### Observability (should-fix, adopted)
`retrieve()` logs the chosen episode ids + their (sim, imp, rec, total) sub-scores to the **existing `DebugLog` table** (`schema.py:58`) each turn. Near-zero cost, reuses existing infra, and lets a GM see whether the new ~800-token block earns its place before weights are tuned.

---

## Staged Roadmap

### SPRINT 1 — "The DM remembers salient events across sessions" (shippable, 1–2 weeks)

**Goal.** Replace the single lossy rolling summary with durable, append-only episodic memory retrieved by salience+recency+keyword, fenced as reference-only, with a minimal presence-gated callback. Closes the roadmap line "remember actions from several sessions ago." **No embeddings, no pgvector, no event bus, no new infra.**

**Scope IN:**
- `memory_episodes` table + indexes (incl. FTS) + `campaigns` provider/flag/`session_no` columns + `items.rarity` column, via idempotent `init_db.py` DDL.
- `app/events/game_event.py` — the `GameEvent` Pydantic model **only** (the generic fact-payload firewall type). **No bus.**
- `app/services/memory_service.py`:
  - `record_event(campaign_id, kind, content, facts, subject_refs, witnessed_by, importance)` — opens its own session, idempotent sha256-id INSERT with per-kind `source_ref`.
  - `ingest_episode_from_summary(...)` — the ~2-line hook into the existing summarization branch (`ai_service.py:261`); stamps `src_from/src_to`, `session_no`, ambient `witnessed_by`.
  - `retrieve(campaign_id, present_entity_ids, query_text, current_turn)` — SQL pool (salience+FTS+entity-presence) → weighted-sum re-rank → presence-gate → cooldown → dedup-vs-window → top-k=6 / ~800 tokens. Logs sub-scores to `DebugLog`.
  - `bump_session(campaign_id)`; `compute_salience(kind, facts)` pure fn.
- Deterministic hooks at existing emission sites, **direct calls wrapped in try/except (fail-open)**: `entity_died`/`combat_ended:defeat` (`combat_service._handle_entity_death`, snapshot **before** delete, emit **after** commit) and `loot_acquired` with rarity-scaled salience (`loot_service.take_items`, pass full party as `witnessed_by`). **Crit/near-death deferred to Sprint 2** (lower narrative value per row; more natural as a relationship beat — per over-engineering should-fix).
- `compute_salience`: defeat 1.0, death 0.85, loot `0.2 + rarity_weight` (`common 0, uncommon .1, rare .25, very_rare .4, legendary .55`), summary baseline 0.5.
- Fenced injection between `STORY SO FAR` and `SYSTEM CONTEXT (REFERENCE ONLY)`, in **both** DM and character paths: `RELEVANT MEMORIES (narrative reference only — NOT current state; the authoritative PARTY STATUS/ENEMIES below win)`.
- Env kill-switch `MEMORY_RAG_ENABLED` + per-campaign `memory_rag_enabled`.

**Scope OUT / deferred:** Embeddings/pgvector → Sprint 3. `EventBus` pub-sub → Sprint 2. `FakeEmbeddingProvider`/`cosine_rank`/`filter_by_dim` + their tests → Sprint 3 (no Sprint-1 caller; testing them now codifies an unbuilt API). `memory_facts`/reflection → Sprint 4. Relationships/register/crit-hook → Sprint 2. Markdown/lore → Sprint 3.

**Files touched:** `db/init_db.py`; `app/events/game_event.py` (new, model only); `app/services/memory_service.py` (new); `app/services/ai_service.py` (summary-ingest hook + retrieve/inject in DM and character paths); `app/services/combat_service.py` (death/defeat emit + `combat_event_seq`); `app/services/loot_service.py` (loot emit); `tests/test_memory_service.py`, `tests/test_memory_retrieval.py` (new); `pytest.ini`; `CLAUDE.md`.

**Test plan (all token-free; `-m "not integration"` stays green):**
1. weighted-sum re-rank prefers high-importance-old over low-importance-new — **the cross-session callback case**, using the FTS+entity-presence similarity term (no embeddings).
2. `compute_salience` returns expected scores incl. rarity scaling.
3. `record_event` is idempotent — same `source_ref` → one row; distinct events with identical content text → two rows (the `combat_event_seq` discriminator).
4. presence-gate excludes an episode whose `subject_refs` don't intersect present entities; ambient `summary` rows are never excluded.
5. cooldown suppresses re-surfacing within N turns.
6. fail-open: `retrieve` returns `[]` and `record_event` no-ops when key missing / flag off (and, asserted by stub, when extension absent).
7. a raised exception inside `record_event` does not propagate to the caller (memory failure can't corrupt state).

**Definition of done:** With `memory_rag_enabled=true` on the seeded Dev Test + Echoes campaigns: kill an enemy, take a rare item, advance ~40 messages (triggering summary aging), bump the session — the DM and a companion reference the kill, the rare loot, and the aged-out scene in narration **when the relevant subjects are present**; live HP/positions still come only from PARTY STATUS. Flag off → byte-identical to today. Unit suite green, zero tokens in CI.

**Risks:** entity-row deletion before snapshot → snapshot built in-memory pre-delete, emit post-commit (mitigated in scope). Prompt bloat → k=6/~800-token cap + DebugLog visibility. Salience weights are guesses → isolated in one pure fn, unit-tested, DebugLog-observable.

---

### SPRINT 2 — Relationships, emotional stakes, register control, quest memory, event bus (deterministic, no RAG)

**Goal.** NPCs and companions react to how the party treats them; the DM's tone follows danger and relationship; quests and promises stop being dead data. All deterministic.

**Scope IN:**
- **Promote the write seam to `EventBus`** (`app/events/bus.py` + `main.py` startup subscribe), now that quest/relationship/condition producers and memory+analytics consumers justify fan-out. Migrate the Sprint-1 direct calls onto it. **Add the deferred `critical_hit`/`near_death_save` hook here**, as an emotional/relationship beat.
- `relationships` table + `relationship_service.apply_event()` (heal-from-death +, attack-non-hostile −, social-check-success +) + `derive_tier()`. Hydrate party-level relationship onto NPCs on load (server-side only — **keep out of the broadcast blob**; `_last_broadcasted_state` is fragile).
- `register_service.select_register()` — pure fn `tension × tier × valence → register ∈ {grave, tense, neutral, warm, banter}` with **hysteresis** (require a margin to change tier; no grave↔banter thrash). Returns a **bark-bucket key**.
- **Bark-bucket contract (completeness must-fix).** Define canonical `data.voice.barks` buckets: `aggro|friendly|banter|wary|grief`. `context_builder.format_npc_state` (currently hardcodes `barks['aggro'][0]`, lines 122–128) selects the bucket by register instead. Authored NPC JSON lacking buckets falls back to `aggro`→`neutral`; the schema addition is documented in the Sprint-3 authoring contract. Separately, the register directive is injected into `character_agent.py` so **AI companions banter** (they have no NPC bark buckets — a companion jokes when tension is low AND the party relationship tier is warm/devoted, read from `relationships`).
- `quest_service.advance_stage()` (validates `requires[]`, **rejects illegal LLM-proposed advances**); `ACTIVE QUESTS` + `OPEN PROMISES` blocks injected into `context_builder` **above PARTY STATUS** (preserving the live-state-last invariant); `quest_flag_changed` + `relationship_changed` events feed `memory_episodes` (kind=`quest`/`relationship`).
- `state.narrative.{quests,revealed_facts,promises,variables}` in `game_states.state_data` (rides existing sync). `revealed_facts` writable **only** by deterministic quest advancement.
- `update_quest_progress` / `record_promise` **narration-only** tools in `ai_tools.py`.

**Scope OUT:** Embeddings (S3); reflection (S4); relationship-graph UI (Phase 2). Pure social warmth with no mechanical event won't move affinity until reflection lands — accepted, flagged.

**Test plan:** `derive_tier` boundaries; `apply_event` clamping + tier re-derivation + history cap; `select_register` truth table incl. hysteresis; `advance_stage` rejects when `requires` unmet; bark-bucket selection maps register→key; quest/promise blocks insert above PARTY STATUS. All deterministic, token-free.

**Definition of done:** Attacking a friendly NPC flips them hostile and the DM narrates the betrayal in a grave register; healing a downed ally raises trust and the companion later references it and banters when safe; an active quest's current stage appears in DM context; a promise made 3 sessions ago shows in OPEN PROMISES verbatim.

---

### SPRINT 3 — pgvector, BYOK embeddings, markdown campaigns, lore RAG *(split into 3a + 3b)*

Heavy sprint; ship as **two independent increments**.

**Sprint 3a — semantic recall (pgvector + BYOK embeddings):**
- Swap image → `pgvector/pgvector:pg15`; `CREATE EXTENSION` in its **own `engine.begin()` block before `metadata.create_all`**; ALTER embedding columns onto `memory_episodes`; register pgvector codec in `db/session.py` (string-literal bind is the documented primary path).
- `app/services/embeddings.py`: `get_embedding_provider(provider, api_key, model)` — Gemini `text-embedding-004` (768) / OpenAI `text-embedding-3-small` (1536), batched, 429 backoff. This is the **first multi-provider code in the repo** (`get_llm_instance` does not exist; `langchain-openai` is not yet in `requirements.txt`) — Sprint 3a owns adding `langchain-openai` + the provider dispatch. Embedding token counts folded into `campaigns.total_input_tokens` via each provider's usage field (chat `SocketIOCallbackHandler` does not cover embeddings — read usage from the embeddings response directly).
- `FakeEmbeddingProvider` + `cosine_rank` + `filter_by_dim` + their tests land **here** (now they have a production caller).
- Embed-at-write (background `create_task` with per-campaign in-flight guard + content-hash idempotency) **plus a reconciliation sweep**: a startup/periodic job re-embeds rows where `embedding IS NULL` (covers tasks killed by worker recycling — feasibility should-fix). Cosine swaps into `retrieve()`'s similarity slot via the **pool-union query** (importance contributes candidates).
- `reembed_campaign()` for provider switch; `scripts/backfill_memory.py` for existing `campaign_memories`.

**Sprint 3b — markdown authoring + lore RAG:**
- `markdown_compiler.py` — parse `campaign.md` → exact `games/*.json` shape + `lore_chunks` records. **Authoring dialect:** `## Location: <id>` / `## NPC: <id>` / `## Quest: <id>` headers; a `\`\`\`yaml ... \`\`\`` stat-fence inside a section compiles to deterministic JSON keys (e.g. an NPC's `data.stats`, `data.disposition`, `data.voice.barks` buckets, `data.knowledge`); prose under the header compiles to `lore_chunks` (narrative/RAG). Example: a `## NPC: blacksmith` section's yaml fence → the `npcs[].data` block `_hydrate_party` already consumes; its prose → a `lore_chunk(source_id="lore_blacksmith", gated_by=null)`.
- `campaign_validator.py` (referential integrity: every `requires`/`gated_by` id resolves; every NPC has the canonical bark buckets), CI-wired. A reverse-compile CLI regenerates the 4 existing `games/*.json` from round-tripped markdown to **prove byte-shape fidelity** (the safety net against silent hydration mis-values).
- `lore_service.seed_lore_corpus` / `retrieve_lore` — **hard `gated_by` pre-filter** against deterministic `revealed_facts` (an unearned secret never reaches the prompt even if semantically top-ranked), skip-if-empty guard, `RELEVANT LORE` block in `context_builder` (above PARTY STATUS).

**Scope OUT:** ANN/HNSW index (brute-force until a measured >10k-chunk campaign); RRF fusion (pure weighted-sum over the merged pool is adequate at stated scale — defer until measured recall justifies it); cross-encoder rerankers; external vector DB (never); per-dim partial indexes; folder-split campaigns; numeric faction reputation.

**Test plan:** real `<=>` ranking (`@pytest.mark.integration`, pgvector container); BYOK dim isolation (768 query never hits 1536 rows); pool-union resurfaces a high-importance low-cosine memory; NULL-embedding reconciliation sweep backfills; gated lore hard pre-filter (secret hidden until its fact is revealed); markdown round-trip fidelity (compiled `.md` == original `.json` shape).

**Definition of done:** "Who betrayed us and why" pulls the actual scene by semantics. OpenAI-keyed and Gemini-keyed campaigns both retrieve correctly; provider switch degrades recall (not correctness) until `reembed_campaign` runs. Author Echoes in `campaign.md`, compile, instantiate — runtime identical to the JSON. A gated lore secret surfaces only after its quest stage completes.

---

### SPRINT 4 — Reflection / consolidation, relationship evolution, forgetting

**Goal.** Episodic→semantic distillation; supersedable relationship facts; graceful forgetting.

**Scope IN:** `memory_facts` table; throttled `reflect()` (session-end or every K=20 episodes, BYOK-gated, writes distilled facts with `source_episode_ids` provenance). Relationship evolution via `supersedes` + `valid` (soft-supersede, never hard-delete). SQL `prune()` — banter/trivia evicted, deterministic `kind=event/death/loot` **exempt**, semantic facts soft-superseded never deleted.

**Decision #5 bounded exception (over-engineering should-fix):** reflection lets the LLM assign `memory_facts.importance`, a deliberate, **clamped** departure from "writer assigns salience." Clamp to `[0.3, 0.7]`; deterministic `kind=event/death/loot` episodes always outrank LLM-scored facts on ties. This is the *only* place the LLM touches salience, and it is documented as such so a contributor doesn't read Decision #5 as absolute.

**Scope OUT / deferred:** the `RulesEngine` Protocol + `DnD5eRulesEngine` adapter moves to **Sprint 5 / "when a second ruleset is actually requested."** The brief says "D&D 5e FIRST" and there is exactly one system; the `GameEvent.facts` generic payload already delivers the portability value, and routing `start_combat` through a factory touches the verified-fragile `TurnManager` lock→advance→save→emit flow for zero behavior change. (Known 5e leak to address whenever that seam lands: `context_builder.get_stat_block` at line 24 hardcodes the `(val-10)//2` modifier — flagged, out of scope until then.) Also out: second concrete ruleset; reflection hierarchies / planning memory; MemGPT self-editing memory (new poisoning surface).

**Test plan:** reflection facts carry `source_episode_ids` provenance; `supersedes` flips the old fact `valid=false` and retrieval returns only the current; prune spares `kind=event/death/loot`; clamped LLM importance never exceeds 0.7 and loses ties to deterministic event rows.

**Definition of done:** After a session a distilled relationship fact appears and supersedes its predecessor on change; old banter is pruned while a death beat survives.

---

## Decisions Ledger

| # | Decision | Choice | Why / what was deferred |
|---|----------|--------|-------------------------|
| 1 | Memory store shape | **One `memory_episodes` append-only table** (kind-tagged); `memory_facts` only at reflection | 5 dimensions named the same log; a 2nd table earns its place only for *distilled supersedable* facts (S4). |
| 2 | Sprint-1 retrieval | **SQL salience+recency+FTS+entity-presence, NO embeddings** | At low-thousands rows SQL is sub-10ms; vectors are premature. Keeps S1 shippable in 1–2 wks. pgvector → S3 (lore's home). |
| 3 | Write seam | **Direct `record_event` call (try/except, fail-open) in S1; `EventBus` in S2** | Memory is the sole consumer in S1; a bus is build-ahead-of-need. Bus earns its place when quest/relationship/condition producers multiply. Firewall comes from `GameEvent.facts`, not the bus. |
| 4 | BYOK embedding dims | **Unconstrained `vector` col + `embed_dim` filter + per-campaign brute-force cosine** | One provider per campaign ⇒ dims never mix. Rejected zero-pad (silent invariant) and per-dim HNSW (premature). |
| 5 | Salience ownership | **Writer assigns it in Python; LLM only in S4 reflection, clamped [0.3,0.7], loses ties to deterministic rows** | Determinism-first; the one bounded exception is documented so it isn't read as absolute. |
| 6 | Rank formula | **Weighted SUM over a pool that UNIONs (similarity) + (importance) + (presence) candidates** | A product, or a cosine-only pool, drops old-but-relevant callbacks — exactly the cross-session beats the brief prizes. |
| 7 | Relationships | **Separate authoritative `relationships` table (numbers); recollection lives in episodes (story)** | Numbers are deterministic state; the *story* of the change is RAG. Pairwise edges don't belong in any one NPC's JSON. |
| 8 | Register/tone | **Pure fn state→register→bark-bucket key, direct-injected, with hysteresis** | Guardrail-class (always-on, not retrieved). "Funny when it should be" must be deterministic, not LLM mood. |
| 9 | Quest state | **Deterministic in `game_states.narrative`; LLM narrates committed transitions only; blocks injected above PARTY STATUS** | Mirrors combat ethos; rejects illegal advances; preserves live-state-last; rides existing JSON-Patch sync. |
| 10 | Lore gating | **Hard pre-filter on `gated_by` vs deterministic `revealed_facts`** | Unearned secrets can't reach the prompt even if semantically top-ranked. Mechanics unlock lore, never the reverse. |
| 11 | Markdown campaigns | **Compile to existing `games/*.json` shape; JSON stays valid runtime input; round-trip test enforces fidelity** | Zero runtime change; rejected bespoke MD runtime (rewrites fragile hydration). |
| 12 | System-agnostic seam | **`GameEvent.facts` generic payload now; `RulesEngine` Protocol deferred to S5/when a 2nd ruleset is requested** | The firewall is the data shape; building the interface before a 2nd impl (and touching fragile TurnManager) is premature. |
| 13 | Failure mode | **Fail-open: no key / flag off / no extension ⇒ degrade to today's rolling summary** | Memory is strictly additive; can never crash the engine or block a turn. |
| 14 | Provider resolution | **Add `campaigns.llm_provider`/`embed_model`; memory owns embedding-provider dispatch** | `campaigns` has no provider column; `profiles.llm_provider` is wrong scope for multiplayer. `get_llm_instance` does not exist — memory resolves its own; `embeddings.py` is the repo's first multi-provider code. |
| 15 | Embedding timing | **Embed at WRITE (background `create_task` + in-flight guard) + a NULL-embedding reconciliation sweep; query-embed at read** | Player turns never block on embed I/O. The reconciliation sweep covers tasks killed by worker recycling. Rejects the premature per-call corpus-embed pattern. |
| 16 | Item rarity | **Add `items.rarity` (S1) so loot salience scales** | Verified: items have no rarity field; without it loot collapses to the 0.2 floor and "great loot as a memorable beat" is unmet. |
| 17 | Session counter | **Add `campaigns.session_no`, bumped on reconnect-after-gap; stamped on every episode** | No session concept exists; "several sessions ago" recall and the S1 DoD depend on it. |
| 18 | Callback mechanism | **Presence-gate (subject_refs ∩ present) + cooldown (`recently_surfaced`, N=12 turns); summaries are ambient** | The marquee feature is specified, not asserted. S1 DoD scopes the claim to gated retrieval, not arbitrary callbacks. |

---

## Product Brief → Mechanism → Sprint Traceability

| Brief element | Concrete mechanism | Honors ethos via | Sprint |
|---|---|---|---|
| **Light/friendly banter** | `register_service`→bark-bucket key; companion banter when tension low + party tier warm/devoted; injected into `character_agent` | Deterministic register, direct-injected | 2 |
| **Great loot as memorable beats** | `loot_acquired` event, salience `0.2 + rarity_weight` (new `items.rarity`), stores item **ID** | Fact verbatim from `loot_service`; ID pins reality | 1 |
| **Persistent characters** | `subject_refs`/`witnessed_by`; companion retrieval biases on its own `witnessed_by` via `entity_overlap_bonus` (campaign-scoped, not a separate per-character index) | Engine-owned sheet; memory is reference | 1 |
| **Evolving relationships** | `relationships` table + deterministic `apply_event`; `memory_facts.supersedes` for the *story* of change | Numbers deterministic; story is RAG | 2 (state) / 4 (evolution) |
| **High emotional stakes + callbacks** | high-salience death/defeat beats; pool-union surfaces old-but-relevant; presence-gate + cooldown | Salience in Python; fenced reference-only | 1 |
| **Quests** | `quest_service` deterministic stage graph; `ACTIVE QUESTS`/`OPEN PROMISES` above PARTY STATUS; illegal-advance rejection | State deterministic, LLM narrates | 2 |
| **Lore / worldbuilding** | `lore_chunks` RAG, `gated_by` hard pre-filter, skip-if-empty | Narrative reference only; never feeds resolver | 3b |
| **Markdown campaigns** | `markdown_compiler` (yaml-fence=deterministic, prose=lore) → existing JSON shape; `campaign_validator` + round-trip CI | Determinism enforced at authoring layer | 3b |
| **TTRPG-agnostic** | `GameEvent.facts` generic numbers (now); `RulesEngine` Protocol deferred until a 2nd ruleset | Data-shape firewall now, interface when earned | 5 (deferred) |

**Three ethos anchors, honored throughout:** (1) **Determinism first** — every memory write is downstream of a Python-resolved fact; the LLM has no tool that writes HP/gold/state; retrieved memory is always fenced "reference only — authoritative state below wins"; the one LLM salience exception (S4 reflection) is clamped and loses ties to deterministic rows. (2) **BYOK + multi-provider** — one provider per campaign, `embed_dim`-filtered retrieval makes cross-provider mixing structurally impossible, no server-key fallback, memory no-ops without a key. (3) **Guardrails always-on, memory retrieved** — DM persona, combat protocol, conditions, and social register stay direct-injected; only episodic memory and lore (large, per-campaign, narrative-only) are retrieval targets, and lore retrieval is skipped entirely when a campaign has no `lore_chunks`.

**Files verified during synthesis:** `loot_service.take_items` (only `actor`+`vessel` in scope at emit — drove the `witnessed_by` fix), `context_builder.get_stat_block:24` (hardcoded `(val-10)//2` 5e leak — flagged for the deferred rules seam), `db/session.py` (bare `create_async_engine`, no connect hook — drove the pgvector codec + string-literal-primary fix).
