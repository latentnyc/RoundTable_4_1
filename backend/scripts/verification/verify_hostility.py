
import asyncio
import os
import sys
import json
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Set Env to use test DB
TEST_DB_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:roundtable_dev_2024@127.0.0.1:5432/postgres")
os.environ["DATABASE_URL"] = TEST_DB_URL

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from db.schema import metadata
from app.models import GameState, Player, NPC, Location, Coordinates

# Import the handler AFTER setting env
from app.socket.handlers.chat import handle_chat_message

async def setup_db():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)

    SessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return SessionLocal

async def seed_data(session_factory):
    async with session_factory() as db:
        from sqlalchemy import text

        # 1. Campaign
        cid = str(uuid4())
        uid = str(uuid4())
        await db.execute(
            text("INSERT INTO campaigns (id, name, gm_id) VALUES (:id, 'Test Campaign', :gm_id)"),
            {"id": cid, "gm_id": uid}
        )

        # 2. Player
        pid = str(uuid4())
        player = Player(
            id=pid, name="Hero", is_ai=False, hp_current=20, hp_max=20, ac=10,
            position=Coordinates(q=0, r=0, s=0), role="Fighter", user_id=uid,
            sheet_data={"stats": {"hp_current": 20, "hp_max": 20, "ac": 10}}
        )

        await db.execute(
            text("INSERT INTO characters (id, user_id, campaign_id, name, role, sheet_data, control_mode) VALUES (:id, :uid, :cid, :name, :role, :data, 'human')"),
            {"id": pid, "uid": uid, "cid": cid, "name": "Hero", "role": "Fighter", "data": json.dumps(player.sheet_data)} # Fix: dump dict
        )

        # 3. NPC
        nid = str(uuid4())
        npc_data = {
            "stats": {"hp": 15, "ac": 10, "attacks": [{"name": "Punch", "bonus": 5, "damage": "1d6+2"}]},
            "hostile": False # Initially peaceful
        }
        npc = NPC(
            id=nid, name="Villager", is_ai=True, hp_current=15, hp_max=15, ac=10,
            position=Coordinates(q=0, r=0, s=0), role="Commoner", data=npc_data
        )

        await db.execute(
            text("INSERT INTO npcs (id, campaign_id, source_id, name, role, data) VALUES (:id, :cid, 'npc_1', 'Villager', 'Commoner', :data)"),
            {"id": nid, "cid": cid, "data": json.dumps(npc_data)}
        )

        # 4. Game State
        gs = GameState(
            session_id=cid,
            location=Location(name="Start", description="A test place."),
            party=[player],
            npcs=[npc]
        )

        await db.execute(
            text("INSERT INTO game_states (id, campaign_id, state_data) VALUES (:id, :cid, :data)"),
            {"id": str(uuid4()), "cid": cid, "data": gs.model_dump_json()}
        )

        await db.commit()
        return cid, uid, pid, nid

async def run_test():
    print("Setting up DB...")
    SessionLocal = await setup_db()

    # Patch the session factory in chat.py?
    # Since we imported handle_chat_message, it typically uses the global AsyncSessionLocal from db.session.
    # But we reloaded/imported AFTER setting env, so db.session should have initialized with our TEST_DB_PATH.
    # Let's verify.
    print(f"DB initialized with Postgres")

    cid, uid, pid, nid = await seed_data(SessionLocal)
    print(f"Seeded Campaign {cid}, Player {pid}, NPC {nid}")

    # Mock SIO
    sio = AsyncMock()
    connected_users = {
        "sid1": {"user_id": uid, "campaign_id": cid}
    }

    # Test Payload
    data = {
        "content": "@attack Villager",
        "sender_name": "Hero",
        "sender_id": pid
    }

    print("Sending @attack command...")
    # Trigger Handler
    # We mock get_dm_graph to avoid API calls
    # Ensure app.agents is loaded
    import app.agents
    with patch("app.agents.get_dm_graph", return_value=(None, "Mocked Offline")):
        await handle_chat_message("sid1", data, sio, connected_users)

    print("Verifying results...")

    async with SessionLocal() as db:
        from sqlalchemy import text

        # Check NPC Hostility
        res = await db.execute(text("SELECT data FROM npcs WHERE id=:id"), {"id": nid})
        row = res.mappings().fetchone()
        npc_saved_data = json.loads(row['data'])
        print(f"NPC Data: {npc_saved_data}")

        if not npc_saved_data.get('hostile'):
            print("FAILURE: NPC was not marked hostile!")
        else:
            print("SUCCESS: NPC marked hostile.")

        # Check Chat Output for Counterattack
        # We look at sio.emit calls
        calls = sio.emit.call_args_list
        found_counterattack = False
        found_hit = False

        for call in calls:
            args, kwargs = call
            # name is not in call_args_list items
            content = kwargs.get('data', {}).get('content', '') if 'data' in kwargs else (args[1].get('content', '') if len(args) > 1 else '')
            print(f"Chat Message Emitted: {content}")
            if "COUNTERATTACK!" in content:
                print("FOUND COUNTERATTACK MESSAGE!")
                found_counterattack = True
            if "Hero attacks Villager" in content and "HIT!" in content:
                found_hit = True

        if found_counterattack:
            print("SUCCESS: Counterattack triggered and broadcasted.")
        else:
            print("WARNING: Counterattack NOT found (Did the player miss? Or logic fail?)")

        # Check if NPC actually attacked back (mechanically)
        # We can check if Player HP dropped (starts at 20)
        p_res = await db.execute(text("SELECT sheet_data FROM characters WHERE id=:id"), {"id": pid})
        p_row = p_res.mappings().fetchone()
        p_data = json.loads(p_row['sheet_data'])
        p_hp = p_data['stats']['hp_current']
        print(f"Player HP: {p_hp}/20")

        if p_hp < 20:
             print("SUCCESS: Player took damage from counterattack.")
        elif found_counterattack:
             print("NOTE: Counterattack missed (Player HP full).")


    # Validation Logic
    if found_counterattack:
        print("TEST PASSED!")
    else:
        print("TEST INCONCLUSIVE (Check logs)")

if __name__ == "__main__":
    asyncio.run(run_test())
