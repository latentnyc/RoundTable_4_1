from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Literal
from uuid import UUID, uuid4

# --- Fundamentals ---
class Coordinates(BaseModel):
    q: int
    r: int
    s: int # s = -q - r

class Entity(BaseModel):
    id: str
    name: str
    is_ai: bool
    hp_current: int
    hp_max: int
    ac: int = 10
    initiative: int = 0
    speed: int = 30
    position: Coordinates
    inventory: List[str] = []
    status_effects: List[str] = []

class Player(Entity):
    role: str # Class e.g. "Paladin"
    control_mode: str = "human" # "human", "ai", "disabled"
    race: str = "Human" # Default
    level: int = 1
    xp: int = 0
    user_id: Optional[str] = None
    # dict for flexible storage of stats, skills, feats, etc.
    sheet_data: Dict = {} 

class Enemy(Entity):
    type: str # e.g. "Goblin"

# --- Game State ---
class DMSettings(BaseModel):
    strictness_level: Literal["strict", "normal", "relaxed", "cinematic"] = "normal"
    dice_fudging: bool = True
    narrative_focus: Literal["low", "medium", "high"] = "high"

class Location(BaseModel):
    name: str
    description: str

class LogEntry(BaseModel):
    tick: int
    actor_id: str
    action: str
    target_id: Optional[str] = None
    result: str
    timestamp: str

class GameState(BaseModel):
    session_id: str
    turn_index: int = 0
    phase: Literal["combat", "exploration", "social"] = "exploration"
    active_entity_id: Optional[str] = None
    location: Location
    party: List[Player]
    enemies: List[Enemy] = []
    combat_log: List[LogEntry] = []
    dm_settings: DMSettings = Field(default_factory=DMSettings)
