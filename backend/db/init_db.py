import asyncio
import os
import sys
import logging

logger = logging.getLogger(__name__)

# Add parent directory to path to allow imports from backend root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.session import engine
from db.schema import metadata
from app.firebase_config import init_firebase
from sqlalchemy import text

async def init_db_async():
    logger.info("Initializing Database...")
    try:
        logger.debug("Beginning DB transaction for schema creation...")
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
                logger.warning(f"Migration Warning (status column): {e}")

            # Migration for template_id in campaigns
            # In Schema now. (Skipped)

            # Migration for template_id in items / monsters
            # In Schema now. (Skipped)

            # Migration for campaign_id in items / monsters
            # In Schema now. (Skipped)

            # Migration for json_path in campaign_templates
            try:
                if dialect == 'postgresql':
                     await conn.execute(text("ALTER TABLE campaign_templates ADD COLUMN IF NOT EXISTS json_path VARCHAR"))
                else:
                     try:
                        await conn.execute(text("ALTER TABLE campaign_templates ADD COLUMN json_path VARCHAR"))
                     except Exception: pass
            except Exception as e:
                logger.warning(f"Migration Warning (campaign_templates.json_path): {e}")

            # --- MIGRATIONS FOR AI STATS ---
            try:
                if dialect == 'postgresql':
                     await conn.execute(text("ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS total_input_tokens INTEGER DEFAULT 0"))
                     await conn.execute(text("ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS total_output_tokens INTEGER DEFAULT 0"))
                     await conn.execute(text("ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS query_count INTEGER DEFAULT 0"))
                else:
                     try: await conn.execute(text("ALTER TABLE campaigns ADD COLUMN total_input_tokens INTEGER DEFAULT 0"))
                     except Exception: pass
                     try: await conn.execute(text("ALTER TABLE campaigns ADD COLUMN total_output_tokens INTEGER DEFAULT 0"))
                     except Exception: pass
                     try: await conn.execute(text("ALTER TABLE campaigns ADD COLUMN query_count INTEGER DEFAULT 0"))
                     except Exception: pass
            except Exception as e:
                logger.warning(f"Migration Warning (campaign stats columns): {e}")

            # --- MIGRATIONS FOR SCOPED TABLES (npcs, locations, quests) ---
            # These tables might exist with 'template_id' from earlier runs.
            # We need to add 'campaign_id' and 'source_id'.

            # npcs
            try:
                if dialect == 'postgresql':
                     await conn.execute(text("ALTER TABLE npcs ADD COLUMN IF NOT EXISTS campaign_id VARCHAR"))
                     await conn.execute(text("ALTER TABLE npcs ADD COLUMN IF NOT EXISTS source_id VARCHAR"))
                else:
                     try: await conn.execute(text("ALTER TABLE npcs ADD COLUMN campaign_id VARCHAR"))
                     except Exception: pass
                     try: await conn.execute(text("ALTER TABLE npcs ADD COLUMN source_id VARCHAR"))
                     except Exception: pass
            except Exception as e:
                logger.warning(f"Migration Warning (npcs columns): {e}")

            # locations
            try:
                if dialect == 'postgresql':
                     await conn.execute(text("ALTER TABLE locations ADD COLUMN IF NOT EXISTS campaign_id VARCHAR"))
                     await conn.execute(text("ALTER TABLE locations ADD COLUMN IF NOT EXISTS source_id VARCHAR"))
                else:
                     try: await conn.execute(text("ALTER TABLE locations ADD COLUMN campaign_id VARCHAR"))
                     except Exception: pass
                     try: await conn.execute(text("ALTER TABLE locations ADD COLUMN source_id VARCHAR"))
                     except Exception: pass
            except Exception as e:
                logger.warning(f"Migration Warning (locations columns): {e}")

            # quests
            try:
                if dialect == 'postgresql':
                     await conn.execute(text("ALTER TABLE quests ADD COLUMN IF NOT EXISTS campaign_id VARCHAR"))
                     await conn.execute(text("ALTER TABLE quests ADD COLUMN IF NOT EXISTS source_id VARCHAR"))
                else:
                     try: await conn.execute(text("ALTER TABLE quests ADD COLUMN campaign_id VARCHAR"))
                     except Exception: pass
                     try: await conn.execute(text("ALTER TABLE quests ADD COLUMN source_id VARCHAR"))
                     except Exception: pass
            except Exception as e:
                logger.warning(f"Migration Warning (quests columns): {e}")

        logger.debug("Schema creation transaction committed.")
    except Exception as e:
        logger.critical(f"Database initialization failed: {e}")
        raise e
    logger.info("Database Initialized.")

def init_sqlite():
    # Wrapper for sync calls if needed (like in main.py startup which is async though)
    # But main.py calls it.
    asyncio.run(init_db_async())

if __name__ == "__main__":
    asyncio.run(init_db_async())
    init_firebase()
