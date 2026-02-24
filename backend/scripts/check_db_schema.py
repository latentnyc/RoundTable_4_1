
import asyncio
import sys
import os
from sqlalchemy import text

# Ensure backend modules can be imported if needed, though we just need sqlalchemy here
sys.path.append(os.getcwd())

# We can reuse the engine from db.session if available, or just connect directly to DB for a raw check
# Let's try to use the app's engine to be sure we are checking the same DB the app uses.
try:
    from db.session import engine
except ImportError:
    # Fallback if imports fail (shouldn't if cwd is backend)
    print("Could not import engine, attempting manual connection logic...")
    from sqlalchemy import create_engine
    engine = create_engine(os.getenv("DATABASE_URL", "postgresql://postgres:roundtable_dev_2024@127.0.0.1:5432/postgres"))

async def check_schema():
    print("Checking schema for table 'campaigns'...", flush=True)
    async with engine.connect() as conn:
        # PostgreSQL information schema check.
        try:
             result = await conn.execute(text("SELECT column_name, data_type, is_nullable, column_default FROM information_schema.columns WHERE table_name = 'campaigns'"))
             rows = result.fetchall()
             print(f"{'Name':<25} {'Type':<10} {'Nullable':<10} {'Dflt':<10}")
             print("-" * 70)
             found_cols = []
             for row in rows:
                 # row is (column_name, data_type, is_nullable, column_default)
                 print(f"{row[0]:<25} {row[1]:<10} {row[2]:<10} {str(row[3]):<10}")
                 if row[1] in ['total_input_tokens', 'total_output_tokens', 'query_count']:
                     found_cols.append(row[1])

             print("-" * 70)
             if len(found_cols) == 3:
                 print("VERIFICATION SUCCESS: All 3 AI stats columns found.")
             else:
                 print(f"VERIFICATION FAILED: Found {len(found_cols)}/3 columns: {found_cols}")

        except Exception as e:
            print(f"Fatal Error: {e}")
            import sys; sys.exit(1)

if __name__ == "__main__":
    asyncio.run(check_schema())
