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
from sqlalchemy.exc import SQLAlchemyError

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
            except SQLAlchemyError as e:
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
            except SQLAlchemyError as e:
                logger.warning(f"Migration Warning (campaign_templates.json_path): {e}")

            # --- MIGRATIONS FOR AI STATS ---
            try:
                await conn.execute(text("ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS total_input_tokens INTEGER DEFAULT 0"))
                await conn.execute(text("ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS total_output_tokens INTEGER DEFAULT 0"))
                await conn.execute(text("ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS query_count INTEGER DEFAULT 0"))
                await conn.execute(text("ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS llm_provider VARCHAR DEFAULT 'gemini'"))
            except SQLAlchemyError as e:
                logger.warning(f"Migration Warning (campaign stats columns): {e}")

            # --- MIGRATIONS FOR SCOPED TABLES (npcs, locations, quests) ---
            # These tables might exist with 'template_id' from earlier runs.
            # We need to add 'campaign_id' and 'source_id'.

            # npcs
            try:
                await conn.execute(text("ALTER TABLE npcs ADD COLUMN IF NOT EXISTS campaign_id VARCHAR"))
                await conn.execute(text("ALTER TABLE npcs ADD COLUMN IF NOT EXISTS source_id VARCHAR"))
            except SQLAlchemyError as e:
                logger.warning(f"Migration Warning (npcs columns): {e}")

            # locations
            try:
                await conn.execute(text("ALTER TABLE locations ADD COLUMN IF NOT EXISTS campaign_id VARCHAR"))
                await conn.execute(text("ALTER TABLE locations ADD COLUMN IF NOT EXISTS source_id VARCHAR"))
            except SQLAlchemyError as e:
                logger.warning(f"Migration Warning (locations columns): {e}")

            # quests
            try:
                await conn.execute(text("ALTER TABLE quests ADD COLUMN IF NOT EXISTS campaign_id VARCHAR"))
                await conn.execute(text("ALTER TABLE quests ADD COLUMN IF NOT EXISTS source_id VARCHAR"))
            except SQLAlchemyError as e:
                logger.warning(f"Migration Warning (quests columns): {e}")

        logger.debug("Schema creation transaction committed.")
    except SQLAlchemyError as e:
        logger.critical(f"Database initialization failed: {e}")
        raise e

    # --- GAME_STATES: collapse append-log to one upserted row per campaign (idempotent) ---
    # Older builds inserted a fresh game_states row per save and read "newest by timestamp",
    # which is non-deterministic under rapid AI-turn saves. Dedup to the newest row per
    # campaign, then enforce it with a unique constraint so save_game_state can upsert on
    # campaign_id. Both steps are idempotent; a second run deletes 0 rows and skips the add.
    try:
        async with engine.begin() as conn:
            await conn.execute(text("""
                DELETE FROM game_states gs
                USING (
                    SELECT id, ROW_NUMBER() OVER (
                        PARTITION BY campaign_id ORDER BY updated_at DESC, id DESC
                    ) AS rn
                    FROM game_states
                ) ranked
                WHERE gs.id = ranked.id AND ranked.rn > 1
            """))
            await conn.execute(text("""
                DO $$ BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint WHERE conname = 'uq_game_states_campaign_id'
                    ) THEN
                        ALTER TABLE game_states ADD CONSTRAINT uq_game_states_campaign_id UNIQUE (campaign_id);
                    END IF;
                END $$;
            """))
    except SQLAlchemyError as e:
        logger.warning(f"game_states dedup/unique migration failed (non-fatal): {e}")

    # --- SPRINT 1: LONG-TERM MEMORY (episodic) — isolated & fail-open ---
    # Created via raw DDL only (intentionally NOT in schema.py metadata, so
    # metadata.create_all never races it). A failure here must not crash startup:
    # memory is strictly additive, so we log and continue.
    try:
        async with engine.begin() as conn:
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS memory_episodes (
                    id                 VARCHAR PRIMARY KEY,
                    campaign_id        VARCHAR NOT NULL,
                    kind               VARCHAR NOT NULL DEFAULT 'summary',
                    content            TEXT NOT NULL,
                    facts              JSONB NOT NULL DEFAULT '{}',
                    subject_refs       JSONB NOT NULL DEFAULT '[]',
                    witnessed_by       JSONB NOT NULL DEFAULT '[]',
                    importance         REAL NOT NULL DEFAULT 0.5,
                    access_count       INTEGER NOT NULL DEFAULT 0,
                    last_surfaced_turn INTEGER,
                    session_no         INTEGER,
                    src_from           TIMESTAMPTZ,
                    src_to             TIMESTAMPTZ,
                    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
                )
            """))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_mem_ep_camp_salience ON memory_episodes (campaign_id, importance DESC, created_at DESC)"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_mem_ep_subjects ON memory_episodes USING gin (subject_refs)"))
            # 2-arg to_tsvector(regconfig, text) is IMMUTABLE, so it is index-safe.
            await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_mem_ep_fts ON memory_episodes USING gin (to_tsvector('english', content))"))
            await conn.execute(text("ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS session_no INTEGER NOT NULL DEFAULT 1"))
            await conn.execute(text("ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS embed_model VARCHAR"))
            await conn.execute(text("ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS memory_rag_enabled BOOLEAN DEFAULT FALSE"))
    except SQLAlchemyError as e:
        logger.warning(f"Memory migration failed (non-fatal): {e}")

    # items.rarity in its own transaction so a missing items table can't roll back the memory schema.
    try:
        async with engine.begin() as conn:
            await conn.execute(text("ALTER TABLE items ADD COLUMN IF NOT EXISTS rarity VARCHAR DEFAULT 'common'"))
    except SQLAlchemyError as e:
        logger.warning(f"items.rarity migration failed (non-fatal): {e}")

    # --- COORDINATE MIGRATION: cube {q,r,s} -> square {x,y} (idempotent, fail-open) ---
    # Positions live only inside JSON text columns (no coordinate DDL). init_db is the
    # sole migration execution path in this repo — Alembic is never invoked. A second
    # run reports 0 changed rows. The Coordinates model also has a {q,r}->{x,y} shim,
    # so an un-migrated row still loads even if this step is skipped.
    try:
        from db.migrate_coords import migrate_json_text
        targets = [
            ("game_states", "id", "state_data"),
            ("characters",  "id", "sheet_data"),
            ("monsters",    "id", "data"),
            ("npcs",        "id", "data"),
            ("locations",   "id", "data"),
        ]
        async with engine.begin() as conn:
            for table, pk, col in targets:
                res = await conn.execute(text(f"SELECT {pk}, {col} FROM {table}"))
                for row_id, raw in res.fetchall():
                    new_raw, changed = migrate_json_text(raw)
                    if changed:
                        await conn.execute(
                            text(f"UPDATE {table} SET {col} = :v WHERE {pk} = :id"),
                            {"v": new_raw, "id": row_id},
                        )
    except SQLAlchemyError as e:
        logger.warning(f"Coordinate migration failed (non-fatal): {e}")

    logger.info("Database Initialized.")



if __name__ == "__main__":
    asyncio.run(init_db_async())
    init_firebase()
