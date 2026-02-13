import asyncio
import os
import sys
import json
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Set Env to use test DB
TEST_DB_PATH = "test_game_loop.db"
if os.path.exists(TEST_DB_PATH):
    os.remove(TEST_DB_PATH)
os.environ["SQLITE_DB_PATH"] = TEST_DB_PATH
os.environ["DATABASE_URL"] = "" # Force SQLite

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from db.schema import metadata
from app.models import GameState, Player, NPC, Location, Coordinates
from app.socket.handlers.chat import handle_chat_message

# Mock Services to avoid Side Effects (LLM calls)
# We need to patch them where they are IMPORTED in the modules we test
# or globally if possible.
# Since we import handle_chat_message, which imports CommandService, etc.

async def setup_db():
    engine = create_async_engine(f"sqlite+aiosqlite:///{TEST_DB_PATH}", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
    SessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return SessionLocal

async def seed_data(session_factory):
    async with session_factory() as db:
        from sqlalchemy import text
        
        cid = str(uuid4())
        uid1 = str(uuid4())
        uid2 = str(uuid4())
        
        # Campaign
        await db.execute(text("INSERT INTO campaigns (id, name, gm_id) VALUES (:id, 'Loop Test', :gm)"), {"id": cid, "gm": uid1})
        
        # Player 1 (Fighter)
        pid1 = str(uuid4())
        p1 = Player(
            id=pid1, name="Alice", user_id=uid1, hp_current=20, hp_max=20, ac=12,
            position=Coordinates(q=0,r=0,s=0),
            is_ai=False, role="Fighter" # Added required fields
        )
        await db.execute(
            text("INSERT INTO characters (id, user_id, campaign_id, name, role, sheet_data, control_mode) VALUES (:id, :uid, :cid, 'Alice', 'Fighter', :data, 'human')"),
            {"id": pid1, "uid": uid1, "cid": cid, "data": json.dumps(p1.sheet_data)}
        )
        
        # Player 2 (Cleric)
        pid2 = str(uuid4())
        p2 = Player(
            id=pid2, name="Bob", user_id=uid2, hp_current=18, hp_max=18, ac=11,
            position=Coordinates(q=1,r=0,s=-1),
            is_ai=False, role="Cleric" # Added required fields
        )
        await db.execute(
            text("INSERT INTO characters (id, user_id, campaign_id, name, role, sheet_data, control_mode) VALUES (:id, :uid, :cid, 'Bob', 'Cleric', :data, 'human')"),
            {"id": pid2, "uid": uid2, "cid": cid, "data": json.dumps(p2.sheet_data)}
        )
        
        # Enemy (Goblin)
        eid = str(uuid4())
        npc_data = {"stats": {"hp": 10, "ac": 12, "attacks": [{"name": "Stab", "bonus": 4, "damage": "1d6"}]}}
        # Create Enemy Object for GameState
        from app.models import Enemy
        goblin = Enemy(
            id=eid, name="Goblin", is_ai=True, hp_current=10, hp_max=10, ac=12,
            position=Coordinates(q=2,r=0,s=-2),
            type="Goblin"
        )
        
        await db.execute(
            text("INSERT INTO npcs (id, campaign_id, source_id, name, role, data) VALUES (:id, :cid, 'goblin', 'Goblin', 'Monster', :data)"),
            {"id": eid, "cid": cid, "data": json.dumps(npc_data)}
        )
        
        # Game State
        # We assume the goblin is already "spawned" as an enemy in the state for combat to work easiest
        gs = GameState(session_id=cid, party=[p1, p2], npcs=[], enemies=[goblin], location=Location(name="Test Room", description="Tests")) 
        
        await db.execute(
            text("INSERT INTO game_states (id, campaign_id, state_data) VALUES (:id, :cid, :data)"),
            {"id": str(uuid4()), "cid": cid, "data": gs.model_dump_json()}
        )
        
        await db.commit()
        return cid, pid1, pid2, eid, uid1, uid2

async def run_test():
    print("Setting up DB...")
    SessionLocal = await setup_db()
    
    cid, pid1, pid2, eid, uid1, uid2 = await seed_data(SessionLocal)
    print(f"Data Seeded. Campaign: {cid}")
    
    # Mock SIO
    sio = AsyncMock()
    # Mock connected users
    connected_users = {
        "sid1": {"user_id": uid1, "campaign_id": cid},
        "sid2": {"user_id": uid2, "campaign_id": cid}
    }
    
    # helper to print system messages
    def print_sio_events():
        print("--- SIO EVENTS ---")
        for call in sio.emit.call_args_list:
            args, kwargs = call
            event = args[0]
            data = kwargs.get('data') or (args[1] if len(args) > 1 else {})
            room = kwargs.get('room')
            if event == 'system_message':
                print(f"[SYS] {data.get('content')}")
            elif event == 'chat_message':
                print(f"[{data.get('sender_name')}]: {data.get('content')}")
        print("------------------")
        sio.emit.reset_mock()

    # PATCH SERVICES
    # We want to patch AIService to return dummy narration
    with patch('app.services.narrator_service.NarratorService.narrate', new_callable=AsyncMock) as mock_narrate:
        
        # 1. Start Combat (Alice Attacks Goblin)
        print("\n=== STEP 1: Alice Starts Combat ===")
        msg1 = {"content": "@attack Goblin", "sender_name": "Alice", "sender_id": pid1}
        await handle_chat_message("sid1", msg1, sio, connected_users)
        
        print_sio_events()
        
        # Verify Combat Started
        # We need to check the DB for GameState phase
        async with SessionLocal() as db:
            from app.services.game_service import GameService
            gs = await GameService.get_game_state(cid, db=db)
            print(f"Phase: {gs.phase}")
            assert gs.phase == 'combat'
            print(f"Active Entity: {gs.active_entity_id}")
            
            active_id = gs.active_entity_id
            turn_order = gs.turn_order
            print(f"Turn Order: {turn_order}")
            
        # 2. Simulate Next Turn(s)
        # If it's Alice's turn, she just attacked. Wait, @attack triggers 'process_turn' if it started combat?
        # In CommandService.handle_attack:
        # If combat starts -> rolls initiative -> sets active_id -> notifies -> calls process_turn (if AI).
        # If it was Alice's turn (she won initiative), she attacks.
        # If she WON initiative, she attacks immediately? No.
        # Logic: 
        #  - Start Combat returns active_id.
        #  - if active_id != sender_id (Alice), then Alice shouldn't be attacking yet?
        #  - Wait, the code says: "Initiative Rolled! It is X's turn first." and returns.
        # So if Alice is NOT first, her attack is ignored (or warned).
        # If Alice IS first, she attacks.
        
        # Let's see who is active.
        next_actor = None
        if active_id == pid1:
            print("Alice won initiative and attacked.")
            # She attacked. Turn updates?
            # CommandService.handle_attack -> resolution_attack -> advance_turn.
            # So the turn should have advanced to the NEXT person.
            pass
        else:
            print(f"Someone else ({active_id}) won initiative.")
            # If someone else won, Alice's attack might have been rejected?
            # Or did she effectively start combat, roll init, and if she wasn't first, the system stopped her?
            # CommandService line 102: if start_res['active_entity_id'] != sender_id ... return.
            # So if she wasn't first, her attack was NOT processed as an attack, just as a combat starter.
            pass
            
        # 3. Simulate another action
        # Let's say we want to force Alice to attack again (if it's her turn now)
        # Or if it's Bob's turn.
        
        async with SessionLocal() as db:
             gs = await GameService.get_game_state(cid, db=db)
             active_id = gs.active_entity_id
             print(f"Current Active Entity: {active_id}")
        
        if active_id == pid2:
            print("\n=== STEP 2: Bob's Turn ===")
            msg2 = {"content": "@attack Goblin", "sender_name": "Bob", "sender_id": pid2}
            await handle_chat_message("sid2", msg2, sio, connected_users)
            print_sio_events()
            
        elif active_id == eid:
            print("\n=== STEP 2: Goblin's Turn (AI) ===")
            # AI turn should have been triggered automatically by TurnManager?
            pass
            
    print("\nTest Finished.")

if __name__ == "__main__":
    asyncio.run(run_test())
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except:
             pass
