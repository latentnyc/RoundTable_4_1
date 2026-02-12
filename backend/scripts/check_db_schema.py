
import asyncio
import sys
import os
from sqlalchemy import text

# Ensure backend modules can be imported if needed, though we just need sqlalchemy here
sys.path.append(os.getcwd())

# We can reuse the engine from db.session if available, or just connect directly to sqlite file for a raw check
# Let's try to use the app's engine to be sure we are checking the same DB the app uses.
try:
    from db.session import engine
except ImportError:
    # Fallback if imports fail (shouldn't if cwd is backend)
    print("Could not import engine, attempting manual connection logic...")
    from sqlalchemy import create_engine
    engine = create_engine("sqlite:///game.db")

async def check_schema():
    print("Checking schema for table 'campaigns'...", flush=True)
    async with engine.connect() as conn:
        # PRAGMA table_info is specific to SQLite.
        # If this checks a postgres DB in future, we'd need information_schema.
        # Assuming SQLite based on previous context.
        try:
             result = await conn.execute(text("PRAGMA table_info(campaigns)"))
             rows = result.fetchall()
             print(f"{'CID':<5} {'Name':<25} {'Type':<10} {'NotNull':<10} {'Dflt':<10} {'PK':<5}")
             print("-" * 70)
             found_cols = []
             for row in rows:
                 # row is (cid, name, type, notnull, dflt_value, pk)
                 print(f"{row[0]:<5} {row[1]:<25} {row[2]:<10} {row[3]:<10} {str(row[4]):<10} {row[5]:<5}")
                 if row[1] in ['total_input_tokens', 'total_output_tokens', 'query_count']:
                     found_cols.append(row[1])

             print("-" * 70)
             if len(found_cols) == 3:
                 print("VERIFICATION SUCCESS: All 3 AI stats columns found.")
             else:
                 print(f"VERIFICATION FAILED: Found {len(found_cols)}/3 columns: {found_cols}")

        except Exception as e:
            print(f"Error inspecting table: {e}")

if __name__ == "__main__":
    asyncio.run(check_schema())
