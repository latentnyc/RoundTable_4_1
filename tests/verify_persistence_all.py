import asyncio
import sys
import os
import json
from uuid import uuid4

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from sqlalchemy import text
from db.session import AsyncSessionLocal

async def test_persistence():
    async with AsyncSessionLocal() as db:
        print("Setting up test data...")
        cid = str(uuid4())
        uid = str(uuid4()) # user id
        pid = str(uuid4()) # profile id = uid

        # 1. Create Profile
        await db.execute(text("INSERT INTO profiles (id, username) VALUES (:id, :name)"), {"id": uid, "name": "TestUser"})

        # 2. Setup Character
        char_id = str(uuid4())
        initial_char_data = {"stats": {"hp": 50, "hp_current": 50}, "background": "Test"}
        await db.execute(
            text("""INSERT INTO characters (id, user_id, campaign_id, name, role, sheet_data, backstory)
                    VALUES (:id, :uid, :cid, :name, :role, :data, 'None')"""),
            {"id": char_id, "uid": uid, "cid": cid, "name": "Hero", "role": "Fighter", "data": json.dumps(initial_char_data)}
        )

        # 3. Setup Monster
        mon_id = str(uuid4())
        initial_mon_data = {"stats": {"hp": 40, "ac": 15}, "type": "beast"}
        await db.execute(
            text("INSERT INTO monsters (id, campaign_id, name, type, data) VALUES (:id, :cid, :name, :type, :data)"),
            {"id": mon_id, "cid": cid, "name": "Rat Guard", "type": "beast", "data": json.dumps(initial_mon_data)}
        )
        await db.commit()

        print("Simulating damage updates logic from chat.py...")

        # --- PLAYER UPDATE SIMULATION ---
        new_hp_char = 30
        c_res = await db.execute(text("SELECT sheet_data FROM characters WHERE id = :id"), {"id": char_id})
        c_row = c_res.mappings().fetchone()
        c_data = json.loads(c_row['sheet_data'])
        if 'stats' not in c_data: c_data['stats'] = {}
        c_data['stats']['hp_current'] = new_hp_char
        await db.execute(text("UPDATE characters SET sheet_data = :data WHERE id = :id"), {"data": json.dumps(c_data), "id": char_id})

        # --- MONSTER UPDATE SIMULATION ---
        new_hp_mon = 20
        m_res = await db.execute(text("SELECT data FROM monsters WHERE id = :id"), {"id": mon_id})
        m_row = m_res.mappings().fetchone()
        m_data = json.loads(m_row['data'])
        if 'stats' not in m_data: m_data['stats'] = {}
        m_data['stats']['hp'] = new_hp_mon
        await db.execute(text("UPDATE monsters SET data = :data WHERE id = :id"), {"data": json.dumps(m_data), "id": mon_id})

        await db.commit()

        # --- VERIFICATION ---
        print("Verifying persistence...")

        # Check Character
        c_res = await db.execute(text("SELECT sheet_data FROM characters WHERE id = :id"), {"id": char_id})
        c_data_final = json.loads(c_res.mappings().fetchone()['sheet_data'])
        saved_hp_char = c_data_final['stats']['hp_current']

        # Check Monster
        m_res = await db.execute(text("SELECT data FROM monsters WHERE id = :id"), {"id": mon_id})
        m_data_final = json.loads(m_res.mappings().fetchone()['data'])
        saved_hp_mon = m_data_final['stats']['hp']

        success = True
        print(f"Character: Expected {new_hp_char}, Got {saved_hp_char}")
        if saved_hp_char != new_hp_char: success = False

        print(f"Monster:   Expected {new_hp_mon}, Got {saved_hp_mon}")
        if saved_hp_mon != new_hp_mon: success = False

        if success:
            print("SUCCESS: Persistence verified for Player and Monster.")
        else:
            print("FAILED: Data mismatch.")

        # Cleanup
        await db.execute(text("DELETE FROM characters WHERE id = :id"), {"id": char_id})
        await db.execute(text("DELETE FROM monsters WHERE id = :id"), {"id": mon_id})
        await db.execute(text("DELETE FROM profiles WHERE id = :id"), {"id": uid})
        await db.commit()

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_persistence())
