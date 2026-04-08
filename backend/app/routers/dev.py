"""
Development-only endpoints for fast iteration.

These endpoints are only active when Firebase emulators are detected
(FIREBASE_AUTH_EMULATOR_HOST is set), ensuring they never run in production.
"""
import os
import json
import logging
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert

from app.auth_utils import verify_token
from app.dependencies import get_db
from db.schema import (
    campaigns, campaign_participants, characters, profiles
)
from app.services.test_campaign_setup import (
    TEST_CAMPAIGN_ID, TEST_PARTY
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/dev", tags=["dev"])


@router.post("/quickjoin/{campaign_id}")
async def quickjoin(
    campaign_id: str,
    user: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db),
):
    """One-click join: creates a test character and joins the campaign.

    Skips the character creation wizard entirely. Creates a pre-built
    Human Fighter with longsword + shield + chain mail, ready for combat.

    Returns the character ID and campaign URL for immediate play.
    """
    if not os.getenv("FIREBASE_AUTH_EMULATOR_HOST"):
        raise HTTPException(status_code=404, detail="Not found")

    user_id = user["uid"]

    # Ensure campaign exists
    camp_result = await db.execute(
        select(campaigns.c.id).where(campaigns.c.id == campaign_id)
    )
    if not camp_result.scalar():
        raise HTTPException(status_code=404, detail=f"Campaign {campaign_id} not found")

    # Ensure user profile exists with admin status
    profile_result = await db.execute(
        select(profiles.c.id).where(profiles.c.id == user_id)
    )
    if not profile_result.scalar():
        # Create profile for this Firebase user
        display_name = user.get("name", user.get("email", "DevUser"))
        await db.execute(insert(profiles).values(
            id=user_id,
            username=display_name,
            is_admin=True,
            status="active",
        ))
        logger.info(f"Created admin profile for {display_name}")
    else:
        # Ensure admin + active
        from sqlalchemy import update
        await db.execute(
            update(profiles)
            .where(profiles.c.id == user_id)
            .values(is_admin=True, status="active")
        )

    # Ensure participant record exists
    part_result = await db.execute(
        select(campaign_participants.c.id).where(
            campaign_participants.c.campaign_id == campaign_id,
            campaign_participants.c.user_id == user_id,
        )
    )
    if not part_result.scalar():
        await db.execute(insert(campaign_participants).values(
            id=str(uuid4()),
            campaign_id=campaign_id,
            user_id=user_id,
            role="gm",
            status="active",
        ))

    # Check if user already has a character in this campaign
    char_result = await db.execute(
        select(characters.c.id, characters.c.name).where(
            characters.c.campaign_id == campaign_id,
            characters.c.user_id == user_id,
            characters.c.control_mode != "disabled",
        )
    )
    existing_char = char_result.first()

    if existing_char:
        await db.commit()
        return {
            "status": "already_joined",
            "character_id": existing_char.id,
            "character_name": existing_char.name,
            "campaign_id": campaign_id,
            "url": f"/campaign_dash/{campaign_id}",
        }

    # Create full test party: Wizard (human) + Ranger (AI) + Fighter (AI)
    created = []
    for member in TEST_PARTY:
        char_id = str(uuid4())
        await db.execute(insert(characters).values(
            id=char_id,
            user_id=user_id,
            campaign_id=campaign_id,
            name=member["name"],
            role=member["role"],
            race=member["race"],
            level=1,
            xp=0,
            sheet_data=json.dumps(member["sheet"]),
            control_mode=member["control_mode"],
        ))
        created.append({"id": char_id, "name": member["name"], "role": member["role"], "control_mode": member["control_mode"]})

    await db.commit()

    human_char = next(c for c in created if c["control_mode"] == "human")
    logger.info(f"Quickjoin: created party for user {user_id} in campaign {campaign_id}: {[c['name'] for c in created]}")

    return {
        "status": "joined",
        "character_id": human_char["id"],
        "character_name": human_char["name"],
        "party": created,
        "campaign_id": campaign_id,
        "url": f"/campaign_dash/{campaign_id}",
    }


@router.get("/test-campaign-id")
async def get_test_campaign_id():
    """Returns the stable test campaign ID for scripting/automation."""
    if not os.getenv("FIREBASE_AUTH_EMULATOR_HOST"):
        raise HTTPException(status_code=404, detail="Not found")

    return {"campaign_id": TEST_CAMPAIGN_ID}
