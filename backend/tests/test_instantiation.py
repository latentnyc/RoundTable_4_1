
import asyncio
import os
from sqlalchemy import text
from db.session import AsyncSessionLocal
from app.services.campaign_loader import instantiate_campaign
from uuid import uuid4

async def verify_instantiation():
    async with AsyncSessionLocal() as db:
        try:
            # 1. Ensure template exists (Wait, loader already ran)
            template_id = "adv_001_rats"

            # 2. Create Dummy Campaign
            campaign_id = str(uuid4())
            gm_id = "test_gm"
            print(f"Creating test campaign: {campaign_id}")
            await db.execute(text("""
                INSERT INTO campaigns (id, name, gm_id, status, template_id)
                VALUES (:id, :name, :gm_id, :status, :template_id)
            """), {
                "id": campaign_id,
                "name": "Test Campaign - Rats1",
                "gm_id": gm_id,
                "status": "test",
                "template_id": template_id
            })

            # 3. Instantiate
            await instantiate_campaign(db, campaign_id, template_id)
            await db.commit()

            # 4. Verify Counts
            counts = {}
            for table in ["npcs", "locations", "quests", "items", "monsters"]:
                 result = await db.execute(text(f"SELECT COUNT(*) FROM {table} WHERE campaign_id = :cid"), {"cid": campaign_id})
                 counts[table] = result.scalar()

            print("\n---------- Verification Results ----------")
            print(f"Campaign ID: {campaign_id}")
            print(f"Template ID: {template_id}")
            for table, count in counts.items():
                print(f"  - {table}: {count}")

            if all(c > 0 for c in counts.values()):
                print("\nSUCCESS: All tables populated!")
            else:
                print("\nFAILURE: Some tables empty!")

        except Exception as e:
            await db.rollback()
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(verify_instantiation())
