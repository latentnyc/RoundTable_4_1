import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from db.schema import metadata

# Force SQLite for this test
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_migration.db"

DATABASE_URL = os.environ["DATABASE_URL"]

async def test_db():
    print(f"Testing with {DATABASE_URL}")
    
    # 1. Create Engine
    engine = create_async_engine(DATABASE_URL, echo=True)
    
    # 2. Init DB (Create Tables)
    async with engine.begin() as conn:
        await conn.run_sync(metadata.drop_all)
        await conn.run_sync(metadata.create_all)
    print("Tables created.")
    
    # 3. Create Session Factory
    AsyncSessionLocal = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    # 4. detailed test
    async with AsyncSessionLocal() as db:
        try:
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
            assert row["is_admin"] == True # SQLite might return 1, but SQLAlchemy casts if Boolean type is used
            
            print("SUCCESS: Database abstraction works for SQLite.")
        except Exception as e:
            print(f"FAILURE: {e}")
            raise
        finally:
            await db.close()

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_db())
