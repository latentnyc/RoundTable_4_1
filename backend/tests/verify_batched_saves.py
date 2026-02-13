
import asyncio
import os
import sys
import json
from uuid import uuid4
from unittest.mock import AsyncMock, patch, MagicMock

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Set Env to use test DB
TEST_DB_PATH = "test_batched_saves.db"
if os.path.exists(TEST_DB_PATH):
    os.remove(TEST_DB_PATH)
os.environ["SQLITE_DB_PATH"] = TEST_DB_PATH
os.environ["DATABASE_URL"] = ""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from db.schema import metadata
from app.models import GameState, Player, Enemy, Coordinates, Location
from app.services.game_service import GameService
from app.services.turn_manager import TurnManager

async def setup_db():
    engine = create_async_engine(f"sqlite+aiosqlite:///{TEST_DB_PATH}", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
    SessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return SessionLocal

async def seed_campaign(session_factory):
    async with session_factory() as db:
        from sqlalchemy import text
        cid = str(uuid4())
        
        # 1. Player (Inactive)
        pid = str(uuid4())
        p = Player(id=pid, name="Hero", is_ai=False, role="Fighter", hp_current=20, hp_max=20, position=Coordinates(q=0,r=0,s=0))
        
        # 2. Enemies (Active Sequence)
        # e.g. Goblin1, Goblin2, Goblin3
        enemies = []
        for i in range(3):
            eid = str(uuid4())
            e = Enemy(id=eid, name=f"Goblin{i}", is_ai=True, type="Goblin", hp_current=5, hp_max=5, position=Coordinates(q=2,r=0,s=-2+i))
            enemies.append(e)
            
            # Insert into NPCs/Monsters table for lookup
            npc_data = {"stats": {"hp": 5, "ac": 10, "attacks": [{"name": "Stab", "damage": "1d4"}]}, "hostile": True}
            await db.execute(
                text("INSERT INTO npcs (id, campaign_id, source_id, name, role, data) VALUES (:id, :cid, 'goblin', :name, 'Monster', :data)"),
                {"id": eid, "cid": cid, "name": f"Goblin{i}", "data": json.dumps(npc_data)}
            )

        # Turn Order: Goblin0 -> Goblin1 -> Goblin2 -> Hero
        # We start at index 0 (Goblin0)
        turn_order = [e.id for e in enemies] + [pid]
        
        gs = GameState(
            session_id=cid, 
            party=[p], 
            enemies=enemies, 
            npcs=[], 
            turn_order=turn_order,
            turn_index=0,
            active_entity_id=enemies[0].id,
            phase='combat',
            location=Location(name="Test", description="Test Location")
        )
        
        await db.execute(
            text("INSERT INTO game_states (id, campaign_id, state_data) VALUES (:id, :cid, :data)"),
            {"id": str(uuid4()), "cid": cid, "data": gs.model_dump_json()}
        )
        
        await db.commit()
        return cid, gs

async def run_test():
    print("Setting up...")
    SessionLocal = await setup_db()
    cid, initial_gs = await seed_campaign(SessionLocal)
    
    # Mock SIO
    sio = AsyncMock()
    
    # Spy on GameService.save_game_state
    # We need to wrap the original method to let it run, but count calls?
    # Actually, we can just spy on it using SideEffect or Wraps?
    # But since it's a static method on a class, we can patch it.
    
    original_save = GameService.save_game_state
    
    with patch('app.services.game_service.GameService.save_game_state', side_effect=original_save) as mock_save:
         with patch('app.services.narrator_service.NarratorService.narrate', new_callable=AsyncMock): # Skip Narration
            
            print("Starting Turn Loop...")
            
            async with SessionLocal() as db:
                # Run _turn_loop
                # It should process Goblin0, Goblin1, Goblin2. 
                # Then it hits Hero (index 3), sees it's Human, and breaks.
                # Total steps: 3 AI turns.
                # Expected save_game_state calls: 1 (at the very end).
                
                # We pass the initial state
                await TurnManager._turn_loop(cid, sio, db, initial_gs, advance_first=False)
                # advance_first=False because we set active_entity to Goblin0 already.
            
            call_count = mock_save.call_count
            print(f"GameService.save_game_state called {call_count} times.")
            
            # Check calls
            # Debug info
            # for call in mock_save.call_args_list:
            #    print(call)
            
            if call_count == 1:
                print("SUCCESS: Batched saves verified (1 call).")
            elif call_count == 0:
                 print("FAILURE: No saves occurred?")
                 exit(1)
            else:
                print(f"FAILURE: Too many saves ({call_count}). Optimization failed.")
                exit(1)

if __name__ == "__main__":
    asyncio.run(run_test())
    if os.path.exists(TEST_DB_PATH):
        try: os.remove(TEST_DB_PATH)
        except: pass
