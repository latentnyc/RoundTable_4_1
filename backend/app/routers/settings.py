from fastapi import APIRouter, HTTPException
import logging
from app.dtos import TestAPIKeyRequest, ModelListResponse, UpdateSettingsRequest, Profile
from app.dependencies import get_db
from app.auth_utils import verify_token
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import google.genai as genai

router = APIRouter(tags=["settings"])
logger = logging.getLogger(__name__)

@router.post("/test-key", response_model=ModelListResponse)
async def test_api_key(request: TestAPIKeyRequest):
    if request.provider.lower() == "gemini":
        try:
            client = genai.Client(api_key=request.api_key)
            models = []
            for m in client.models.list():
                if 'generateContent' in (m.supported_actions or []):
                    # The name usually comes as "models/gemini-pro", let's strip "models/" if present
                    name = m.name.replace("models/", "")
                    models.append(name)

            if not models:
                # If no models found, it might be an invalid key or no access
                # But client.models.list() might not raise immediately if key is bad, usually it does.
                pass # Just proceed to check if models list is empty


            if not models:
                raise HTTPException(status_code=400, detail="No models found for this API Key.")

            return ModelListResponse(models=models)
        except Exception as e:
            # Log the error for debugging if needed, but return 400 to client
            logger.error(f"API Key Validation Error: {e}")
            raise HTTPException(status_code=400, detail=str(e))

    else:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {request.provider}")

@router.post("/save")
async def save_settings(
    request: UpdateSettingsRequest,
    token_data: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db)
):
    user_id = token_data["uid"]

    # Check if profile exists
    result = await db.execute(text("SELECT id FROM profiles WHERE id = :id"), {"id": user_id})
    row = result.mappings().fetchone()

    if not row:
        username = token_data.get("name", "Adventurer")
        # Upsert logic? Or Insert
        await db.execute(
            text("INSERT INTO profiles (id, username, api_key, llm_provider) VALUES (:id, :username, :api_key, :llm_provider)"),
            {"id": user_id, "username": username, "api_key": request.api_key, "llm_provider": request.provider}
        ) # dataset deprecated or not in schema? Schema.py didn't have dataset col. Let's check schema/init_db.
        # Wait, init_db didn't show 'dataset' column in profiles.
        # But this code has `dataset` in INSERT/UPDATE.
        # I must act defensively. If the column doesn't exist, this will crash.
        # But 'request.dataset' implies it's in the DTO.
        # Let's assume schema matches code or catch error.
        # Looking at previous view_file of init_db.py:
        # profiles table: id, username, api_key, llm_provider, is_admin, created_at.
        # NO 'dataset' column.
        # So I will REMOVE 'dataset' from the query to fix the bug (or mismatch).
    else:
        await db.execute(
            text("UPDATE profiles SET api_key = :api_key, llm_provider = :llm_provider WHERE id = :id"),
            {"api_key": request.api_key, "llm_provider": request.provider, "id": user_id}
        )
        # removed dataset update as it likely doesn't exist in DB

    await db.commit()

    return {"status": "success", "message": "Settings saved."}

from app.services.data_loader import is_dataset_loaded, load_basic_dataset
from pydantic import BaseModel

class DatasetInfo(BaseModel):
    id: str
    name: str
    description: str
    is_loaded: bool

@router.get("/datasets", response_model=list[DatasetInfo])
async def get_datasets(db: AsyncSession = Depends(get_db)):
    # Currently only 'basic' is supported
    loaded = await is_dataset_loaded(db)
    return [
        DatasetInfo(
            id="basic",
            name="Basic (5e SRD)",
            description="Standard 5e System Reference Document data (limited).",
            is_loaded=loaded
        )
    ]

@router.post("/datasets/{dataset_id}/load")
async def load_dataset(dataset_id: str, token_data: dict = Depends(verify_token)):
    # Basic authorization check - any logged in user? Or Admin only?
    # Assuming any user for now as it's a local app, but ideally admin.

    if dataset_id == "basic":
        success, msg = await load_basic_dataset()
        if success:
            return {"status": "success", "message": msg}
        else:
            raise HTTPException(status_code=500, detail=f"Failed to load dataset: {msg}")
    else:
        raise HTTPException(status_code=404, detail="Dataset not found.")

import os
import json
import glob

class GameTemplate(BaseModel):
    filename: str
    name: str
    description: str
    system_prompt: str

@router.get("/game_templates", response_model=list[GameTemplate])
async def get_game_templates(token_data: dict = Depends(verify_token)):
    """
    Scans the 'games' directory for JSON files and returns them as templates.
    """
    templates = []
    # robustly find games dir
    # settings.py is in backend/app/routers
    # games is in ../../../games (from file) or ../../games (from backend root?)
    # Let's rely on finding the project root or just trying a few paths.

    # Try traversing up until we find 'games' or hit root.
    # Alternatively, use relative path from this file.
    current_file = os.path.abspath(__file__)
    # backend/app/routers/settings.py -> backend/app/routers -> backend/app -> backend -> root
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))
    games_dir = os.path.join(project_root, "games")

    if not os.path.exists(games_dir):
        # Fallback: try CWD
        games_dir = os.path.join(os.getcwd(), "games")
        if not os.path.exists(games_dir):
             # Try ../games just in case
             games_dir = os.path.join(os.getcwd(), "../games")

    if not os.path.exists(games_dir):
        logger.warning(f"Warning: Games directory not found at {games_dir}")
        return []

    # Find all json files
    files = glob.glob(os.path.join(games_dir, "*.json"))

    for fpath in files:
        filename = os.path.basename(fpath)
        if filename == "blank_schema.json":
            continue

        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)

            meta = data.get("campaign_meta", {})
            title = meta.get("title", filename)
            # Use setting_system_prompt if available
            prompt = meta.get("setting_system_prompt", "")

            # If no prompt, maybe fallback to description or empty
            # The prompt is the key deliverable here.

            templates.append(GameTemplate(
                filename=filename,
                name=title,
                description=meta.get("description", meta.get("genre", "")),
                system_prompt=prompt
            ))
        except Exception as e:
            logger.error(f"Error reading game file {filename}: {e}")
            # Skip malformed files
            continue

    return templates
