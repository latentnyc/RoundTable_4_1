import asyncio
import json
import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:roundtable_dev_2024@127.0.0.1:5432/postgres")

async def main():
    engine = create_async_engine(DATABASE_URL)
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT name, sheet_data FROM characters LIMIT 1"))
        row = result.fetchone()
        if row:
            print(f"Name: {row[0]}")
            try:
                data = json.loads(row[1])
                print(json.dumps(data, indent=2))
            except json.JSONDecodeError:
                print("Invalid JSON")
        else:
            print("No characters found")

if __name__ == "__main__":
    asyncio.run(main())
