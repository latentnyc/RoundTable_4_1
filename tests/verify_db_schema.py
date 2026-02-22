import asyncio
import sys
import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text, inspect

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from db.schema import metadata

async def test_schema():
    print("Testing schema creation on PostgreSQL DB...")

    url = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:roundtable_dev_2024@127.0.0.1:5432/postgres")
    engine = create_async_engine(url, echo=False)

    try:
        async with engine.begin() as conn:
            await conn.run_sync(metadata.create_all)
            print("Tables created.")

            print("Tables created.")

            def get_cols(table):
                return f"SELECT column_name as name FROM information_schema.columns WHERE table_name = '{table}'"

            # Check Campaigns
            print("Checking 'campaigns' table...")
            res = await conn.execute(text(get_cols("campaigns")))
            columns = [row.name for row in res.fetchall()]
            required = ['template_id', 'total_input_tokens', 'query_count', 'description']
            for req in required:
                if req in columns:
                    print(f"  [OK] Found {req}")
                else:
                    print(f"  [FAIL] Missing {req}")

            # Check Monsters
            print("Checking 'monsters' table...")
            res = await conn.execute(text(get_cols("monsters")))
            columns = [row.name for row in res.fetchall()]
            required = ['campaign_id', 'template_id']
            for req in required:
                if req in columns:
                    print(f"  [OK] Found {req}")
                else:
                    print(f"  [FAIL] Missing {req}")

            # Check Items
            print("Checking 'items' table...")
            res = await conn.execute(text(get_cols("items")))
            columns = [row.name for row in res.fetchall()]
            required = ['campaign_id', 'template_id']
            for req in required:
                if req in columns:
                     print(f"  [OK] Found {req}")
                else:
                     print(f"  [FAIL] Missing {req}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

    await engine.dispose()

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_schema())
