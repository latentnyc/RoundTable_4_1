import json
import os
import asyncio
import logging
import traceback
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from ..dependencies import get_db
from db.session import AsyncSessionLocal

# Define paths relative to this file
# backend/app/services/data_loader.py
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)

# Correct path to data: backend/json_data
DATA_DIR = os.path.join(BASE_DIR, "json_data")

def load_json_file(filepath):
    if not os.path.exists(filepath):
        logger.warning(f"{filepath} not found.")
        return []
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

async def is_dataset_loaded(db: AsyncSession):
    try:
        # Check if we have any spells AND monsters
        result_spells = await db.execute(text("SELECT COUNT(*) FROM spells"))
        count_spells = result_spells.scalar()

        result_monsters = await db.execute(text("SELECT COUNT(*) FROM monsters"))
        count_monsters = result_monsters.scalar()

        return count_spells > 0 and count_monsters > 0
    except Exception as e:
        logger.error(f"Error checking dataset status: {e}")
        return False

async def import_table(db: AsyncSession, table_name, json_filename, json_dir, name_key="name"):
    logger.info(f"--- Importing {table_name} from {json_filename} ---")
    filepath = os.path.join(json_dir, json_filename)
    items = load_json_file(filepath)
    if not items:
        logger.warning(f"No items found in {json_filename}")
        return 0

    batch_params = []
    
    # Prepare SQL statement based on table
    if table_name == "spells":
        sql = text("""
            INSERT INTO spells (id, name, level, school, data)
            VALUES (:id, :name, :level, :school, :data)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                level=excluded.level,
                school=excluded.school,
                data=excluded.data
        """)
        for item in items:
            record_id = item.get('index')
            name = item.get(name_key)
            if not record_id or not name: continue
            
            level = item.get('level', 0)
            try: level = int(level)
            except: level = 0
            
            batch_params.append({
                "id": record_id,
                "name": name,
                "level": level,
                "school": item.get('school', {}).get('name', 'Unknown'),
                "data": json.dumps(item)
            })

    elif table_name == "monsters":
        sql = text("""
            INSERT INTO monsters (id, name, type, cr, data)
            VALUES (:id, :name, :type, :cr, :data)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                type=excluded.type,
                cr=excluded.cr,
                data=excluded.data
        """)
        for item in items:
            record_id = item.get('index')
            name = item.get(name_key)
            if not record_id or not name: continue

            cr = str(item.get('challenge_rating', 0))
            batch_params.append({
                "id": record_id,
                "name": name,
                "type": item.get('type', 'unknown'),
                "cr": cr,
                "data": json.dumps(item)
            })

    elif table_name == "items":
        sql = text("""
            INSERT INTO items (id, name, type, data)
            VALUES (:id, :name, :type, :data)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                type=excluded.type,
                data=excluded.data
        """)
        for item in items:
            record_id = item.get('index')
            name = item.get(name_key)
            if not record_id or not name: continue

            batch_params.append({
                "id": record_id,
                "name": name,
                "type": item.get('equipment_category', {}).get('name', 'Item'),
                "data": json.dumps(item)
            })

    elif table_name in ["classes", "races", "alignments", "backgrounds"]:
        sql = text(f"""
            INSERT INTO {table_name} (id, name, data)
            VALUES (:id, :name, :data)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                data=excluded.data
        """)
        for item in items:
            record_id = item.get('index')
            name = item.get(name_key)
            if not record_id or not name: continue
            
            batch_params.append({
                "id": record_id,
                "name": name,
                "data": json.dumps(item)
            })
    
    else:
        logger.warning(f"Unknown table {table_name}")
        return 0

    if batch_params:
        try:
            # Execute batch insert
            await db.execute(sql, batch_params)
            await db.commit()
            logger.info(f"Processed {len(batch_params)} records for {table_name} (Batched)")
            return len(batch_params)
        except Exception as e:
            logger.error(f"Error executing batch for {table_name}: {e}")
            await db.rollback()
            return 0
    
    return 0

async def load_basic_dataset():
    logger.info(f"Loading basic dataset...")

    if not os.path.exists(DATA_DIR):
        msg = f"Error: Could not find data directory at {DATA_DIR}"
        logger.error(msg)
        return False, msg

    logger.info(f"Found data directory at {DATA_DIR}")

    # Create a new session
    async with AsyncSessionLocal() as db:
        try:
            # Map tables to files
            await import_table(db, "spells", "spell_box.json", DATA_DIR)
            await import_table(db, "items", "equipment_box.json", DATA_DIR)
            await import_table(db, "monsters", "monsters.json", DATA_DIR)
            await import_table(db, "classes", "class_box.json", DATA_DIR)
            await import_table(db, "races", "race_box.json", DATA_DIR)

            # Load stats box for alignments and backgrounds
            if os.path.exists(os.path.join(DATA_DIR, "stats_box.json")):
                 stats = load_json_file(os.path.join(DATA_DIR, "stats_box.json"))

                 if isinstance(stats, dict):
                     if "alignments" in stats:
                         logger.info("Importing alignments from stats_box.json")
                         for item in stats["alignments"]:
                             await db.execute(text("""
                                INSERT INTO alignments (id, name, data)
                                VALUES (:id, :name, :data)
                                ON CONFLICT(id) DO UPDATE SET name=excluded.name, data=excluded.data
                             """), {"id": item.get('index'), "name": item.get('name'), "data": json.dumps(item)})

                     if "backgrounds" in stats:
                         logger.info("Importing backgrounds from stats_box.json")
                         for item in stats["backgrounds"]:
                             await db.execute(text("""
                                INSERT INTO backgrounds (id, name, data)
                                VALUES (:id, :name, :data)
                                ON CONFLICT(id) DO UPDATE SET name=excluded.name, data=excluded.data
                             """), {"id": item.get('index'), "name": item.get('name'), "data": json.dumps(item)})

                     await db.commit()

            return True, "Dataset loaded successfully from custom JSON."
        except Exception as e:
            msg = f"Dataset load failed: {str(e)}"
            logger.error(msg)
            logger.error(traceback.format_exc())
            return False, msg
