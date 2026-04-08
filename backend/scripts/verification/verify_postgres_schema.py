import asyncio
import os
import sys
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

# Start with the URL from .env, but allow override
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql+asyncpg://postgres:roundtable_dev_2024@127.0.0.1:5432/postgres")

async def verify_postgres_schema():
    print(f"Connecting to: {DATABASE_URL}")
    try:
        engine = create_async_engine(DATABASE_URL, echo=False)

        async with engine.connect() as conn:
            print("Successfully connected to PostgreSQL!")

            # Inspect tables
            tables = ["characters", "monsters", "npcs"]
            for t in tables:
                print(f"\n--- Checking Table: {t} ---")
                try:
                    # Postgres specific: querying information_schema
                    query = text(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{t}'")
                    result = await conn.execute(query)
                    columns = result.fetchall()

                    if not columns:
                        print(f"Table '{t}' NOT FOUND (or empty schema).")
                    else:
                        for col in columns:
                            print(f"  - {col[0]} ({col[1]})")

                        # Specific validation
                        col_names = [c[0] for c in columns]
                        if t == 'characters' and 'sheet_data' in col_names:
                            print(f"✅ 'sheet_data' column present in {t}")
                        elif t in ['monsters', 'npcs'] and 'data' in col_names:
                            print(f"✅ 'data' column present in {t}")
                        else:
                            print(f"⚠️ Critical column missing in {t}!")

                except Exception as e:
                    print(f"Fatal Error: {e}")
                    import sys; sys.exit(1)

    except Exception as e:
        print(f"Fatal Error: {e}")
        import sys; sys.exit(1)
        print("Note: Ensure Postgres (or Cloud SQL Proxy) is running on port 5432.")

if __name__ == "__main__":
    asyncio.run(verify_postgres_schema())
