from pydantic import BaseModel
from typing import Dict, Optional, List
from datetime import datetime

class CreateProfileRequest(BaseModel):
    username: str

class Profile(BaseModel):
    id: str
    username: str
    is_admin: bool = False
    status: str = "interested"

class UpdateProfileRequest(BaseModel):
    is_admin: Optional[bool] = None
    status: Optional[str] = None

class CreateCharacterRequest(BaseModel):
    user_id: str
    campaign_id: Optional[str] = None
    name: str
    role: str
    race: str = "Human" # Default
    level: int = 1
    xp: int = 0
    control_mode: str = "human"
    # dict for flexible storage of stats, skills, feats, inventory, etc.
    sheet_data: Dict = {}
    backstory: Optional[str] = None

class CharacterResponse(BaseModel):
    id: str
    user_id: str
    campaign_id: Optional[str] = None
    name: str
    role: str
    control_mode: str
    race: str
    level: int
    xp: int
    sheet_data: Dict
    backstory: Optional[str]

class TestAPIKeyRequest(BaseModel):
    provider: str
    api_key: str

class ModelListResponse(BaseModel):
    models: list[str]

class UpdateSettingsRequest(BaseModel):
    api_key: str
    provider: str = "Gemini"
    dataset: str = "5e(open)"

class UpdateCharacterRequest(BaseModel):
    control_mode: Optional[str] = None
    campaign_id: Optional[str] = None
    name: Optional[str] = None
    role: Optional[str] = None
    race: Optional[str] = None
    level: Optional[int] = None
    xp: Optional[int] = None
    sheet_data: Optional[Dict] = None
    backstory: Optional[str] = None

class CampaignCreateRequest(BaseModel):
    name: str
    gm_id: str
    api_key: str | None = None
    model: str | None = None
    system_prompt: str | None = None
    template_id: str | None = None

class CampaignTemplateResponse(BaseModel):
    id: str
    name: str
    description: str
    genre: str


class CampaignResponse(BaseModel):
    id: str
    name: str
    gm_id: str
    status: str
    created_at: str | datetime = None
    template_id: str | None = None
    api_key_verified: bool = False
    api_key_configured: bool = False

class CampaignDetailsResponse(CampaignResponse):
    api_key: Optional[str] = None
    model: Optional[str] = None
    system_prompt: Optional[str] = None
    user_status: Optional[str] = None # 'active', 'interested', 'banned', or None (not joined)
    user_role: Optional[str] = None # 'gm', 'player'
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    query_count: int = 0

class ParticipantCharacter(BaseModel):
    id: str
    name: str
    race: str
    class_name: str # 'role' in DB
    level: int

class CampaignParticipantResponse(BaseModel):
    id: str # user_id
    username: str
    role: str
    status: str
    joined_at: str | datetime
    characters: List[ParticipantCharacter] = []

class UpdateParticipantRequest(BaseModel):
    role: Optional[str] = None
    status: Optional[str] = None

class UpdateCampaignRequest(BaseModel):
    name: Optional[str] = None
    api_key: Optional[str] = None
    api_key_verified: Optional[bool] = None
    model: Optional[str] = None
    system_prompt: Optional[str] = None
