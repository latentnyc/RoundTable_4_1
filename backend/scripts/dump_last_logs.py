import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from db.session import AsyncSessionLocal
from sqlalchemy import text

async def main():
    async with AsyncSessionLocal() as db:
        res = await db.execute(text("SELECT type, content FROM debug_logs ORDER BY created_at DESC LIMIT 5"))
        rows = res.fetchall()
        for r in rows:
            print(f"[{r[0]}] {r[1][:500]}...")

if __name__ == '__main__':
    asyncio.run(main())
