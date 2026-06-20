"""Long-term episodic memory (Sprint 1).

Captures deterministic facts and aged-out rolling summaries into an append-only
`memory_episodes` log, then retrieves them as clearly-fenced narrative reference
(never authoritative state). Sprint 1 ranks in SQL by salience + recency +
full-text keyword + entity-presence — NO embeddings, NO pgvector (those arrive
in Sprint 3 when lore, a genuinely large corpus, earns them).

Design invariants:
  * Strictly additive & fail-open — if the feature flag is off, a key is missing,
    or anything throws, memory no-ops and the engine behaves exactly as before.
  * Salience is assigned by the WRITER in Python, never by an LLM (Sprint 1).
  * Retrieved memory is reference only; the live authoritative state block that
    appears LAST in the prompt always wins.
"""
import os
import json
import hashlib
import logging
from typing import Any, Optional

from sqlalchemy import text
from db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)

# ── Salience (writer-assigned) ────────────────────────────────────────────────
BASE_SALIENCE = {
    "summary": 0.5,
    "event": 0.4,
    "quest": 0.7,
    "relationship": 0.6,
    "reflection": 0.6,
}
RARITY_WEIGHT = {
    "common": 0.0,
    "uncommon": 0.1,
    "rare": 0.25,
    "very_rare": 0.4,
    "legendary": 0.55,
}

# ── Retrieval tuning ──────────────────────────────────────────────────────────
W_SIM, W_IMP, W_REC = 0.5, 0.25, 0.25      # weighted SUM (not product — keeps old-but-relevant alive)
HALF_LIFE_SECONDS = 7 * 24 * 3600           # recency decay half-life
COOLDOWN_TURNS = 12                          # don't re-surface the same beat within N turns
DEFAULT_TOP_K = 6
IMPORTANCE_FLOOR = 0.6                        # rows at/above this are always pooled
POOL_LIMIT = 40


def _enabled() -> bool:
    """Global kill-switch. Default OFF so behavior is byte-identical until opted in."""
    return os.getenv("MEMORY_RAG_ENABLED", "false").strip().lower() in ("1", "true", "yes", "on")


def is_enabled() -> bool:
    """Public flag check, so callers can skip all memory work (incl. extra DB reads)
    when the feature is off."""
    return _enabled()


def _episode_id(campaign_id: str, kind: str, source_ref: str) -> str:
    return hashlib.sha256(f"{campaign_id}|{kind}|{source_ref}".encode("utf-8")).hexdigest()[:32]


def _ref_ids(subject_refs: Any) -> list[str]:
    """Extract entity ids from subject_refs, tolerating dicts, strings, or a JSON string."""
    if isinstance(subject_refs, str):
        try:
            subject_refs = json.loads(subject_refs)
        except (ValueError, TypeError):
            return []
    out = []
    for r in (subject_refs or []):
        if isinstance(r, dict) and r.get("id"):
            out.append(r["id"])
        elif isinstance(r, str):
            out.append(r)
    return out


def compute_salience(kind: str, facts: Optional[dict] = None) -> float:
    """Importance in [0, 1], assigned deterministically by the writing code."""
    facts = facts or {}
    if kind == "loot":
        rarity = str(facts.get("rarity", "common")).lower()
        return round(0.2 + RARITY_WEIGHT.get(rarity, 0.0), 4)
    if kind == "death":
        # A foe defeated is a triumphant beat (1.0); an ally going down is a grave one (0.85).
        return 1.0 if facts.get("was_hostile") else 0.85
    return BASE_SALIENCE.get(kind, 0.5)


def _on_cooldown(ep_id: str, recently_surfaced: dict, current_turn: Optional[int]) -> bool:
    last = (recently_surfaced or {}).get(ep_id)
    if last is None or current_turn is None:
        return False
    return last > (current_turn - COOLDOWN_TURNS)


def _rank_and_gate(
    candidates: list[dict],
    present_entity_ids: Optional[list[str]] = None,
    current_turn: Optional[int] = None,
    recently_surfaced: Optional[dict] = None,
    k: int = DEFAULT_TOP_K,
) -> list[dict]:
    """Pure ranking core (no I/O), so it is fully unit-testable without a DB.

    Pipeline: cooldown filter → presence gate → weighted-sum score → top-k.
    Score = W_SIM*similarity + W_IMP*importance + W_REC*recency_decay, where
    similarity = 0.6*normalized_fts + 0.4*entity_overlap. The weighted SUM (not a
    product) is what lets an OLD but highly-relevant memory resurface — the
    cross-session callback the design prizes.
    """
    present = set(present_entity_ids or [])
    recently = recently_surfaced or {}

    # 1. cooldown
    pool = [c for c in candidates if not _on_cooldown(c["id"], recently, current_turn)]

    # 2. eligibility — keep an episode if it is ambient (a summary, or has no subjects),
    #    topically relevant to the current query (a full-text hit), or about a
    #    currently-present entity. Presence ALONE is too strict: it would block
    #    "remember when you killed the LIZARDFOLK" once the lizardfolk is gone, even
    #    when the player explicitly asks about it. Topical relevance covers that case.
    gated = []
    for c in pool:
        subj = set(_ref_ids(c.get("subject_refs")))
        ambient = c.get("kind") == "summary" or not subj
        relevant = (c.get("fts_rank") or 0.0) > 0.0
        if ambient or relevant or (subj & present):
            gated.append(c)
    if not gated:
        return []

    # 3. weighted-sum score
    max_fts = max((c.get("fts_rank") or 0.0) for c in gated) or 1.0
    now_ref = max((c.get("created_ts") or 0.0) for c in gated)
    scored = []
    for c in gated:
        subj = set(_ref_ids(c.get("subject_refs")))
        overlap = 1.0 if (subj & present) else 0.0
        fts_norm = (c.get("fts_rank") or 0.0) / max_fts
        similarity = 0.6 * fts_norm + 0.4 * overlap
        importance = float(c.get("importance") or 0.0)
        age = max(0.0, now_ref - (c.get("created_ts") or 0.0))
        recency = 0.5 ** (age / HALF_LIFE_SECONDS)
        total = W_SIM * similarity + W_IMP * importance + W_REC * recency
        scored.append((total, c))

    scored.sort(key=lambda t: t[0], reverse=True)
    return [c for _, c in scored[:k]]


# ── Write path ────────────────────────────────────────────────────────────────
async def record_event(
    campaign_id: str,
    kind: str,
    content: str,
    *,
    facts: Optional[dict] = None,
    subject_refs: Optional[list] = None,
    witnessed_by: Optional[list] = None,
    importance: Optional[float] = None,
    source_ref: str = "",
    session_no: Optional[int] = None,
) -> None:
    """Append one episode. Opens its OWN session (the caller's may already be
    committed/closed), idempotent on (campaign|kind|source_ref), and fail-open."""
    if not _enabled():
        return
    try:
        facts = facts or {}
        imp = importance if importance is not None else compute_salience(kind, facts)
        ep_id = _episode_id(campaign_id, kind, source_ref or content)
        async with AsyncSessionLocal() as session:
            await session.execute(
                text("""
                    INSERT INTO memory_episodes
                        (id, campaign_id, kind, content, facts, subject_refs, witnessed_by, importance, session_no)
                    VALUES
                        (:id, :cid, :kind, :content, CAST(:facts AS JSONB),
                         CAST(:subject_refs AS JSONB), CAST(:witnessed_by AS JSONB), :imp, :session_no)
                    ON CONFLICT (id) DO NOTHING
                """),
                {
                    "id": ep_id,
                    "cid": campaign_id,
                    "kind": kind,
                    "content": content,
                    "facts": json.dumps(facts),
                    "subject_refs": json.dumps(subject_refs or []),
                    "witnessed_by": json.dumps(witnessed_by or []),
                    "imp": imp,
                    "session_no": session_no,
                },
            )
            await session.commit()
    except Exception as e:  # noqa: BLE001 — memory must never break the engine
        logger.warning("memory.record_event failed (non-fatal): %s", e)


async def bump_session(campaign_id: str) -> Optional[int]:
    """Increment the campaign's session counter (drives 'several sessions ago')."""
    if not _enabled():
        return None
    try:
        async with AsyncSessionLocal() as session:
            res = await session.execute(
                text("UPDATE campaigns SET session_no = COALESCE(session_no, 1) + 1 WHERE id = :cid RETURNING session_no"),
                {"cid": campaign_id},
            )
            row = res.fetchone()
            await session.commit()
            return row[0] if row else None
    except Exception as e:  # noqa: BLE001
        logger.warning("memory.bump_session failed (non-fatal): %s", e)
        return None


async def ingest_episode_from_summary(
    campaign_id: str,
    summary_text: str,
    *,
    party_ids: Optional[list] = None,
    session_no: Optional[int] = None,
) -> None:
    """Promote an aged-out rolling summary into durable episodic memory.

    Ambient (empty witnessed_by); subject_refs = the party so it stays reachable.
    Idempotent on the summary text, so re-ingesting the same summary is a no-op.
    """
    await record_event(
        campaign_id,
        kind="summary",
        content=summary_text,
        subject_refs=[{"kind": "player", "id": pid} for pid in (party_ids or [])],
        witnessed_by=[],
        importance=BASE_SALIENCE["summary"],
        source_ref="",  # → record_event derives a stable id from the content
        session_no=session_no,
    )


# ── Read path ─────────────────────────────────────────────────────────────────
_POOL_SQL = text("""
    SELECT id, kind, content, subject_refs, importance,
           COALESCE(ts_rank(to_tsvector('english', content), plainto_tsquery('english', :q)), 0) AS fts_rank,
           extract(epoch FROM created_at) AS created_ts
    FROM memory_episodes
    WHERE campaign_id = :cid
      AND (CAST(:window_ts AS double precision) IS NULL
           OR extract(epoch FROM created_at) < CAST(:window_ts AS double precision))
      AND (importance >= :imp_floor
           OR (:q <> '' AND to_tsvector('english', content) @@ plainto_tsquery('english', :q)))
    ORDER BY importance DESC, created_at DESC
    LIMIT :pool_limit
""")


async def retrieve(
    campaign_id: str,
    db,
    *,
    present_entity_ids: Optional[list] = None,
    query_text: str = "",
    current_turn: Optional[int] = None,
    recently_surfaced: Optional[dict] = None,
    window_start_ts: Optional[float] = None,
    k: int = DEFAULT_TOP_K,
) -> list[dict]:
    """Return up to `k` relevant past episodes (dicts) for fenced injection.

    Uses the caller's read-only session. Fail-open: returns [] on any error.
    Narrative state (`recently_surfaced`, the working-window cutoff) is supplied
    by the caller, keeping this function a thin SQL-pool + pure-rank wrapper.
    """
    if not _enabled():
        return []
    try:
        res = await db.execute(_POOL_SQL, {
            "cid": campaign_id,
            "q": query_text or "",
            "window_ts": window_start_ts,
            "imp_floor": IMPORTANCE_FLOOR,
            "pool_limit": POOL_LIMIT,
        })
        candidates = []
        for row in res.mappings().all():
            candidates.append({
                "id": row["id"],
                "kind": row["kind"],
                "content": row["content"],
                "subject_refs": _ref_ids(row["subject_refs"]),
                "importance": row["importance"],
                "fts_rank": float(row["fts_rank"] or 0.0),
                "created_ts": float(row["created_ts"] or 0.0),
            })
        return _rank_and_gate(candidates, present_entity_ids, current_turn, recently_surfaced, k=k)
    except Exception as e:  # noqa: BLE001
        logger.warning("memory.retrieve failed (non-fatal): %s", e)
        return []


def format_memory_block(episodes: list[dict]) -> str:
    """Render retrieved episodes as a clearly-fenced, reference-only block.

    The fence is deliberate: the authoritative PARTY STATUS / ENEMIES block is
    injected AFTER this and labeled 'current', so the model treats memory as
    past-tense recollection, never as live state.
    """
    if not episodes:
        return ""
    lines = "\n".join(f"- {e['content']}" for e in episodes)
    return (
        "\n\n=== RELEVANT MEMORIES (narrative reference only — NOT current state; "
        "the authoritative PARTY STATUS / ENEMIES below win) ===\n"
        f"{lines}\n=== END MEMORIES ===\n"
    )


def present_entity_ids(game_state) -> list:
    """All entity ids currently in the scene (party + enemies + npcs)."""
    ids = []
    for coll in ("party", "enemies", "npcs"):
        for e in (getattr(game_state, coll, None) or []):
            eid = getattr(e, "id", None)
            if eid:
                ids.append(eid)
    return ids


async def recall_block(campaign_id: str, db, game_state, query_text: str, k: int = DEFAULT_TOP_K) -> str:
    """Convenience: retrieve relevant memories for the current scene and return a
    fenced, reference-only block ready to inject. Empty string if disabled, if there
    is no state, or if nothing relevant surfaces."""
    if not _enabled() or game_state is None:
        return ""
    eps = await retrieve(
        campaign_id, db,
        present_entity_ids=present_entity_ids(game_state),
        query_text=query_text or "",
        current_turn=getattr(game_state, "turn_index", None),
        k=k,
    )
    return format_memory_block(eps)
