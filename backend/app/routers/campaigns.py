from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict
import json
import logging
from ..permissions import verify_token, is_admin
from ..dependencies import get_db
from ..dtos import (
    CampaignCreateRequest, CampaignResponse, CampaignDetailsResponse,
    UpdateCampaignRequest, TestAPIKeyRequest, ModelListResponse,
    CampaignParticipantResponse, ParticipantCharacter, UpdateParticipantRequest,
    CampaignTemplateResponse, ImageGenerationRequest, ImageGenerationResponse
)
from ..models import GameState, Location, NPC, Coordinates
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert, update, delete, desc, text
from db.schema import campaigns, campaign_templates, campaign_participants, game_states, characters, chat_messages, npcs, locations, debug_logs, profiles
from ..services.campaign_loader import instantiate_campaign

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/test_key", response_model=ModelListResponse)
async def test_api_key(
    req: TestAPIKeyRequest,
    user: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db)
):
    from app.services.system_service import SystemService
    # Admin only
    if not await is_admin(user, db):
        raise HTTPException(status_code=403, detail="Only admins can test API keys")

    try:
        api_key_to_use = req.api_key
        if not api_key_to_use:
             import os
             api_key_to_use = os.getenv("GEMINI_API_KEY")

        models = SystemService.validate_api_key(api_key_to_use, req.provider)
        return ModelListResponse(models=models)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"API Key Validation Error: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to validate API Key: {str(e)}")

@router.get("/templates", response_model=List[CampaignTemplateResponse])
async def list_templates(
    user: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db)
):
    try:
        query = select(campaign_templates.c.id, campaign_templates.c.name, campaign_templates.c.description, campaign_templates.c.genre).order_by(campaign_templates.c.name)
        result = await db.execute(query)
        rows = result.all()
        return [
            CampaignTemplateResponse(
                id=row.id,
                name=row.name,
                description=row.description,
                genre=row.genre
            )
            for row in rows
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list templates: {e}")

@router.get("/", response_model=List[CampaignResponse])
async def list_campaigns(
    user: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db)
):
    try:
        query = select(
            campaigns.c.id, campaigns.c.name, campaigns.c.gm_id,
            campaigns.c.status, campaigns.c.created_at,
            campaigns.c.api_key_verified, campaigns.c.api_key
        ).order_by(desc(campaigns.c.created_at))

        result = await db.execute(query)
        rows = result.all()
        import os
        return [
            CampaignResponse(
                id=row.id,
                name=row.name,
                gm_id=row.gm_id,
                status=row.status,
                created_at=row.created_at,
                api_key_verified=row.api_key_verified,
                api_key_configured=bool(row.api_key or os.getenv("GEMINI_API_KEY"))
            )
            for row in rows
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list campaigns: {e}")

@router.post("/", response_model=CampaignResponse)
async def create_campaign(
    req: CampaignCreateRequest,
    user: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db)
):
    # Enforce Admin Only
    if not await is_admin(user, db):
        raise HTTPException(status_code=403, detail="Only admins can create campaigns")

    new_id = str(uuid4())

    # Resolve API Key
    api_key_to_use = req.api_key
    if not api_key_to_use:
        import os
        api_key_to_use = os.getenv("GEMINI_API_KEY")

    # Verify API Key if provided
    is_verified = False
    if api_key_to_use:
        try:
            # We need to import genai here or uses SystemService
            from app.services.system_service import SystemService
            try:
                SystemService.validate_api_key(api_key_to_use)
                is_verified = True
            except ValueError:
                pass # valid to leave unverified if check fails but we still save it?
                     # The original code just printed error and left it unverified.
        except Exception as e:
            logger.warning(f"Pre-verification field for new campaign key: {e}")

    # Default Model
    model_to_use = req.model
    if not model_to_use:
        model_to_use = "gemini-2.5-flash"

    try:
        # Create Campaign
        stmt = insert(campaigns).values(
            id=new_id,
            name=req.name,
            gm_id=req.gm_id,
            status="active",
            api_key=api_key_to_use,
            api_key_verified=is_verified,
            model=model_to_use,
            system_prompt=req.system_prompt,
            template_id=req.template_id
        )
        await db.execute(stmt)

        # Instantiate Template Content if provided
        if req.template_id:
             await instantiate_campaign(db, new_id, req.template_id)

        # Auto-join Creator as GM
        stmt_part = insert(campaign_participants).values(
            id=str(uuid4()),
            campaign_id=new_id,
            user_id=req.gm_id,
            role="gm",
            status="active"
        )
        await db.execute(stmt_part)

        await db.commit()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create campaign: {e}")

    # Init Game State
    initial_location_name = "The Beginning"
    initial_location_desc = "" # Empty to prevent premature image gen
    initial_location_source_id = None
    initial_location_id = str(uuid4()) # Default if not found

    initial_npcs = []

    # Try to get specific starting location from template if available
    try:
        if req.template_id:
             # Get Template Config
             query = select(campaign_templates.c.config).where(campaign_templates.c.id == req.template_id)
             t_res = await db.execute(query)
             t_config_str = t_res.scalar()

             if t_config_str:
                 t_config = json.loads(t_config_str)
                 start_loc_id = t_config.get('starting_location')

                 if start_loc_id:
                     # Fetch full location data
                     query_loc = select(locations.c.id, locations.c.name, locations.c.data).where(
                         locations.c.campaign_id == new_id,
                         locations.c.source_id == start_loc_id
                     )
                     l_res = await db.execute(query_loc)
                     l_row = l_res.first()

                     if l_row:
                         initial_location_name = l_row.name
                         initial_location_source_id = start_loc_id
                         initial_location_id = l_row.id

                         l_data = json.loads(l_row.data)
                         l_desc = l_data.get('description', {})
                         if isinstance(l_desc, dict):
                             initial_location_desc = l_desc.get('visual', "A mystery location.")
                         else:
                             initial_location_desc = str(l_desc)

                     # Fetch NPCs present at this location
                     query_npcs = select(npcs.c.id, npcs.c.name, npcs.c.role, npcs.c.data).where(
                         npcs.c.campaign_id == new_id
                     )
                     n_res = await db.execute(query_npcs)
                     all_npcs = n_res.all()

                     for n_row in all_npcs:
                         n_data = json.loads(n_row.data)
                         schedule = n_data.get('schedule', [])
                         is_here = False
                         for slot in schedule:
                             if slot.get('location') == start_loc_id:
                                 is_here = True
                                 break

                         if is_here:
                             # Create NPC Entity
                             hp = n_data.get('stats', {}).get('hp', 10)
                             ac = n_data.get('stats', {}).get('ac', 10)

                             # Hostility Sync
                             disposition = n_data.get('disposition', {})
                             attitude = disposition.get('attitude', '').lower()
                             HOSTILE_ATTITUDES = ['hostile', 'aggressive', 'violent', 'enemy', 'attack on sight']

                             if any(h in attitude for h in HOSTILE_ATTITUDES):
                                 if 'hostile' not in n_data:
                                     n_data['hostile'] = True

                             initial_npcs.append(NPC(
                                 id=n_row.id,
                                 name=n_row.name,
                                 is_ai=True,
                                 hp_current=hp,
                                 hp_max=hp,
                                 ac=ac,
                                 role=n_row.role,
                                 target_id=n_data.get('target_id'),
                                 unidentified_name=n_data.get('unidentified_name'),
                                 unidentified_description=n_data.get('unidentified_description'),
                                 llm_description=n_data.get('llm_description'),
                                 position=Coordinates(q=0, r=0, s=0),
                                 barks=n_data.get('voice', {}).get('barks'),
                                 knowledge=n_data.get('knowledge', []),
                                 loot=n_data.get('loot'),
                                 data=n_data
                             ))

    except Exception as e:
        logger.error(f"Error checking starting location/NPCs: {e}")
        import traceback
        logger.error(traceback.format_exc())

    initial_state = GameState(
        session_id=new_id,
        location=Location(
            id=initial_location_id,
            source_id=initial_location_source_id,
            name=initial_location_name,
            description=initial_location_desc
        ),
        party=[],
        npcs=initial_npcs
    )

    stmt_state = insert(game_states).values(
        id=str(uuid4()),
        campaign_id=new_id,
        turn_index=0,
        phase="exploration",
        state_data=initial_state.model_dump_json()
    )
    await db.execute(stmt_state)
    await db.commit()

    return CampaignResponse(
        id=new_id,
        name=req.name,
        gm_id=req.gm_id,
        status="active",
        created_at="Just now",
        api_key_verified=is_verified,
        api_key_configured=bool(req.api_key),
        template_id=req.template_id
    )

@router.patch("/{campaign_id}", response_model=CampaignDetailsResponse)
async def update_campaign(
    campaign_id: str,
    req: UpdateCampaignRequest,
    user: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db)
):
    # Verify Admin or GM
    if not await is_admin(user, db):
         # Check if GM
         query = select(campaigns.c.gm_id).where(campaigns.c.id == campaign_id)
         result = await db.execute(query)
         gm_id = result.scalar()
         if not gm_id or gm_id != user['uid']:
             raise HTTPException(status_code=403, detail="Not authorized")

    values = {}
    if req.name:
        values["name"] = req.name
    if req.api_key is not None:
        values["api_key"] = req.api_key
        # If key is being updated, check if verified flag is also provided
        # If not provided, assume False because key changed
        if req.api_key_verified is None:
             values["api_key_verified"] = False

    if req.api_key_verified is not None:
        values["api_key_verified"] = req.api_key_verified

    if req.model:
        values["model"] = req.model
    if req.system_prompt:
        values["system_prompt"] = req.system_prompt

    if values:
        stmt = (
            update(campaigns)
            .where(campaigns.c.id == campaign_id)
            .values(**values)
        )
        await db.execute(stmt)
        await db.commit()

    # Fetch updated
    query = select(campaigns).where(campaigns.c.id == campaign_id)
    result = await db.execute(query)
    row = result.first()

    if not row: raise HTTPException(status_code=404)

    import os
    return CampaignDetailsResponse(
        id=row.id,
        name=row.name,
        gm_id=row.gm_id,
        status=row.status,
        created_at=row.created_at,
        api_key=None, # NEVER expose to frontend
        api_key_verified=row.api_key_verified,
        api_key_configured=bool(row.api_key or os.getenv("GEMINI_API_KEY")),
        model=row.model,
        system_prompt=row.system_prompt
    )

@router.put("/{campaign_id}/settings")
async def update_campaign_settings(
    campaign_id: str,
    settings: dict,
    user: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db)
):
    # Verify Admin
    if not await is_admin(user, db):
        raise HTTPException(status_code=403, detail="Only admins can modify campaign settings")

    # Validate Campaign Existence
    query = select(campaigns.c.id).where(campaigns.c.id == campaign_id)
    result = await db.execute(query)
    if not result.first():
        raise HTTPException(status_code=404, detail="Campaign not found")

    api_key = settings.get("api_key")
    model = settings.get("model")

    values = {}
    if api_key is not None:
        values["api_key"] = api_key
    if model is not None:
        values["model"] = model

    if not values:
        return {"status": "no changes"}

    stmt = (
        update(campaigns)
        .where(campaigns.c.id == campaign_id)
        .values(**values)
    )

    await db.execute(stmt)
    await db.commit()

    return {"status": "success", "message": "Settings updated"}

@router.get("/{campaign_id}", response_model=CampaignDetailsResponse)
async def get_campaign(
    campaign_id: str,
    user: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db)
):
    query = select(campaigns).where(campaigns.c.id == campaign_id)
    result = await db.execute(query)
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Campaign not found")

    # Get user participant status
    user_status = None
    user_role = None

    # Check if user is participant
    p_query = select(campaign_participants.c.role, campaign_participants.c.status).where(
        campaign_participants.c.campaign_id == campaign_id,
        campaign_participants.c.user_id == user['uid']
    )
    part_result = await db.execute(p_query)
    part_row = part_result.first()

    if part_row:
        user_status = part_row.status
        user_role = part_row.role
    elif await is_admin(user, db):
        pass

    import os
    return CampaignDetailsResponse(
        id=row.id,
        name=row.name,
        gm_id=row.gm_id,
        status=row.status,
        created_at=row.created_at,
        api_key=None, # NEVER expose to frontend
        api_key_verified=row.api_key_verified,
        api_key_configured=bool(row.api_key or os.getenv("GEMINI_API_KEY")),
        model=row.model,
        system_prompt=row.system_prompt,
        user_status=user_status,
        user_role=user_role,
        total_input_tokens=row.total_input_tokens or 0,
        total_output_tokens=row.total_output_tokens or 0,
        query_count=row.query_count or 0
    )

@router.post("/{campaign_id}/join")
async def join_campaign(
    campaign_id: str,
    user: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db)
):
    # Check if campaign exists
    camp_result = await db.execute(text("SELECT * FROM campaigns WHERE id = :id"), {"id": campaign_id})
    camp = camp_result.mappings().fetchone()
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")

    # Check if already joined
    part_result = await db.execute(
        text("SELECT * FROM campaign_participants WHERE campaign_id = :cid AND user_id = :uid"),
        {"cid": campaign_id, "uid": user['uid']}
    )
    if part_result.mappings().fetchone():
        return {"message": "Already joined"}

    # Determine Role/Status
    role = "player"
    status = "interested"

    # If Admin -> Active
    if await is_admin(user, db):
        status = "active"

    # If User is GM (by ID match on campaign) -> GM, Active
    # (Should have happened at creation, but just in case)
    if camp['gm_id'] == user['uid']:
        role = "gm"
        status = "active"

    await db.execute(
        text("INSERT INTO campaign_participants (id, campaign_id, user_id, role, status) VALUES (:id, :cid, :uid, :role, :status)"),
        {"id": str(uuid4()), "cid": campaign_id, "uid": user['uid'], "role": role, "status": status}
    )
    await db.commit()
    return {"status": status, "role": role}


@router.get("/{campaign_id}/participants", response_model=List[CampaignParticipantResponse])
async def list_participants(
    campaign_id: str,
    user: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db)
):
    logger.info(f"[DEBUG] Listing participants for campaign {campaign_id} user {user['uid']}")

    # Auth Check: Must be participant (or Admin) to see list?
    if not await is_admin(user, db):
        query = select(campaign_participants.c.status).where(
            campaign_participants.c.campaign_id == campaign_id,
            campaign_participants.c.user_id == user['uid']
        )
        check = await db.execute(query)
        if not check.scalar():
             logger.warning(f"[DEBUG] User {user['uid']} not in campaign {campaign_id}")
             raise HTTPException(status_code=403, detail="Must join campaign to view participants")

    # Fetch Participants + Profile Info
    # JOIN users and participants
    j_query = (
        select(
            campaign_participants.c.user_id.label("id"),
            campaign_participants.c.role,
            campaign_participants.c.status,
            campaign_participants.c.joined_at,
            profiles.c.username
        )
        .select_from(
            campaign_participants.join(profiles, campaign_participants.c.user_id == profiles.c.id)
        )
        .where(campaign_participants.c.campaign_id == campaign_id)
        .order_by(campaign_participants.c.joined_at)
    )

    result = await db.execute(j_query)
    users = result.all()
    logger.info(f"[DEBUG] Found {len(users)} participants")

    # Fetch Characters for all these users in this campaign
    chars_by_user = {}
    if users:
        c_query = select(
            characters.c.id, characters.c.user_id, characters.c.name,
            characters.c.race, characters.c.role.label("class_name"), characters.c.level
        ).where(characters.c.campaign_id == campaign_id)

        c_result = await db.execute(c_query)
        chars = c_result.all()

    # chars_by_user logic
    # chars_by_user logic
    chars_by_user = {}
    for c in chars:
        uid = str(c.user_id)
        if uid not in chars_by_user:
            chars_by_user[uid] = []
        chars_by_user[uid].append({
            "id": str(c.id),
            "name": c.name,
            "race": c.race or "Unknown",
            "class_name": c.class_name, # aliased
            "level": c.level
        })

    response = []
    for u in users:
        # u is a Row object
        uid = str(u.id)
        response.append(CampaignParticipantResponse(
            id=uid, # user_id
            username=u.username,
            role=u.role,
            status=u.status,
            joined_at=u.joined_at,
            characters=chars_by_user.get(uid, [])
        ))

    return response

@router.patch("/{campaign_id}/participants/{target_user_id}")
async def update_participant(
    campaign_id: str,
    target_user_id: str,
    req: UpdateParticipantRequest,
    user: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db)
):
    # Verify Requester is GM or Admin
    if not await is_admin(user, db):
        # Check if GM
        query = select(campaign_participants.c.role).where(
            campaign_participants.c.campaign_id == campaign_id,
            campaign_participants.c.user_id == user['uid'],
            campaign_participants.c.role == 'gm',
            campaign_participants.c.status == 'active'
        )
        gm_check = await db.execute(query)
        if not gm_check.scalar():
            raise HTTPException(status_code=403, detail="Only GM or Admin can manage participants")

    values = {}
    if req.role:
        values["role"] = req.role
    if req.status:
        values["status"] = req.status

    if not values:
        return {"status": "no changes"}

    stmt = (
        update(campaign_participants)
        .where(
            campaign_participants.c.campaign_id == campaign_id,
            campaign_participants.c.user_id == target_user_id
        )
        .values(**values)
    )

    await db.execute(stmt)
    await db.commit()

    return {"status": "success"}

@router.delete("/{campaign_id}")
async def delete_campaign(
    campaign_id: str,
    user: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db)
):
    # Admin only
    if not await is_admin(user, db):
        raise HTTPException(status_code=403, detail="Only admins can delete campaigns")

    # Check existence
    query = select(campaigns.c.id).where(campaigns.c.id == campaign_id)
    result = await db.execute(query)
    if not result.first():
        raise HTTPException(status_code=404, detail="Campaign not found")

    try:
        # Delete related game states
        await db.execute(delete(game_states).where(game_states.c.campaign_id == campaign_id))
        # Delete related characters
        await db.execute(delete(characters).where(characters.c.campaign_id == campaign_id))
        # Delete related chat messages
        await db.execute(delete(chat_messages).where(chat_messages.c.campaign_id == campaign_id))
        # Delete participants
        await db.execute(delete(campaign_participants).where(campaign_participants.c.campaign_id == campaign_id))

        # Delete the campaign
        await db.execute(delete(campaigns).where(campaigns.c.id == campaign_id))

        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete campaign: {e}")


@router.get("/{campaign_id}/logs")
async def get_campaign_logs(
    campaign_id: str,
    limit: int = 50,
    user: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db)
):
    # Verify Admin or Participant
    if not await is_admin(user, db):
        # Check if participant
        query = select(campaign_participants.c.status).where(
            campaign_participants.c.campaign_id == campaign_id,
            campaign_participants.c.user_id == user['uid']
        )
        check = await db.execute(query)
        if not check.scalar():
             raise HTTPException(status_code=403, detail="Access denied")

    try:
        query = (
            select(debug_logs.c.type, debug_logs.c.content, debug_logs.c.full_content, debug_logs.c.created_at)
            .where(debug_logs.c.campaign_id == campaign_id)
            .order_by(desc(debug_logs.c.created_at))
            .limit(limit)
        )
        result = await db.execute(query)
        rows = result.all()

        return [
            {
                "type": row.type,
                "content": row.content,
                "full_content": row.full_content,
                "created_at": row.created_at
            }
            for row in rows
        ]
    except Exception as e:
        logger.error(f"Error fetching logs: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch logs")

@router.post("/{campaign_id}/images/generate", response_model=ImageGenerationResponse)
async def generate_campaign_image(
    campaign_id: str,
    req: ImageGenerationRequest,
    user: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db)
):
    from app.services.ai_service import AIService
    import hashlib
    from db.schema import image_cache
    from sqlalchemy import select, insert
    import base64

    # Check if participant
    if not await is_admin(user, db):
         query = select(campaign_participants.c.status).where(
             campaign_participants.c.campaign_id == campaign_id,
             campaign_participants.c.user_id == user['uid']
         )
         check = await db.execute(query)
         if not check.scalar():
              raise HTTPException(status_code=403, detail="Access denied")

    # Hash the prompt for caching
    prompt_hash = hashlib.sha256(req.prompt.encode('utf-8')).hexdigest()

    # Check Cache
    try:
        cache_query = select(image_cache.c.image_base64).where(image_cache.c.prompt_hash == prompt_hash)
        cache_res = await db.execute(cache_query)
        cached_img = cache_res.scalar()
        if cached_img:
            return ImageGenerationResponse(
                image_base64=cached_img,
                prompt_used=req.prompt
            )
    except Exception as e:
        logger.warning(f"Cache read error: {e}")

    # Generate Image via AI
    image_bytes = await AIService.generate_scene_image(campaign_id, req.prompt, db)
    if not image_bytes:
        raise HTTPException(status_code=500, detail="Failed to generate image")

    b64_img = base64.b64encode(image_bytes).decode('utf-8')

    # Save cache
    try:
        stmt = insert(image_cache).values(
            prompt_hash=prompt_hash,
            image_base64=b64_img
        )
        await db.execute(stmt)
        await db.commit()
    except Exception as e:
         logger.warning(f"Cache write error: {e}")
         await db.rollback()

    # Broadcast stats
    from app.socket_manager import sio
    await sio.emit('ai_stats', {
        'type': 'usage',
        'is_image': True,
        'model': 'imagen-4.0-fast-generate-001'
    }, room=campaign_id)

    return ImageGenerationResponse(
        image_base64=b64_img,
        prompt_used=req.prompt
    )
