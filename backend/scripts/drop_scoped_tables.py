
import asyncio
from sqlalchemy import text
from db.session import engine

async def drop_tables():
    async with engine.begin() as conn:
        print("Dropping scoped tables (npcs, locations, quests)...")
        await conn.execute(text("DROP TABLE IF EXISTS npcs"))
        await conn.execute(text("DROP TABLE IF EXISTS locations"))
        await conn.execute(text("DROP TABLE IF EXISTS quests"))
        print("Done.")

if __name__ == "__main__":
    asyncio.run(drop_tables())
