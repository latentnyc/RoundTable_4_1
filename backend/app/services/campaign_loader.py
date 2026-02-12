
import json
import os
import asyncio
import logging
import traceback
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from ..dependencies import get_db
from db.session import AsyncSessionLocal
import glob
from uuid import uuid4

# Define paths relative to this file
# backend/app/services/campaign_loader.py
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
# backend -> RoundTable_4_1
GAMES_DIR = os.path.join(BASE_DIR, "games")

logger = logging.getLogger(__name__)

def load_json_file(filepath):
    if not os.path.exists(filepath):
        logger.warning(f"{filepath} not found.")
        return None
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

async def sync_template_metadata(db: AsyncSession, data, filepath):
    # Campaign Template Catalog
    template_id = data.get('id')

    # Extract starting meta
    meta = data.get('campaign_meta', {})

    config = {
        "time_config": data.get('time_config', meta.get('time_config', {})),
        "starting_location": data.get('starting_location', meta.get('starting_location')),
        "starting_npc": data.get('starting_npc', meta.get('starting_npc'))
    }

    # Store minimal initial state metadata if needed, but the full JSON path is key
    initial_state = {
        "narrative_state": data.get('narrative_state', {}),
        "timeline": data.get('timeline', []),
        "quests": data.get('quests', []),
        "active_quests": data.get('narrative_state', {}).get('active_quests', [])
    }

    logger.info(f"Syncing Template: {template_id} from {os.path.basename(filepath)}")

    # Check if exists
    # We use ON CONFLICT to update
    await db.execute(text("""
        INSERT INTO campaign_templates (id, name, description, genre, config, system_prompt, json_path, initial_state)
        VALUES (:id, :name, :description, :genre, :config, :system_prompt, :json_path, :initial_state)
        ON CONFLICT(id) DO UPDATE SET
            name=excluded.name,
            description=excluded.description,
            genre=excluded.genre,
            config=excluded.config,
            system_prompt=excluded.system_prompt,
            json_path=excluded.json_path,
            initial_state=excluded.initial_state
    """), {
        "id": template_id,
        "name": data.get('title', 'Unknown'),
        "description": data.get('description', ''),
        "genre": data.get('genre', ''),
        "config": json.dumps(config),
        "system_prompt": data.get('setting_system_prompt', ''),
        "json_path": filepath,
        "initial_state": json.dumps(initial_state)
    })

async def instantiate_campaign(db: AsyncSession, campaign_id: str, template_id: str):
    """
    Copies data from the template JSON into the campaign instance tables.
    """
    logger.info(f"Instantiating campaign {campaign_id} from template {template_id}")

    # 1. Get Template Path
    result = await db.execute(text("SELECT json_path FROM campaign_templates WHERE id = :tid"), {"tid": template_id})
    row = result.fetchone()
    if not row:
        raise ValueError(f"Template {template_id} not found")

    json_path = row[0]
    data = load_json_file(json_path)
    if not data:
        raise ValueError(f"Could not load JSON from {json_path}")

    # 2. Insert NPCs
    npcs = data.get('npcs', [])
    logger.info(f"  - Loading {len(npcs)} NPCs")
    for npc in npcs:
        new_id = str(uuid4()) # Generate new unique ID for this instance
        npc_data = npc

        # --- Hostility Synchronization ---
        # Automatically set mechanical 'hostile' flag if attitude implies it
        disposition = npc_data.get('disposition', {})
        attitude = disposition.get('attitude', '').lower()
        HOSTILE_ATTITUDES = ['hostile', 'aggressive', 'violent', 'enemy', 'attack on sight']

        if any(h in attitude for h in HOSTILE_ATTITUDES):
             # Only override if not explicitly set to False (allow manual peace)
             if 'hostile' not in npc_data:
                 npc_data['hostile'] = True
                 logger.info(f"    -> Auto-marked {npc.get('name')} as Hostile based on attitude '{attitude}'")

        await db.execute(text("""
            INSERT INTO npcs (id, campaign_id, source_id, name, role, data)
            VALUES (:id, :campaign_id, :source_id, :name, :role, :data)
        """), {
            "id": new_id,
            "campaign_id": campaign_id,
            "source_id": npc.get('id'), # Keep original ID as reference
            "name": npc.get('name'),
            "role": npc.get('role'),
            "data": json.dumps(npc_data)
        })

    # 3. Insert Locations
    locations = data.get('atlas', [])
    logger.info(f"  - Loading {len(locations)} Locations")
    for loc in locations:
        new_id = str(uuid4())
        await db.execute(text("""
            INSERT INTO locations (id, campaign_id, source_id, name, data)
            VALUES (:id, :campaign_id, :source_id, :name, :data)
        """), {
            "id": new_id,
            "campaign_id": campaign_id,
            "source_id": loc.get('id'),
            "name": loc.get('name'),
            "data": json.dumps(loc)
        })

    # 4. Insert Quests
    quests = data.get('quests', [])
    logger.info(f"  - Loading {len(quests)} Quests")
    for q in quests:
         new_id = str(uuid4())
         await db.execute(text("""
            INSERT INTO quests (id, campaign_id, source_id, title, steps, rewards, data)
            VALUES (:id, :campaign_id, :source_id, :title, :steps, :rewards, :data)
        """), {
            "id": new_id,
            "campaign_id": campaign_id,
            "source_id": q.get('id'),
            "title": q.get('title'),
            "steps": json.dumps(q.get('steps', [])),
            "rewards": json.dumps(q.get('rewards', [])),
            "data": json.dumps(q)
        })

    # 5. Insert Items (Campaign Specific)
    items = data.get('items', [])
    logger.info(f"  - Loading {len(items)} Items")
    for item in items:
        new_id = str(uuid4())
        # Note: We are inserting into 'items' table, but now it has campaign_id
        await db.execute(text("""
            INSERT INTO items (id, campaign_id, name, type, data)
            VALUES (:id, :campaign_id, :name, :type, :data)
        """), {
            "id": new_id,
            "campaign_id": campaign_id,
            "name": item.get('name'),
            "type": item.get('type'),
            "data": json.dumps(item)
        })

    # 6. Insert Monsters (Campaign Specific)
    monsters = data.get('monsters', [])
    logger.info(f"  - Loading {len(monsters)} Monsters")
    for mon in monsters:
        new_id = str(uuid4())
        await db.execute(text("""
            INSERT INTO monsters (id, campaign_id, name, type, cr, data)
            VALUES (:id, :campaign_id, :name, :type, :cr, :data)
        """), {
            "id": new_id,
            "campaign_id": campaign_id,
            "name": mon.get('name'),
            "type": mon.get('type'),
            "cr": str(mon.get('challenge_rating', 'Unknown')),
            "data": json.dumps(mon)
        })

    logger.info(f"Successfully instantiated campaign {campaign_id}")


async def parse_and_load():
    """
    Main entry point for startup script. Syncs templates.
    """
    logger.info(f"Searching for campaign JSONs in {GAMES_DIR}...")
    json_files = glob.glob(os.path.join(GAMES_DIR, "*.json"))

    async with AsyncSessionLocal() as db:
        for file in json_files:
            if "blank_schema.json" in file:
                continue

            logger.info(f"Processing {os.path.basename(file)}...")
            data = load_json_file(file)
            if not data:
                logger.warning(f"Skipping {file} - Empty or invalid JSON")
                continue

            # Standardize Metadata from campaign_meta if present
            if 'campaign_meta' in data:
                meta = data['campaign_meta']
                # Prefer root keys if they exist, otherwise fallback to meta
                if 'id' not in data: data['id'] = meta.get('id')
                if 'title' not in data: data['title'] = meta.get('title')
                if 'genre' not in data: data['genre'] = meta.get('genre')
                if 'description' not in data: data['description'] = meta.get('description')
                if 'setting_system_prompt' not in data: data['setting_system_prompt'] = meta.get('setting_system_prompt')
                if 'time_config' not in data: data['time_config'] = meta.get('time_config')

            if 'id' not in data:
                logger.warning(f"Skipping {file} - Invalid data or missing ID")
                continue

            try:
                await sync_template_metadata(db, data, file)
                await db.commit()
            except Exception as e:
                await db.rollback()
                logger.error(f"Error loading {file}: {e}")
                logger.error(traceback.format_exc())

if __name__ == "__main__":
    asyncio.run(parse_and_load())
