import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def verify():
    engine = create_async_engine('postgresql+asyncpg://postgres:roundtable_dev_2024@127.0.0.1:5432/postgres')
    async with engine.connect() as conn:
        res = await conn.execute(text("SELECT campaign_id, count(*), sum(length(state_data)) as bytes FROM game_states GROUP BY campaign_id"))
        for r in res.fetchall():
            print(f"Campaign: {r[0]} | Rows: {r[1]} | JSON Bytes: {r[2]}")

if __name__ == '__main__':
    asyncio.run(verify())
