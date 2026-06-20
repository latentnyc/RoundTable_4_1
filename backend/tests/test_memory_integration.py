"""Integration tests for the Sprint 1 memory DB layer (require live Postgres).

Run:  pytest backend/tests/test_memory_integration.py -m integration

These exercise the SQL that unit tests cannot honestly cover: the JSONB casts,
ON CONFLICT idempotency, and the full-text retrieval/ranking query against a real
database. Each test uses a throwaway campaign id and cleans up after itself.
"""
import pytest
from uuid import uuid4
from sqlalchemy import text

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
async def _dispose_engine_after_test():
    """The app's global async engine pools connections; pytest-asyncio gives each
    test a fresh event loop. Dispose the pool inside the test's own loop so cleanup
    doesn't run against an already-closed loop."""
    yield
    from db.session import engine
    await engine.dispose()


@pytest.fixture
def enable_memory(monkeypatch):
    monkeypatch.setenv("MEMORY_RAG_ENABLED", "true")


async def _count(db, cid):
    res = await db.execute(text("SELECT COUNT(*) FROM memory_episodes WHERE campaign_id = :c"), {"c": cid})
    return res.scalar()


async def test_record_retrieve_and_idempotency(enable_memory):
    from app.services import memory_service as ms
    from db.session import AsyncSessionLocal

    cid = f"itest-{uuid4().hex[:8]}"
    try:
        await ms.record_event(
            cid, "death",
            "BRUNA struck down the LIZARDFOLK warrior with a mighty greataxe blow.",
            facts={"was_hostile": True, "hp_after": 0},
            subject_refs=[{"kind": "enemy", "id": "liz_1", "name": "Lizardfolk"}],
            witnessed_by=["pc_elara", "pc_bruna"],
            source_ref="combat:seq1:liz_1",
        )
        await ms.record_event(
            cid, "loot",
            "ELARA claimed a Flame Tongue longsword from the chest.",
            facts={"rarity": "rare", "item_id": "flame_tongue"},
            subject_refs=[{"kind": "player", "id": "pc_elara"}, {"kind": "item", "id": "flame_tongue"}],
            witnessed_by=["pc_elara", "pc_bruna"],
            source_ref="loot:chest1:pc_elara",
        )
        # Idempotent: a retry with the same source_ref must NOT create a second row.
        await ms.record_event(cid, "death", "dup", facts={"was_hostile": True}, source_ref="combat:seq1:liz_1")

        async with AsyncSessionLocal() as db:
            assert await _count(db, cid) == 2, "ON CONFLICT idempotency failed"

            # Writer-assigned salience persisted (foe defeat = 1.0, rare loot = 0.45).
            rows = (await db.execute(
                text("SELECT kind, importance FROM memory_episodes WHERE campaign_id=:c ORDER BY importance DESC"),
                {"c": cid})).all()
            assert rows[0].kind == "death" and abs(rows[0].importance - 1.0) < 1e-6
            assert any(r.kind == "loot" and abs(r.importance - 0.45) < 1e-6 for r in rows)

            # Asking about the lizardfolk (FTS) with it present surfaces the kill.
            eps = await ms.retrieve(cid, db, present_entity_ids=["liz_1"], query_text="lizardfolk", current_turn=10)
            assert any("LIZARDFOLK" in e["content"] for e in eps)

            # Topical recall by item name, with the looter present.
            eps2 = await ms.retrieve(cid, db, present_entity_ids=["pc_elara"], query_text="flame tongue", current_turn=10)
            assert any("Flame Tongue" in e["content"] for e in eps2)

            # Nobody present and no query → no spurious recall.
            eps3 = await ms.retrieve(cid, db, present_entity_ids=[], query_text="", current_turn=10)
            assert eps3 == []
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(text("DELETE FROM memory_episodes WHERE campaign_id = :c"), {"c": cid})
            await db.commit()


async def test_disabled_flag_is_a_noop(monkeypatch):
    """With the flag off, record_event writes nothing and retrieve returns []."""
    monkeypatch.setenv("MEMORY_RAG_ENABLED", "false")
    from app.services import memory_service as ms
    from db.session import AsyncSessionLocal

    cid = f"itest-off-{uuid4().hex[:8]}"
    await ms.record_event(cid, "death", "should not be written", facts={"was_hostile": True}, source_ref="x")
    async with AsyncSessionLocal() as db:
        assert await _count(db, cid) == 0
        assert await ms.retrieve(cid, db, query_text="anything") == []


async def test_recall_block_surfaces_a_kill(enable_memory):
    """End-to-end of the exact helper the AI service injects: record a kill, then
    recall_block returns it fenced as reference-only when the foe is in the scene."""
    from app.services import memory_service as ms
    from db.session import AsyncSessionLocal
    from types import SimpleNamespace

    cid = f"itest-{uuid4().hex[:8]}"
    try:
        await ms.record_event(
            cid, "death", "BRUNA slew the GOBLIN chieftain.",
            facts={"was_hostile": True},
            subject_refs=[{"kind": "enemy", "id": "gob_1", "name": "Goblin"}],
            witnessed_by=["pc_a"], source_ref="death:gob_1",
        )
        gs = SimpleNamespace(
            party=[SimpleNamespace(id="pc_a")],
            enemies=[SimpleNamespace(id="gob_1")],
            npcs=[], turn_index=3,
        )
        async with AsyncSessionLocal() as db:
            block = await ms.recall_block(cid, db, gs, query_text="goblin")
            assert "RELEVANT MEMORIES" in block
            assert "GOBLIN chieftain" in block
            assert "reference only" in block.lower()
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(text("DELETE FROM memory_episodes WHERE campaign_id = :c"), {"c": cid})
            await db.commit()
