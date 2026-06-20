"""Seed the 'Tomb of the Serpent Kings — The False Tomb' POC campaign.

Mirrors test_campaign_setup, but for the ToSK POC and seeded at Room 6 (the
skeleton ambush) per design_docs/tosk-poc-build-spec.md. It fixes the stock
seeder's hardcoded (0,0,0) NPC spawn (test_campaign_setup.py:249) by reading each
NPC's AUTHORED position, so the three skeletons sit on their coffin hexes instead
of stacking at the origin.

Run:  cd backend && venv/Scripts/python.exe -m app.services.tosk_setup
Requires the live DB; the ToSK template must already be cataloged
(`python -m app.services.campaign_loader`). For the AI DM, set GEMINI_API_KEY.
"""
import os
import json
import asyncio
import logging
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select, insert
from db.schema import (campaigns, campaign_participants, profiles, game_states,
                       campaign_templates, locations, npcs as npcs_table)
from app.models import GameState, Location, Coordinates, NPC
from app.services.campaign_loader import instantiate_campaign

logger = logging.getLogger(__name__)

TOSK_CAMPAIGN_ID = "tosk-poc-001"
TOSK_GM_ID = "dev-test-user-001"      # reuse the dev tester so the same login owns it
TOSK_TEMPLATE_ID = "tosk_false_tomb"

SYSTEM_PROMPT = (
    "You are the Dungeon Master of 'The False Tomb', the first level of the Tomb of the "
    "Serpent Kings — a grim, shoddy DECOY tomb built to fool grave-robbers. Tone: dry, "
    "old-school, faintly wry. Describe cold stone, dust, painted snake-men, and lurking "
    "danger; reward caution and cleverness. Narrate ONLY the outcomes the engine reports — "
    "never invent treasure or resolve mechanics yourself."
)


async def seed_tosk_campaign(db: AsyncSession, recreate: bool = True):
    tpl = (await db.execute(
        select(campaign_templates.c.id, campaign_templates.c.config)
        .where(campaign_templates.c.id == TOSK_TEMPLATE_ID))).first()
    if not tpl:
        logger.error("ToSK template 'tosk_false_tomb' not cataloged. "
                     "Run: python -m app.services.campaign_loader")
        return

    existing = (await db.execute(
        select(campaigns.c.id).where(campaigns.c.id == TOSK_CAMPAIGN_ID))).scalar()
    if existing:
        if not recreate:
            logger.info("ToSK campaign already exists (%s). Use recreate=True to rebuild.", TOSK_CAMPAIGN_ID)
            return
        for t in ("game_states", "npcs", "locations", "items", "monsters", "quests"):
            await db.execute(text(f"DELETE FROM {t} WHERE campaign_id=:c"), {"c": TOSK_CAMPAIGN_ID})
        await db.execute(text("DELETE FROM campaign_participants WHERE campaign_id=:c"), {"c": TOSK_CAMPAIGN_ID})
        await db.execute(text("DELETE FROM campaigns WHERE id=:c"), {"c": TOSK_CAMPAIGN_ID})
        await db.commit()

    api_key = os.getenv("GEMINI_API_KEY", "")

    if not (await db.execute(select(profiles.c.id).where(profiles.c.id == TOSK_GM_ID))).scalar():
        await db.execute(insert(profiles).values(
            id=TOSK_GM_ID, username="DevTester", is_admin=True, status="active"))

    await db.execute(insert(campaigns).values(
        id=TOSK_CAMPAIGN_ID, name="Tomb of the Serpent Kings — POC", gm_id=TOSK_GM_ID,
        status="active", api_key=api_key, api_key_verified=bool(api_key),
        model="gemini-3-flash-preview", system_prompt=SYSTEM_PROMPT,
        template_id=TOSK_TEMPLATE_ID, llm_provider="gemini"))

    await instantiate_campaign(db, TOSK_CAMPAIGN_ID, TOSK_TEMPLATE_ID)

    await db.execute(insert(campaign_participants).values(
        id=str(uuid4()), campaign_id=TOSK_CAMPAIGN_ID, user_id=TOSK_GM_ID,
        role="gm", status="active"))

    # ── Build the first GameState at the starting room (Room 6) ──
    cfg = json.loads(tpl.config) if tpl.config else {}
    start_loc_id = cfg.get("starting_location")
    initial_location = Location(name="Unknown", description="", walkable_hexes=[], party_locations=[])
    initial_npcs = []

    if start_loc_id:
        loc = (await db.execute(
            select(locations.c.id, locations.c.name, locations.c.data)
            .where(locations.c.campaign_id == TOSK_CAMPAIGN_ID,
                   locations.c.source_id == start_loc_id))).first()
        if loc:
            ld = json.loads(loc.data)
            desc = ld.get("description", {})
            dtext = desc.get("visual", "") if isinstance(desc, dict) else str(desc)
            initial_location = Location(
                id=loc.id, source_id=start_loc_id, name=loc.name, description=dtext,
                interactables=ld.get("interactables", []),
                walkable_hexes=ld.get("walkable_hexes", []),
                party_locations=ld.get("party_locations", []))

        rows = (await db.execute(
            select(npcs_table.c.id, npcs_table.c.name, npcs_table.c.role, npcs_table.c.data)
            .where(npcs_table.c.campaign_id == TOSK_CAMPAIGN_ID))).all()
        for nr in rows:
            nd = json.loads(nr.data)
            if not any(s.get("location") == start_loc_id for s in nd.get("schedule", [])):
                continue
            hp = nd.get("stats", {}).get("hp", 10)
            ac = nd.get("stats", {}).get("ac", 10)
            att = nd.get("disposition", {}).get("attitude", "").lower()
            if any(h in att for h in ("hostile", "aggressive", "violent")):
                nd["hostile"] = True
            # PATCH (spec §8.i): read the AUTHORED position, not a hardcoded (0,0,0),
            # so the three skeletons sit on their distinct coffin hexes.
            pos = nd.get("position") or {"q": 0, "r": 0, "s": 0}
            initial_npcs.append(NPC(
                id=nr.id, name=nr.name, is_ai=True, hp_current=hp, hp_max=hp, ac=ac,
                role=nr.role or "NPC",
                position=Coordinates(q=pos["q"], r=pos["r"], s=pos.get("s", -pos["q"] - pos["r"])),
                barks=nd.get("voice", {}).get("barks"),
                knowledge=nd.get("knowledge", []), data=nd))

    gs = GameState(session_id=TOSK_CAMPAIGN_ID, location=initial_location, party=[], npcs=initial_npcs)
    await db.execute(insert(game_states).values(
        id=str(uuid4()), campaign_id=TOSK_CAMPAIGN_ID, turn_index=0,
        phase="exploration", state_data=gs.model_dump_json()))
    await db.commit()

    placed = [(n.name, (n.position.q, n.position.r)) for n in initial_npcs]
    logger.info("Seeded ToSK POC: campaign=%s start=%s skeletons=%d",
                TOSK_CAMPAIGN_ID, start_loc_id, len(initial_npcs))
    logger.info("  positions: %s", placed)
    logger.info("  api_key configured: %s | dash: /campaign_dash/%s", bool(api_key), TOSK_CAMPAIGN_ID)


async def _main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    from db.session import AsyncSessionLocal, engine
    async with AsyncSessionLocal() as db:
        await seed_tosk_campaign(db, recreate=True)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(_main())
