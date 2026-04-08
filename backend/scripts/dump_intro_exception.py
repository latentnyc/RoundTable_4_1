import asyncio
import os
import sys

# adding backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from db.session import AsyncSessionLocal
from sqlalchemy import text

async def main():
    async with AsyncSessionLocal() as db:
        res = await db.execute(text("SELECT content FROM debug_logs WHERE type = 'intro_exception' ORDER BY created_at DESC LIMIT 1"))
        row = res.fetchone()
        print(row[0] if row else "None")

if __name__ == '__main__':
    asyncio.run(main())
