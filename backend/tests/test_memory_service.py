"""Token-free unit tests for the Sprint 1 memory core (pure functions only).

These cover the design's retrieval/salience guarantees without a DB or any LLM
call: salience scoring, the cross-session callback (weighted sum surfaces an
old-but-relevant memory), the presence gate, and the cooldown.
"""
from app.services.memory_service import (
    compute_salience,
    _rank_and_gate,
    format_memory_block,
)


def _ep(id, kind="event", importance=0.5, subjects=None, fts=0.0, created_ts=1000.0, content="x"):
    return {
        "id": id,
        "kind": kind,
        "content": content,
        "subject_refs": subjects or [],
        "importance": importance,
        "fts_rank": fts,
        "created_ts": created_ts,
    }


# ── salience ──────────────────────────────────────────────────────────────────
def test_compute_salience_loot_scales_with_rarity():
    assert compute_salience("loot", {"rarity": "common"}) == 0.2
    assert compute_salience("loot", {"rarity": "rare"}) == 0.45
    assert compute_salience("loot", {"rarity": "legendary"}) == 0.75
    # unknown rarity falls back to the common floor
    assert compute_salience("loot", {"rarity": "mythic?"}) == 0.2


def test_compute_salience_death_vs_defeat():
    assert compute_salience("death", {"was_hostile": True}) == 1.0   # foe defeated — triumphant
    assert compute_salience("death", {"was_hostile": False}) == 0.85  # ally down — grave
    assert compute_salience("summary") == 0.5
    assert compute_salience("unknown-kind") == 0.5


# ── cross-session callback: old-but-relevant beats recent-but-irrelevant ──────
def test_rank_surfaces_old_relevant_over_new_irrelevant():
    present = ["npc_silas"]
    # Old, high-importance, ABOUT a present entity (the betrayer is in the room).
    old_relevant = _ep("old", kind="relationship", importance=0.9,
                        subjects=[{"id": "npc_silas"}], created_ts=1000.0)
    # New, low-importance, about nobody present.
    new_irrelevant = _ep("new", kind="event", importance=0.3,
                         subjects=[{"id": "npc_other"}], created_ts=5_000_000.0)
    ranked = _rank_and_gate([new_irrelevant, old_relevant], present_entity_ids=present)
    assert ranked, "expected at least one memory to survive gating"
    assert ranked[0]["id"] == "old", "old-but-relevant memory should rank first"


# ── presence gate ─────────────────────────────────────────────────────────────
def test_presence_gate_excludes_absent_subjects_but_keeps_ambient_summaries():
    present = ["pc_1"]
    about_present = _ep("hit", subjects=[{"id": "pc_1"}])
    about_absent = _ep("absent", subjects=[{"id": "enemy_99"}])
    ambient_summary = _ep("sum", kind="summary", subjects=[])  # no subjects → ambient
    ranked = _rank_and_gate([about_present, about_absent, ambient_summary], present_entity_ids=present)
    ids = {e["id"] for e in ranked}
    assert "hit" in ids          # subject present → eligible
    assert "sum" in ids          # summary is ambient → always eligible
    assert "absent" not in ids   # subject absent → gated out


# ── cooldown ──────────────────────────────────────────────────────────────────
def test_cooldown_suppresses_recently_surfaced():
    ep = _ep("beat", kind="summary")
    # surfaced on turn 100; current turn 105, cooldown window 12 → still suppressed
    ranked = _rank_and_gate([ep], current_turn=105, recently_surfaced={"beat": 100})
    assert ranked == []
    # 20 turns later it is eligible again
    ranked2 = _rank_and_gate([ep], current_turn=120, recently_surfaced={"beat": 100})
    assert len(ranked2) == 1


# ── top-k budget ──────────────────────────────────────────────────────────────
def test_rank_respects_top_k():
    eps = [_ep(f"e{i}", kind="summary", importance=0.5, created_ts=1000.0 + i) for i in range(10)]
    ranked = _rank_and_gate(eps, k=6)
    assert len(ranked) == 6


# ── fenced output ─────────────────────────────────────────────────────────────
def test_format_memory_block_fences_as_reference_only():
    assert format_memory_block([]) == ""
    block = format_memory_block([{"content": "SILAS betrayed the party at the bridge."}])
    assert "reference only" in block.lower()
    assert "SILAS betrayed the party" in block
