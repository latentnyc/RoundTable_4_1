
import asyncio
import sys
import os

# Ensure backend modules are found
sys.path.append(os.getcwd())

from sqlalchemy import text
from db.session import engine

async def verify_columns():
    print("Verifying campaigns table columns...", flush=True)
    async with engine.connect() as conn:
        # Check for columns by trying to select them
        try:
            result = await conn.execute(text("SELECT total_input_tokens, total_output_tokens, query_count FROM campaigns LIMIT 1"))
            print("SUCCESS: Columns total_input_tokens, total_output_tokens, query_count exist.", flush=True)
        except Exception as e:
            print(f"Fatal Error: {e}")
            import sys; sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(verify_columns())
    except Exception as e:
        print(f"Fatal Error: {e}")
        import sys; sys.exit(1)
