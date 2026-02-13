import asyncio
import os
import sys
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

# Path to actual DB
DB_PATH = "game.db"
DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"

async def verify_schema():
    if not os.path.exists(DB_PATH):
        print(f"Database file {DB_PATH} not found!")
        return

    engine = create_async_engine(DATABASE_URL, echo=False)
    
    async with engine.connect() as conn:
        print(f"Connected to {DB_PATH}")
        
        tables = ["characters", "monsters", "npcs"]
        for t in tables:
            print(f"\n--- Table: {t} ---")
            try:
                # SQLite specific: PRAGMA table_info
                result = await conn.execute(text(f"PRAGMA table_info({t})"))
                columns = result.fetchall()
                if not columns:
                    print(f"Table {t} NOT FOUND or empty schema.")
                else:
                    for col in columns:
                        # cid, name, type, notnull, dflt_value, pk
                        print(f"  - {col[1]} ({col[2]})")
            except Exception as e:
                print(f"Error inspecting {t}: {e}")

if __name__ == "__main__":
    asyncio.run(verify_schema())
