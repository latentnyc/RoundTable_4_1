import pytest
import os
import sys
# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from httpx import AsyncClient, ASGITransport
from main import fastapi_app
from app.routers.characters import verify_token
from db.session import engine, AsyncSessionLocal
from sqlalchemy import text
from db.schema import metadata

async def override_verify_token():
    return {"uid": "test_user_uuid", "email": "test@test.com", "role": "player"}

fastapi_app.dependency_overrides[verify_token] = override_verify_token

@pytest.mark.asyncio
async def test_spawn_trio_api():
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)

    # Insert test user and campaign into the DB to satisfy foreign keys
    campaign_id = "test_campaign_uuid_for_trio"
    user_id = "test_user_uuid"
    
    async with AsyncSessionLocal() as db:
        await db.execute(text("INSERT INTO profiles (id, username) VALUES (:uid, 'Test User') ON CONFLICT (id) DO NOTHING"), {"uid": user_id})
        await db.execute(text("INSERT INTO campaigns (id, name, gm_id) VALUES (:cid, 'Test Trio Campaign', :uid) ON CONFLICT (id) DO NOTHING"), {"cid": campaign_id, "uid": user_id})
        await db.commit()
    
    faein_payload = {
        "name": "Faein",
        "role": "Fighter",
        "race": "Human",
        "level": 3,
        "campaign_id": campaign_id,
        "user_id": user_id,
        "control_mode": "human",
        "sheet_data": {
            "hp_current": 28, "hp_max": 28, "ac": 16, "initiative": 2, "speed": 30,
            "stats": {"Strength": 16, "Dexterity": 14, "Constitution": 15, "Intelligence": 10, "Wisdom": 12, "Charisma": 10},
            "skills": {"Athletics": True, "Intimidation": True, "Perception": True},
            "inventory": ["Longsword", "Shield", "Chain Mail"],
            "equipment": ["Longsword", "Shield", "Chain Mail"],
            "spells": [], "feats": [], "features": "Action Surge, Second Wind, Improved Critical",
            "alignment": "Lawful Neutral"
        }
    }
    
    jenath_payload = {
        "name": "Jenath",
        "role": "Wizard",
        "race": "Elf",
        "level": 3,
        "campaign_id": campaign_id,
        "user_id": user_id,
        "control_mode": "ai",
        "sheet_data": {
            "hp_current": 17, "hp_max": 17, "ac": 15, "initiative": 2, "speed": 30,
            "stats": {"Strength": 8, "Dexterity": 14, "Constitution": 12, "Intelligence": 17, "Wisdom": 13, "Charisma": 10},
            "skills": {"Arcana": True, "History": True, "Investigation": True},
            "inventory": ["Quarterstaff", "Mage Armor (Active)", "Spellbook"],
            "equipment": ["Quarterstaff"],
            "spells": ["Firebolt", "Mage Armor", "Magic Missile", "Shield", "Scorching Ray"],
            "feats": [], "features": "Arcane Recovery, Sculpt Spells",
            "alignment": "Neutral Good"
        }
    }

    zenel_payload = {
        "name": "Zenel",
        "role": "Rogue",
        "race": "Halfling",
        "level": 3,
        "campaign_id": campaign_id,
        "user_id": user_id,
        "control_mode": "ai",
        "sheet_data": {
            "hp_current": 21, "hp_max": 21, "ac": 15, "initiative": 3, "speed": 25,
            "stats": {"Strength": 10, "Dexterity": 17, "Constitution": 14, "Intelligence": 12, "Wisdom": 10, "Charisma": 14},
            "skills": {"Stealth": True, "SleightofHand": True, "Acrobatics": True, "Deception": True},
            "inventory": ["Shortsword", "Dagger", "Leather Armor", "Thieves' Tools"],
            "equipment": ["Shortsword", "Leather Armor"],
            "spells": [], "feats": [], "features": "Sneak Attack (2d6), Cunning Action, Fancy Footwork",
            "alignment": "Chaotic Neutral"
        }
    }

    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Spawn Faein
        res1 = await ac.post("/characters/", json=faein_payload)
        assert res1.status_code == 200
        data1 = res1.json()
        assert data1["name"] == "Faein"
        assert data1["control_mode"] == "human"
        
        # 2. Spawn Jenath
        res2 = await ac.post("/characters/", json=jenath_payload)
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["name"] == "Jenath"
        assert data2["control_mode"] == "ai"

        # 3. Spawn Zenel
        res3 = await ac.post("/characters/", json=zenel_payload)
        assert res3.status_code == 200
        data3 = res3.json()
        assert data3["name"] == "Zenel"
        assert data3["control_mode"] == "ai"
