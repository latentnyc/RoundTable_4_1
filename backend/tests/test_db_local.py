import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from db.schema import metadata
from db.session import engine, AsyncSessionLocal

import pytest

# Define DATABASE_URL for local testing if not already defined
# This assumes a local PostgreSQL database named 'test_db'
# You might need to adjust this based on your local setup
DATABASE_URL = "postgresql+asyncpg://user:password@localhost/test_db"

@pytest.mark.skip(reason="Tests infrastructure directly, causes async event loop side-effects")
async def test_db():
    print(f"Testing DB...")

    async with AsyncSessionLocal() as db:
        try:
            # Clean up previous runs if exist
            await db.execute(text("DELETE FROM profiles WHERE id = 'user123'"))
            await db.commit()

            # Insert Profile
            print("Inserting profile...")
            await db.execute(
                text("INSERT INTO profiles (id, username, is_admin) VALUES (:id, :username, :is_admin)"),
                {"id": "user123", "username": "TestUser", "is_admin": True}
            )
            await db.commit()

            # Query Profile
            print("Querying profile...")
            result = await db.execute(text("SELECT * FROM profiles WHERE id = :id"), {"id": "user123"})
            row = result.mappings().fetchone()
            print(f"Row: {row}")
            assert row["username"] == "TestUser"
            assert row["is_admin"] == True

            print("SUCCESS: Database abstraction works for PostgreSQL.")
        except Exception as e:
            print(f"FAILURE: {e}")
            raise
        finally:
            await db.execute(text("DELETE FROM profiles WHERE id = 'user123'"))
            await db.commit()
            await db.close()
            await engine.dispose()  # Cleanup the engine to avoid event loop closure bugs

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_db())
