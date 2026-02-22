import asyncio
import sys
import os
import json
from uuid import uuid4

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.game_service import GameService
from app.models import GameState, Player, Enemy, Coordinates, Location
from db.session import engine, AsyncSessionLocal
from db.schema import metadata, profiles, campaigns
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import insert

async def verify_refactor():
    print("Starting verification...")

    # 1. Setup DB (InMemory or Local)
    # We use the configured engine from db.session
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)

    async with AsyncSessionLocal() as db:
        # Create dummy Profile and Campaign
        user_id = str(uuid4())
        campaign_id = str(uuid4())

        await db.execute(insert(profiles).values(
            id=user_id,
            username="test_user",
            api_key="test_key"
        ))

        await db.execute(insert(campaigns).values(
            id=campaign_id,
            name="Test Campaign",
            gm_id=user_id
        ))
        await db.commit()

        # 2. Create Dummy State
        p1 = Player(
            id=str(uuid4()),
            name="TestHero",
            role="Fighter",
            hp_current=10,
            hp_max=12,
            position=Coordinates(q=0,r=0,s=0),
            user_id=user_id,
            is_ai=False
        )

        e1 = Enemy(
            id=str(uuid4()),
            name="TestGoblin",
            type="Goblin",
            hp_current=5,
            hp_max=7,
            position=Coordinates(q=1,r=-1,s=0),
            identified=False,
            is_ai=True
        )

        initial_state = GameState(
            id=str(uuid4()),
            campaign_id=campaign_id,
            session_id=str(uuid4()),
            location=Location(name="TestLoc", description="A test location"),
            turn_index=1,
            phase="combat",
            party=[p1],
            enemies=[e1],
            npcs=[],
            vessels=[]
        )

        print(f"Saving state for campaign {campaign_id}...")
        try:
            await GameService.save_game_state(campaign_id, initial_state, db)
            await db.commit()
            print("Save successful.")
        except Exception as e:
            print(f"SAVE FAILED: {e}")
            return

        # 3. Load State
        print("Loading state...")
        try:
            loaded_state = await GameService.get_game_state(campaign_id, db)
            print("Load successful.")
        except Exception as e:
            print(f"LOAD FAILED: {e}")
            return

        # 4. Verification
        print("Verifying data consistency...")

        # Verify Party
        if len(loaded_state.party) != 1:
            print(f"FAIL: Expected 1 party member, got {len(loaded_state.party)}")
        else:
            lp = loaded_state.party[0]
            if lp.id == p1.id and lp.name == p1.name and lp.hp_current == p1.hp_current:
                print("PASS: Party member verified.")
            else:
                print(f"FAIL: Party member mismatch. Expected {p1}, got {lp}")

        # Verify Enemy
        if len(loaded_state.enemies) != 1:
            print(f"FAIL: Expected 1 enemy, got {len(loaded_state.enemies)}")
        else:
            le = loaded_state.enemies[0]
            # ID, Name, HP, Identified status
            if le.id == e1.id and le.name == e1.name and le.hp_current == e1.hp_current:
                print("PASS: Enemy basic data verified.")
            else:
                print(f"FAIL: Enemy mismatch. Expected {e1}, got {le}")

            if le.identified != e1.identified:
                 print(f"FAIL: Enemy identified status mismatch. Expected {e1.identified}, got {le.identified}")
            else:
                 print("PASS: Enemy identified status verified.")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(verify_refactor())
