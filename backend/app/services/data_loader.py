import json
import os
import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from ..dependencies import get_db
from db.session import AsyncSessionLocal

# Define paths relative to this file
# backend/app/services/data_loader.py
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Correct path to data: backend/json_data
DATA_DIR = os.path.join(BASE_DIR, "json_data")

def load_json_file(filepath):
    if not os.path.exists(filepath):
        print(f"Warning: {filepath} not found.")
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
        print(f"Error checking dataset status: {e}")
        return False

async def import_table(db: AsyncSession, table_name, json_filename, json_dir, name_key="name"):
    print(f"--- Importing {table_name} from {json_filename} ---")
    filepath = os.path.join(json_dir, json_filename)
    items = load_json_file(filepath)
    if not items:
        print(f"No items found in {json_filename}")
        return 0

    count = 0
    
    for item in items:
        try:
            record_id = item.get('index')
            name = item.get(name_key)
            
            if not record_id or not name:
                continue

            data_json = json.dumps(item)
            
            if table_name == "spells":
                level = item.get('level', 0)
                # Ensure level is int
                try: level = int(level)
                except: level = 0
                
                school = item.get('school', {}).get('name', 'Unknown')
                await db.execute(text("""
                    INSERT INTO spells (id, name, level, school, data) 
                    VALUES (:id, :name, :level, :school, :data)
                    ON CONFLICT(id) DO UPDATE SET 
                        name=excluded.name, 
                        level=excluded.level, 
                        school=excluded.school, 
                        data=excluded.data
                """), {"id": record_id, "name": name, "level": level, "school": school, "data": data_json})
                
            elif table_name == "monsters":
                m_type = item.get('type', 'unknown')
                cr = item.get('challenge_rating', 0)
                # Ensure CR is valid string or number (Projecting as string in schema? No, Schema might accept string or float. Let's force string as schema has 'cr' as String)
                # Wait, schema check: monsters table has `cr` as String? 
                # Let's assume String since CR can be "1/4".
                cr = str(cr)
                    
                await db.execute(text("""
                    INSERT INTO monsters (id, name, type, cr, data) 
                    VALUES (:id, :name, :type, :cr, :data)
                    ON CONFLICT(id) DO UPDATE SET
                        name=excluded.name,
                        type=excluded.type,
                        cr=excluded.cr,
                        data=excluded.data
                """), {"id": record_id, "name": name, "type": m_type, "cr": cr, "data": data_json})
                
            elif table_name == "items":
                cat = item.get('equipment_category', {}).get('name', 'Item')
                await db.execute(text("""
                    INSERT INTO items (id, name, type, data) 
                    VALUES (:id, :name, :type, :data)
                    ON CONFLICT(id) DO UPDATE SET
                        name=excluded.name,
                        type=excluded.type,
                        data=excluded.data
                """), {"id": record_id, "name": name, "type": cat, "data": data_json})
                
            elif table_name == "classes":
                await db.execute(text("""
                    INSERT INTO classes (id, name, data) 
                    VALUES (:id, :name, :data)
                    ON CONFLICT(id) DO UPDATE SET
                        name=excluded.name,
                        data=excluded.data
                """), {"id": record_id, "name": name, "data": data_json})
                
            elif table_name == "races":
                await db.execute(text("""
                    INSERT INTO races (id, name, data) 
                    VALUES (:id, :name, :data)
                    ON CONFLICT(id) DO UPDATE SET
                        name=excluded.name,
                        data=excluded.data
                """), {"id": record_id, "name": name, "data": data_json})
                
            elif table_name == "alignments":
                 await db.execute(text("""
                    INSERT INTO alignments (id, name, data) 
                    VALUES (:id, :name, :data)
                    ON CONFLICT(id) DO UPDATE SET
                        name=excluded.name,
                        data=excluded.data
                """), {"id": record_id, "name": name, "data": data_json})

            elif table_name == "backgrounds":
                 await db.execute(text("""
                    INSERT INTO backgrounds (id, name, data) 
                    VALUES (:id, :name, :data)
                    ON CONFLICT(id) DO UPDATE SET
                        name=excluded.name,
                        data=excluded.data
                """), {"id": record_id, "name": name, "data": data_json})

            count += 1
            
        except Exception as e:
            print(f"Error importing {name}: {e}")

    await db.commit()
    print(f"Processed {count} records for {table_name}")
    return count

async def load_basic_dataset():
    print(f"Loading basic dataset...")
    
    if not os.path.exists(DATA_DIR):
        msg = f"Error: Could not find data directory at {DATA_DIR}"
        print(msg)
        return False, msg

    print(f"Found data directory at {DATA_DIR}")

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
                         print("Importing alignments from stats_box.json")
                         for item in stats["alignments"]:
                             await db.execute(text("""
                                INSERT INTO alignments (id, name, data) 
                                VALUES (:id, :name, :data)
                                ON CONFLICT(id) DO UPDATE SET name=excluded.name, data=excluded.data
                             """), {"id": item.get('index'), "name": item.get('name'), "data": json.dumps(item)})
                     
                     if "backgrounds" in stats:
                         print("Importing backgrounds from stats_box.json")
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
            print(msg)
            import traceback
            traceback.print_exc()
            return False, msg
