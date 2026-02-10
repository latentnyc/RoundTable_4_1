from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict
from ..permissions import verify_token, is_admin
from ..dependencies import get_db
from ..dtos import CampaignCreateRequest, CampaignResponse, CampaignDetailsResponse, UpdateCampaignRequest, TestAPIKeyRequest, ModelListResponse
from ..models import GameState, Location
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from google import genai

router = APIRouter()

@router.post("/test_key", response_model=ModelListResponse)
async def test_api_key(
    req: TestAPIKeyRequest,
    user: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db)
):
    # Admin only
    if not await is_admin(user, db):
        raise HTTPException(status_code=403, detail="Only admins can test API keys")

    if not req.api_key:
        raise HTTPException(status_code=400, detail="API Key is required")

    try:
        # Initialize client with provided key
        client = genai.Client(api_key=req.api_key)
        
        # Verify credentials by listing models
        models = []
        # genai.Client.models.list() returns an iterable of Model objects
        # We need to filter for models that support content generation
        for m in client.models.list():
            if 'generateContent' in (m.supported_actions or []):
                # Filter for Gemini models primarily as that's what we support
                if 'gemini' in m.name.lower():
                     models.append(m.name)
        
        # Sort for better UX (newer models usually have higher numbers or 'pro'/'flash')
        models.sort(reverse=True)
        
        return ModelListResponse(models=models)

    except Exception as e:
        print(f"API Key Validation Error: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to validate API Key: {str(e)}")

@router.get("/", response_model=List[CampaignResponse])
async def list_campaigns(
    user: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db)
):
    try:
        # TODO: Filter by visibility if needed, currently showing all
        result = await db.execute(text("SELECT id, name, gm_id, status, created_at, api_key, api_key_verified FROM campaigns ORDER BY created_at DESC"))
        rows = result.mappings().all()
        return [
            CampaignResponse(
                id=row["id"],
                name=row["name"],
                gm_id=row["gm_id"],
                status=row["status"],
                created_at=row["created_at"],
                api_key_verified=row["api_key_verified"],
                api_key_configured=bool(row["api_key"])
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
    try:
        await db.execute(
            text("""INSERT INTO campaigns (id, name, gm_id, status, api_key, api_key_verified, model, system_prompt) 
               VALUES (:id, :name, :gm_id, :status, :api_key, :api_key_verified, :model, :system_prompt)"""),
            {"id": new_id, "name": req.name, "gm_id": req.gm_id, "status": "active", "api_key": req.api_key, "api_key_verified": False, "model": req.model, "system_prompt": req.system_prompt}
        )
        await db.commit()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create campaign: {e}")

    # Init Game State
    initial_state = GameState(
        session_id=new_id,
        location=Location(name="The Beginning", description="A new adventure begins."),
        party=[]
    )

    await db.execute(
        text("INSERT INTO game_states (id, campaign_id, turn_index, phase, state_data) VALUES (:id, :campaign_id, :turn_index, :phase, :state_data)"),
        {"id": str(uuid4()), "campaign_id": new_id, "turn_index": 0, "phase": "exploration", "state_data": initial_state.model_dump_json()}
    )
    await db.commit()

    return CampaignResponse(
        id=new_id,
        name=req.name,
        gm_id=req.gm_id,
        status="active",
        created_at="Just now",
        api_key_verified=False,
        api_key_configured=bool(req.api_key)
    )

@router.patch("/{campaign_id}", response_model=CampaignDetailsResponse)
async def update_campaign(
    campaign_id: str,
    req: UpdateCampaignRequest, 
    user: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db)
):
    # Verify Admin or GM
    # For now strict admin/gm check
    if not await is_admin(user, db):
         # Check if GM
         result = await db.execute(text("SELECT gm_id FROM campaigns WHERE id = :id"), {"id": campaign_id})
         row = result.mappings().fetchone()
         if not row or row['gm_id'] != user['uid']:
             raise HTTPException(status_code=403, detail="Not authorized")

    updates = []
    values = {}
    if req.name:
        updates.append("name = :name")
        values["name"] = req.name
    if req.api_key is not None:
        updates.append("api_key = :api_key")
        values["api_key"] = req.api_key
        # If key is being updated, check if verified flag is also provided
        # If not provided, assume False because key changed
        if req.api_key_verified is None:
             updates.append("api_key_verified = :api_key_verified_false")
             values["api_key_verified_false"] = False # using unique keys for safety

    if req.api_key_verified is not None:
        updates.append("api_key_verified = :api_key_verified")
        values["api_key_verified"] = req.api_key_verified

    if req.model:
        updates.append("model = :model")
        values["model"] = req.model
    if req.system_prompt:
        updates.append("system_prompt = :system_prompt")
        values["system_prompt"] = req.system_prompt

    if not updates:
         # Just return current without update
         result = await db.execute(text("SELECT * FROM campaigns WHERE id = :id"), {"id": campaign_id})
         row = result.mappings().fetchone()
         if not row: raise HTTPException(status_code=404)
         return CampaignDetailsResponse(
            id=row["id"],
            name=row["name"],
            gm_id=row["gm_id"],
            status=row["status"],
            created_at=row["created_at"],
            api_key=row["api_key"],
            api_key_verified=row["api_key_verified"],
            api_key_configured=bool(row["api_key"]),
            model=row["model"],
            system_prompt=row["system_prompt"]
        )

    values["id"] = campaign_id
    query = f"UPDATE campaigns SET {', '.join(updates)} WHERE id = :id"

    await db.execute(text(query), values)
    await db.commit()

    # Fetch updated
    result = await db.execute(text("SELECT * FROM campaigns WHERE id = :id"), {"id": campaign_id})
    row = result.mappings().fetchone()

    return CampaignDetailsResponse(
        id=row["id"],
        name=row["name"],
        gm_id=row["gm_id"],
        status=row["status"],
        created_at=row["created_at"],
        api_key=row["api_key"],
        api_key_verified=row["api_key_verified"],
        api_key_configured=bool(row["api_key"]),
        model=row["model"],
        system_prompt=row["system_prompt"]
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
    result = await db.execute(text("SELECT id FROM campaigns WHERE id = :id"), {"id": campaign_id})
    if not result.mappings().fetchone():
        raise HTTPException(status_code=404, detail="Campaign not found")

    api_key = settings.get("api_key")
    model = settings.get("model")

    updates = []
    params = {}

    if api_key is not None:
        updates.append("api_key = :api_key")
        params["api_key"] = api_key

    if model is not None:
        updates.append("model = :model")
        params["model"] = model

    if not updates:
        return {"status": "no changes"}

    params["id"] = campaign_id
    query = f"UPDATE campaigns SET {', '.join(updates)} WHERE id = :id"
    
    await db.execute(text(query), params)
    await db.commit()

    return {"status": "success", "message": "Settings updated"}

@router.get("/{campaign_id}", response_model=CampaignDetailsResponse)
async def get_campaign(
    campaign_id: str,
    user: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(text("SELECT * FROM campaigns WHERE id = :id"), {"id": campaign_id})
    row = result.mappings().fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Campaign not found")

    return CampaignDetailsResponse(
        id=row["id"],
        name=row["name"],
        gm_id=row["gm_id"],
        status=row["status"],
        created_at=row["created_at"],
        api_key=row["api_key"] if await is_admin(user, db) else None, # Hide API key from non-admins? Or return masked?
        # The prompt implies strictly admin flow for settings, so maybe users don't need it here.
        api_key_verified=row["api_key_verified"],
        api_key_configured=bool(row["api_key"]),
        model=row["model"],
        system_prompt=row["system_prompt"]
    )

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
    result = await db.execute(text("SELECT id FROM campaigns WHERE id = :id"), {"id": campaign_id})
    if not result.mappings().fetchone():
        raise HTTPException(status_code=404, detail="Campaign not found")

    try:
        # Delete related game states
        await db.execute(text("DELETE FROM game_states WHERE campaign_id = :id"), {"id": campaign_id})
        # Delete related characters
        await db.execute(text("DELETE FROM characters WHERE campaign_id = :id"), {"id": campaign_id})
        # Delete related chat messages
        await db.execute(text("DELETE FROM chat_messages WHERE campaign_id = :id"), {"id": campaign_id})
        
        # Delete the campaign
        await db.execute(text("DELETE FROM campaigns WHERE id = :id"), {"id": campaign_id})
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete campaign: {e}")

    return {"status": "success", "message": "Campaign deleted"}
