import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:roundtable_dev_2024@127.0.0.1:5432/postgres")

async def main():
    print(f"Connecting to {DATABASE_URL}")
    engine = create_async_engine(DATABASE_URL)

    async with engine.connect() as conn:
        print("\n--- PROFILES ---")
        try:
            result = await conn.execute(text("SELECT id, username, status FROM profiles"))
            profiles = result.mappings().all()
            for p in profiles:
                print(p)
        except Exception as e:
            print(f"Error querying profiles: {e}")

        print("\n--- CAMPAIGNS ---")
        try:
            result = await conn.execute(text("SELECT id, name, gm_id FROM campaigns"))
            campaigns = result.mappings().all()
            for c in campaigns:
                print(c)
        except Exception as e:
             print(f"Error querying campaigns: {e}")

        print("\n--- PARTICIPANTS ---")
        try:
            result = await conn.execute(text("SELECT * FROM campaign_participants"))
            parts = result.mappings().all()
            for p in parts:
                print(p)
            if not parts:
                print("No participants found!")
        except Exception as e:
             print(f"Error querying participants: {e}")

        print("\n--- JOIN TEST ---")
        try:
            # Hardcoded ID from output
            campaign_id = '895263fd-472a-43e5-84be-c6abe239a1bf'
            # ... (existing JOIN query)
            query = text("""
                SELECT cp.user_id as id, cp.role, cp.status, cp.joined_at, p.username
                FROM campaign_participants cp
                JOIN profiles p ON cp.user_id = p.id
                WHERE cp.campaign_id = :cid
                ORDER BY cp.joined_at ASC
            """)
            result = await conn.execute(query, {"cid": campaign_id})
            rows = result.mappings().all()
            for r in rows:
                print(r)

            if rows:
                user_ids = [r['id'] for r in rows]
                print(f"\n--- CHARACTERS TEST (Users: {user_ids}) ---")
                c_query = text("""
                    SELECT id, user_id, name, race, role as class_name, level
                    FROM characters
                    WHERE campaign_id = :cid
                """)
                # Testing the bindparam logic
                try:
                    c_result = await conn.execute(c_query, {"cid": campaign_id})
                    chars = c_result.mappings().all()
                    for c in chars:
                        print(c)
                except Exception as ce:
                    print(f"Character Query Failed: {ce}")

            if not rows:
                print("JOIN returned no rows!")
        except Exception as e:
             print(f"Error testing JOIN: {e}")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
