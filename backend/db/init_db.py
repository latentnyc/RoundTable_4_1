import asyncio
from db.session import engine
from db.schema import metadata
from app.firebase_config import init_firebase
from sqlalchemy import text

async def init_db_async():
    print("Initializing Database...", flush=True)
    try:
        print("DEBUG: Beginning DB transaction for schema creation...", flush=True)
        async with engine.begin() as conn:
            # Create tables
            await conn.run_sync(metadata.create_all)
            
            # Manual Migration for existing tables (Cloud SQL / Production)
            # Try to add 'status' column if not exists.
            try:
                # 1. Check if column exists (Using raw SQL due to asyncpg/sqlite differences)
                # But a brute force 'implements' catch is often easiest for simple schema evolutions in raw SQL
                # PostgreSQL support IF NOT EXISTS for ADD COLUMN
                # SQLite supports ADD COLUMN but not IF NOT EXISTS in older versions
                
                # Check dialect
                dialect = conn.dialect.name
                
                if dialect == 'postgresql':
                    await conn.execute(text("ALTER TABLE profiles ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'interested'"))
                else:
                    # SQLite: check pragma or try/except
                    # Simple try/except for SQLite
                    try:
                        await conn.execute(text("ALTER TABLE profiles ADD COLUMN status VARCHAR(50) DEFAULT 'interested'"))
                    except Exception:
                        pass # Column likely exists
                        
            except Exception as e:
                print(f"Migration Warning (status column): {e}", flush=True)

        print("DEBUG: Schema creation transaction committed.", flush=True)
    except Exception as e:
        print(f"CRITICAL: Database initialization failed: {e}", flush=True)
        raise e
    print("Database Initialized.", flush=True)

def init_sqlite():
    # Wrapper for sync calls if needed (like in main.py startup which is async though)
    # But main.py calls it.
    asyncio.run(init_db_async())

if __name__ == "__main__":
    asyncio.run(init_db_async())
    init_firebase()
