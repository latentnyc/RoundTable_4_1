import asyncio
import os
import sys
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

# Path to actual DB
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:roundtable_dev_2024@127.0.0.1:5432/postgres")

async def verify_schema():

    engine = create_async_engine(DATABASE_URL, echo=False)

    async with engine.connect() as conn:
        print(f"Connected to DB")

        tables = ["characters", "monsters", "npcs"]
        for t in tables:
            print(f"\n--- Table: {t} ---")
            try:
                # PostgreSQL information schema
                result = await conn.execute(text(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{t}'"))
                columns = result.fetchall()
                if not columns:
                    print(f"Table {t} NOT FOUND or empty schema.")
                else:
                    for col in columns:
                        # column_name, data_type
                        print(f"  - {col[0]} ({col[1]})")
            except Exception as e:
                print(f"Fatal Error: {e}")
                import sys; sys.exit(1)

if __name__ == "__main__":
    asyncio.run(verify_schema())
