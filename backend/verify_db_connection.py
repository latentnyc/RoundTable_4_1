import asyncio
import os
import sys
from sqlalchemy import text
from db.session import AsyncSessionLocal

# Add parent directory to path so we can import from app/db
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def test_connection():
    print("Testing Database Connection...", flush=True)
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(text("SELECT 1"))
            print(f"Connection Successful! Result: {result.scalar()}", flush=True)
            return True
    except Exception as e:
        print(f"Connection Failed: {e}", flush=True)
        return False

if __name__ == "__main__":
    try:
        success = asyncio.run(test_connection())
        if not success:
            sys.exit(1)
    except Exception as e:
        print(f"Script Error: {e}", flush=True)
        sys.exit(1)
