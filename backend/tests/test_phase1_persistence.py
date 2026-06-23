"""Phase 1 — persistence-as-single-transactional-source-of-truth.

These are integration tests: they exercise the real upsert / transaction /
unique-constraint behaviour against the live database, which mocks cannot model.
Each test seeds a throwaway profile+campaign with unique ids and tears it down in
a finally block, so the suite stays re-runnable against the shared dev DB.
"""
import json
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from db.session import DATABASE_URL
from app.services.state_service import StateService
from app.models import GameState, Player, Location, Coordinates

pytestmark = pytest.mark.integration

# Dedicated NullPool engine: every connection opens and closes within the test's own
# (function-scoped) event loop, avoiding the shared QueuePool's cross-loop
# "Event loop is closed" flakiness under pytest-asyncio on Windows.
_engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
_Session = async_sessionmaker(_engine, expire_on_commit=False)


async def _seed_campaign():
    """Create a throwaway profile + campaign (FK prerequisites); return (campaign_id, user_id)."""
    cid = f"phase1-camp-{uuid.uuid4()}"
    uid = f"phase1-user-{uuid.uuid4()}"
    async with _Session() as db:
        await db.execute(
            text("INSERT INTO profiles (id, username) VALUES (:uid, :uname)"),
            {"uid": uid, "uname": f"Phase1 {uid}"},
        )
        await db.execute(
            text("INSERT INTO campaigns (id, name, gm_id) VALUES (:cid, 'Phase1 Test', :uid)"),
            {"cid": cid, "uid": uid},
        )
        await db.commit()
    return cid, uid


async def _cleanup_campaign(cid, uid):
    async with _Session() as db:
        await db.execute(text("DELETE FROM game_states WHERE campaign_id=:cid"), {"cid": cid})
        await db.execute(text("DELETE FROM characters WHERE campaign_id=:cid OR user_id=:uid"), {"cid": cid, "uid": uid})
        await db.execute(text("DELETE FROM monsters WHERE campaign_id=:cid"), {"cid": cid})
        await db.execute(text("DELETE FROM npcs WHERE campaign_id=:cid"), {"cid": cid})
        await db.execute(text("DELETE FROM campaigns WHERE id=:cid"), {"cid": cid})
        await db.execute(text("DELETE FROM profiles WHERE id=:uid"), {"uid": uid})
        await db.commit()


def _make_player(uid, name="Aria", hp=22, **sheet):
    return Player(
        id=str(uuid.uuid4()), name=name, role="Wizard", is_ai=False,
        hp_current=hp, hp_max=hp, ac=12, position=Coordinates(x=0, y=0),
        user_id=uid, sheet_data=dict(sheet),
    )


def _make_state(cid, player):
    return GameState(
        session_id=cid,
        location=Location(name="Test Room", description="d", walkable_cells=[Coordinates(x=0, y=0)]),
        party=[player],
    )


async def _row_count(db, cid):
    return await db.scalar(text("SELECT count(*) FROM game_states WHERE campaign_id=:cid"), {"cid": cid})


async def test_save_game_state_upserts_one_row_and_latest_is_deterministic():
    """Rapid successive saves collapse to ONE row and the latest read is the last save
    (not a non-deterministic newest-by-timestamp pick of an append-log)."""
    cid, uid = await _seed_campaign()
    try:
        player = _make_player(uid)
        state = _make_state(cid, player)
        async with _Session() as db:
            for i in range(6):
                state.turn_index = i
                await StateService.save_game_state(cid, state, db)
                await db.commit()
            assert await _row_count(db, cid) == 1

        async with _Session() as db:
            loaded = await StateService.get_game_state(cid, db)
            assert loaded.turn_index == 5
            assert await _row_count(db, cid) == 1
    finally:
        await _cleanup_campaign(cid, uid)


async def test_save_is_atomic_rollback_leaves_prior_state_intact():
    """A save stages writes across characters + game_states but does NOT commit; if the
    session owner rolls back, neither the HP change nor the turn change persists."""
    cid, uid = await _seed_campaign()
    try:
        player = _make_player(uid, hp=30)
        state = _make_state(cid, player)

        # Commit baseline state A: hp 30, turn 0.
        async with _Session() as db:
            state.turn_index = 0
            await StateService.save_game_state(cid, state, db)
            await db.commit()

        # Stage a destructive change (hp 1, turn 9) then ROLL BACK (mid-op failure).
        async with _Session() as db:
            player.hp_current = 1
            state.turn_index = 9
            await StateService.save_game_state(cid, state, db)
            await db.rollback()

        # Fresh read must still be state A — no half-commit across the two tables.
        async with _Session() as db:
            loaded = await StateService.get_game_state(cid, db)
            assert loaded.turn_index == 0
            assert loaded.party[0].hp_current == 30
            assert await _row_count(db, cid) == 1
    finally:
        await _cleanup_campaign(cid, uid)


async def test_scalar_columns_track_blob_on_rename():
    """The characters scalar columns (name/role) are rewritten from the entity on UPDATE,
    so they never drift from the blob that hydration overlays them over."""
    cid, uid = await _seed_campaign()
    try:
        player = _make_player(uid, name="Aria")
        state = _make_state(cid, player)
        async with _Session() as db:
            await StateService.save_game_state(cid, state, db)
            await db.commit()

        # Rename + re-class, then save again (UPDATE path).
        async with _Session() as db:
            player.name = "Aria the Renamed"
            player.role = "Sorcerer"
            await StateService.save_game_state(cid, state, db)
            await db.commit()

        async with _Session() as db:
            col_name = await db.scalar(text("SELECT name FROM characters WHERE id=:id"), {"id": player.id})
            col_role = await db.scalar(text("SELECT role FROM characters WHERE id=:id"), {"id": player.id})
            assert col_name == "Aria the Renamed"
            assert col_role == "Sorcerer"
            loaded = await StateService.get_game_state(cid, db)
            assert loaded.party[0].name == "Aria the Renamed"
            assert loaded.party[0].role == "Sorcerer"
    finally:
        await _cleanup_campaign(cid, uid)


async def test_hydration_raises_on_corrupt_sheet_data():
    """Corrupt persisted JSON must fail loud, not silently hydrate to all-default stats."""
    cid, uid = await _seed_campaign()
    try:
        char_id = str(uuid.uuid4())
        skeleton = {
            "session_id": cid, "version": 1, "turn_index": 0, "phase": "exploration",
            "location": {"name": "R", "description": "d", "walkable_cells": [],
                         "party_locations": [], "interactables": []},
            "party": [char_id], "enemies": [], "npcs": [], "vessels": [],
        }
        async with _Session() as db:
            await db.execute(
                text("INSERT INTO characters (id, user_id, campaign_id, name, role, sheet_data) "
                     "VALUES (:id, :uid, :cid, 'Broken', 'Wizard', :sd)"),
                {"id": char_id, "uid": uid, "cid": cid, "sd": "{not valid json"},
            )
            await db.execute(
                text("INSERT INTO game_states (id, campaign_id, turn_index, phase, state_data) "
                     "VALUES (:id, :cid, 0, 'exploration', :sd)"),
                {"id": str(uuid.uuid4()), "cid": cid, "sd": json.dumps(skeleton)},
            )
            await db.commit()

        async with _Session() as db:
            with pytest.raises(ValueError):
                await StateService.get_game_state(cid, db)
    finally:
        await _cleanup_campaign(cid, uid)


async def test_inventory_persists_as_id_strings():
    """Inventory is normalized to canonical id-strings at the persistence boundary, even if a
    dict item (as equip paths can transiently produce) sneaks into the in-memory list."""
    cid, uid = await _seed_campaign()
    try:
        player = _make_player(uid)
        # Mixed list: a string id + a dict item. validate_assignment is off on the model,
        # so this mirrors what equip/unequip can leave in memory.
        player.inventory = ["wpn-dagger", {"id": "arm-leather", "name": "Leather Armor"}]
        state = _make_state(cid, player)
        async with _Session() as db:
            await StateService.save_game_state(cid, state, db)
            await db.commit()

        async with _Session() as db:
            sd = await db.scalar(text("SELECT sheet_data FROM characters WHERE id=:id"), {"id": player.id})
            persisted_inv = json.loads(sd)["inventory"]
            assert persisted_inv == ["wpn-dagger", "arm-leather"]
            assert all(isinstance(x, str) for x in persisted_inv)

            loaded = await StateService.get_game_state(cid, db)
            assert loaded.party[0].inventory == ["wpn-dagger", "arm-leather"]
    finally:
        await _cleanup_campaign(cid, uid)
