"""
Seed a ready-to-play test campaign on local dev startup.

Creates (if not already present):
  - A test user profile (admin)
  - A "Dev Test" campaign with the Gemini API key pre-configured and verified
  - A pre-built Fighter character assigned to the test user
  - Campaign participant record (GM role)
  - Initial game state from the Goblin Combat Test template

The dev can then:
  1. Log in via Firebase emulator (any Google account)
  2. Navigate to /campaign_dash/<id>
  3. Hit Play immediately — no setup wizard needed

Idempotent: safe to call on every startup. Skips if campaign already exists.
"""

import os
import json
import logging
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select, insert
from db.schema import campaigns, campaign_participants, characters, profiles, game_states, campaign_templates
from app.models import GameState, Player, Location, Coordinates, NPC
from app.services.campaign_loader import instantiate_campaign

logger = logging.getLogger(__name__)

# Stable IDs so we can detect "already seeded" on restart
TEST_CAMPAIGN_ID = "dev-test-campaign-001"
TEST_USER_ID = "dev-test-user-001"

# ── Pre-built party: Wizard (you) + AI Ranger (ranged) + AI Fighter (melee) ──

WIZARD_SHEET = {
    "race": "High Elf",
    "stats": {"str": 8, "dex": 14, "con": 13, "int": 16, "wis": 12, "cha": 10},
    "hp_current": 8, "hp_max": 8, "ac": 12, "speed": 30,
    "level": 1, "xp": 0,
    "control_mode": "human", "is_ai": False,
    "position": {"q": 0, "r": 0, "s": 0},
    "inventory": [],
    "equipment": [
        {"name": "Quarterstaff", "type": "Weapon", "data": {
            "type": "Simple Melee", "damage": {"damage_dice": "1d6"},
            "properties": [{"name": "Versatile"}]}},
        {"name": "Mage Armor", "type": "Armor", "data": {"type": "Light", "base_ac": 12}}
    ],
    "spells": [
        {"id": "fire-bolt", "name": "Fire Bolt"},
        {"id": "ray-of-frost", "name": "Ray of Frost"},
        {"id": "magic-missile", "name": "Magic Missile"},
    ],
    "proficiency_bonus": 2,
    "saving_throws": ["int", "wis"],
    "skills": ["arcana", "investigation", "perception"],
    "background": "Sage"
}

RANGER_SHEET = {
    "race": "Wood Elf",
    "stats": {"str": 12, "dex": 16, "con": 13, "int": 10, "wis": 14, "cha": 8},
    "hp_current": 11, "hp_max": 11, "ac": 14, "speed": 35,
    "level": 1, "xp": 0,
    "control_mode": "ai", "is_ai": True,
    "position": {"q": 0, "r": 0, "s": 0},
    "inventory": [],
    "equipment": [
        {"name": "Longbow", "type": "Weapon", "data": {
            "type": "Martial Ranged", "damage": {"damage_dice": "1d8"},
            "properties": [{"name": "Ammunition"}, {"name": "Heavy"}, {"name": "Two-Handed"}],
            "range": {"normal": 150, "long": 600}}},
        {"name": "Shortsword", "type": "Weapon", "data": {
            "type": "Martial Melee", "damage": {"damage_dice": "1d6"},
            "properties": [{"name": "Finesse"}, {"name": "Light"}]}},
        {"name": "Leather Armor", "type": "Armor", "data": {"type": "Light", "base_ac": 11}}
    ],
    "spells": [],
    "proficiency_bonus": 2,
    "saving_throws": ["str", "dex"],
    "skills": ["athletics", "perception", "stealth", "survival"],
    "background": "Outlander"
}

FIGHTER_SHEET = {
    "race": "Human",
    "stats": {"str": 16, "dex": 12, "con": 16, "int": 8, "wis": 10, "cha": 10},
    "hp_current": 13, "hp_max": 13, "ac": 18, "speed": 30,
    "level": 1, "xp": 0,
    "control_mode": "ai", "is_ai": True,
    "position": {"q": 0, "r": 0, "s": 0},
    "inventory": [],
    "equipment": [
        {"name": "Greataxe", "type": "Weapon", "data": {
            "type": "Martial Melee", "damage": {"damage_dice": "1d12"},
            "properties": [{"name": "Heavy"}, {"name": "Two-Handed"}]}},
        {"name": "Chain Mail", "type": "Armor", "data": {"type": "Heavy", "base_ac": 16}},
        {"name": "Shield", "type": "Armor", "data": {"type": "Shield", "ac_bonus": 2}}
    ],
    "spells": [],
    "proficiency_bonus": 2,
    "saving_throws": ["str", "con"],
    "skills": ["athletics", "intimidation", "perception"],
    "background": "Soldier"
}

# Combined for quickjoin: first is the human player, rest are AI
TEST_PARTY = [
    {"name": "Elara Nightwhisper", "role": "Wizard", "race": "High Elf", "sheet": WIZARD_SHEET, "control_mode": "human"},
    {"name": "Theron Swiftwind", "role": "Ranger", "race": "Wood Elf", "sheet": RANGER_SHEET, "control_mode": "ai"},
    {"name": "Bruna Stonefist", "role": "Fighter", "race": "Human", "sheet": FIGHTER_SHEET, "control_mode": "ai"},
]


async def create_test_campaign(db: AsyncSession):
    """Create a ready-to-play test campaign for local development.

    Idempotent — skips if the test campaign already exists.
    Only runs when Firebase emulators are detected (local dev).
    """
    # Only seed in local dev (emulators running)
    if not os.getenv("FIREBASE_AUTH_EMULATOR_HOST"):
        logger.info("Test campaign setup: skipped (not local dev)")
        return

    # Check if already seeded
    result = await db.execute(
        select(campaigns.c.id).where(campaigns.c.id == TEST_CAMPAIGN_ID)
    )
    if result.scalar():
        logger.info(f"Test campaign already exists ({TEST_CAMPAIGN_ID}), skipping seed")
        return

    logger.info("Seeding test campaign for local development...")

    api_key = os.getenv("GEMINI_API_KEY", "")

    try:
        # 1. Create test user profile (if not exists)
        existing_user = await db.execute(
            select(profiles.c.id).where(profiles.c.id == TEST_USER_ID)
        )
        if not existing_user.scalar():
            await db.execute(insert(profiles).values(
                id=TEST_USER_ID,
                username="DevTester",
                is_admin=True,
                status="active",
            ))
            logger.info("Created test user profile: DevTester (admin)")

        # 2. Find the Goblin Combat Test template
        template_result = await db.execute(
            select(campaign_templates.c.id, campaign_templates.c.config)
            .where(campaign_templates.c.name == "Goblin Combat Test")
        )
        template_row = template_result.first()
        template_id = template_row.id if template_row else None

        # 3. Create campaign
        await db.execute(insert(campaigns).values(
            id=TEST_CAMPAIGN_ID,
            name="Dev Test — Goblin Combat",
            gm_id=TEST_USER_ID,
            status="active",
            api_key=api_key,
            api_key_verified=bool(api_key),
            model="gemini-2.5-flash",
            system_prompt="You are a dramatic and concise Dungeon Master for a D&D 5e combat test. Keep narration to 1-2 sentences.",
            template_id=template_id,
        ))

        # 4. Instantiate template content (locations, NPCs, monsters)
        if template_id:
            await instantiate_campaign(db, TEST_CAMPAIGN_ID, template_id)
            logger.info("Instantiated Goblin Combat Test template")

        # 5. Add test user as GM participant
        await db.execute(insert(campaign_participants).values(
            id=str(uuid4()),
            campaign_id=TEST_CAMPAIGN_ID,
            user_id=TEST_USER_ID,
            role="gm",
            status="active",
        ))

        # 6. Character is NOT created here — it's created on-demand via
        # the /dev/quickjoin endpoint when a real user joins, since we
        # don't know their Firebase UID at startup time.

        # 7. Build initial game state from template
        initial_location = Location(
            name="The Beginning",
            description="A test arena.",
            walkable_hexes=[],
            party_locations=[],
        )
        initial_npcs = []

        if template_id and template_row:
            t_config = json.loads(template_row.config) if template_row.config else {}
            start_loc_id = t_config.get('starting_location')

            if start_loc_id:
                from db.schema import locations, npcs as npcs_table
                loc_result = await db.execute(
                    select(locations.c.id, locations.c.name, locations.c.data)
                    .where(locations.c.campaign_id == TEST_CAMPAIGN_ID,
                           locations.c.source_id == start_loc_id)
                )
                loc_row = loc_result.first()

                if loc_row:
                    l_data = json.loads(loc_row.data)
                    l_desc = l_data.get('description', {})
                    desc_text = l_desc.get('visual', '') if isinstance(l_desc, dict) else str(l_desc)
                    initial_location = Location(
                        id=loc_row.id,
                        source_id=start_loc_id,
                        name=loc_row.name,
                        description=desc_text,
                        interactables=l_data.get('interactables', []),
                        walkable_hexes=l_data.get('walkable_hexes', []),
                        party_locations=l_data.get('party_locations', []),
                    )

                # Load NPCs at starting location
                npc_result = await db.execute(
                    select(npcs_table.c.id, npcs_table.c.name, npcs_table.c.role, npcs_table.c.data)
                    .where(npcs_table.c.campaign_id == TEST_CAMPAIGN_ID)
                )
                for n_row in npc_result.all():
                    n_data = json.loads(n_row.data)
                    schedule = n_data.get('schedule', [])
                    is_here = any(slot.get('location') == start_loc_id for slot in schedule)
                    if is_here:
                        hp = n_data.get('stats', {}).get('hp', 10)
                        ac = n_data.get('stats', {}).get('ac', 10)
                        disposition = n_data.get('disposition', {})
                        attitude = disposition.get('attitude', '').lower()
                        if any(h in attitude for h in ['hostile', 'aggressive', 'violent']):
                            n_data['hostile'] = True
                        initial_npcs.append(NPC(
                            id=n_row.id, name=n_row.name, is_ai=True,
                            hp_current=hp, hp_max=hp, ac=ac,
                            role=n_row.role or "NPC",
                            position=Coordinates(q=0, r=0, s=0),
                            barks=n_data.get('voice', {}).get('barks'),
                            knowledge=n_data.get('knowledge', []),
                            data=n_data,
                        ))

        game_state = GameState(
            session_id=TEST_CAMPAIGN_ID,
            location=initial_location,
            party=[],  # Player is spliced in on join_campaign socket event
            npcs=initial_npcs,
        )

        await db.execute(insert(game_states).values(
            id=str(uuid4()),
            campaign_id=TEST_CAMPAIGN_ID,
            turn_index=0,
            phase="exploration",
            state_data=game_state.model_dump_json(),
        ))

        await db.commit()
        logger.info(f"Test campaign seeded successfully: {TEST_CAMPAIGN_ID}")
        logger.info(f"  -> Navigate to /campaign_dash/{TEST_CAMPAIGN_ID} after login")

    except Exception as e:
        logger.error(f"Failed to seed test campaign: {e}", exc_info=True)
        await db.rollback()
