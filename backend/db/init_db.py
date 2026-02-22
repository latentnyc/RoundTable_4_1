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
            try:
                # PostgreSQL support IF NOT EXISTS for ADD COLUMN
                await conn.execute(text("ALTER TABLE profiles ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'interested'"))
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
                await conn.execute(text("ALTER TABLE campaign_templates ADD COLUMN IF NOT EXISTS json_path VARCHAR"))
            except Exception as e:
                logger.warning(f"Migration Warning (campaign_templates.json_path): {e}")

            # --- MIGRATIONS FOR AI STATS ---
            try:
                await conn.execute(text("ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS total_input_tokens INTEGER DEFAULT 0"))
                await conn.execute(text("ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS total_output_tokens INTEGER DEFAULT 0"))
                await conn.execute(text("ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS query_count INTEGER DEFAULT 0"))
            except Exception as e:
                logger.warning(f"Migration Warning (campaign stats columns): {e}")

            # --- MIGRATIONS FOR SCOPED TABLES (npcs, locations, quests) ---
            # These tables might exist with 'template_id' from earlier runs.
            # We need to add 'campaign_id' and 'source_id'.

            # npcs
            try:
                await conn.execute(text("ALTER TABLE npcs ADD COLUMN IF NOT EXISTS campaign_id VARCHAR"))
                await conn.execute(text("ALTER TABLE npcs ADD COLUMN IF NOT EXISTS source_id VARCHAR"))
            except Exception as e:
                logger.warning(f"Migration Warning (npcs columns): {e}")

            # locations
            try:
                await conn.execute(text("ALTER TABLE locations ADD COLUMN IF NOT EXISTS campaign_id VARCHAR"))
                await conn.execute(text("ALTER TABLE locations ADD COLUMN IF NOT EXISTS source_id VARCHAR"))
            except Exception as e:
                logger.warning(f"Migration Warning (locations columns): {e}")

            # quests
            try:
                await conn.execute(text("ALTER TABLE quests ADD COLUMN IF NOT EXISTS campaign_id VARCHAR"))
                await conn.execute(text("ALTER TABLE quests ADD COLUMN IF NOT EXISTS source_id VARCHAR"))
            except Exception as e:
                logger.warning(f"Migration Warning (quests columns): {e}")

        logger.debug("Schema creation transaction committed.")
    except Exception as e:
        logger.critical(f"Database initialization failed: {e}")
        raise e
    logger.info("Database Initialized.")



if __name__ == "__main__":
    asyncio.run(init_db_async())
    init_firebase()
