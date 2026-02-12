import asyncio
import sys
import os
import json
from uuid import uuid4

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from sqlalchemy import text
from db.session import AsyncSessionLocal
from app.models import NPC, Coordinates

async def test_npc_persistence():
    async with AsyncSessionLocal() as db:
        print("Setting up test data...")
        # 1. Create a dummy campaign and NPC
        cid = str(uuid4())
        nid = str(uuid4())

        # Create persistent NPC
        initial_data = {
            "stats": {"hp": 50, "ac": 12},
            "role": "Test Dummy",
            "schedule": []
        }
        await db.execute(
            text("INSERT INTO npcs (id, campaign_id, name, role, data) VALUES (:id, :cid, :name, :role, :data)"),
            {"id": nid, "cid": cid, "name": "Persistence Dummy", "role": "Dummy", "data": json.dumps(initial_data)}
        )
        await db.commit()

        # 2. Simulate the logic from chat.py:
        # - Load NPC
        # - Update HP
        # - Persist

        print("Simulating damage update...")
        # Fetch fresh (as if loading GameState)
        res = await db.execute(text("SELECT data FROM npcs WHERE id = :id"), {"id": nid})
        row = res.mappings().fetchone()
        current_data = json.loads(row['data'])

        # Update HP
        new_hp = 35
        current_data['stats']['hp'] = new_hp # Logic from chat.py

        # Persist
        await db.execute(
            text("UPDATE npcs SET data = :data WHERE id = :id"),
            {"data": json.dumps(current_data), "id": nid}
        )
        await db.commit()

        # 3. Verify
        print("Verifying persistence...")
        res = await db.execute(text("SELECT data FROM npcs WHERE id = :id"), {"id": nid})
        row = res.mappings().fetchone()
        final_data = json.loads(row['data'])

        saved_hp = final_data['stats']['hp']
        print(f"Initial HP: 50")
        print(f"Expected HP: {new_hp}")
        print(f"Saved HP:   {saved_hp}")

        if saved_hp == new_hp:
            print("SUCCESS: NPC HP verified in database.")
        else:
            print("FAILED: DB does not match expected HP.")

        # Cleanup
        print("Cleaning up...")
        await db.execute(text("DELETE FROM npcs WHERE id = :id"), {"id": nid})
        await db.commit()

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_npc_persistence())
