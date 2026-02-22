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
    target_id: Optional[str] = None
    name: str
    unidentified_name: Optional[str] = None
    unidentified_description: Optional[str] = None
    llm_description: Optional[str] = None
    is_ai: bool
    hp_current: int
    hp_max: int
    ac: int = 10
    initiative: int = 0
    speed: int = 30
    position: Coordinates
    inventory: List[str | Dict] = []
    status_effects: List[str] = []
    barks: Optional[Dict[str, List[str]]] = None
    knowledge: List[Dict] = []
    loot: Optional[Dict] = None
    currency: Dict[str, int] = {"pp": 0, "gp": 0, "sp": 0, "cp": 0}
    identified: bool = True

class Vessel(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str # e.g. "Corpse of Goblin"
    description: str = "A container."
    position: Coordinates
    contents: List[str] = [] # Item IDs
    currency: Dict[str, int] = {"pp": 0, "gp": 0, "sp": 0, "cp": 0}

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
    identified: bool = False
    data: Dict = {}

# --- Game State ---
class NPC(Entity):
    role: str # e.g. "Shopkeeper"
    data: Dict = {} # Flexible storage for schedule, voice, etc.
    identified: bool = False

class DMSettings(BaseModel):
    strictness_level: Literal["strict", "normal", "relaxed", "cinematic"] = "normal"
    dice_fudging: bool = True
    narrative_focus: Literal["low", "medium", "high"] = "high"

class Location(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    source_id: Optional[str] = None # The ID from the JSON (e.g. loc_tavern)
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
    npcs: List[NPC] = []
    vessels: List[Vessel] = []
    turn_order: List[str] = []
    combat_log: List[LogEntry] = []
    dm_settings: DMSettings = Field(default_factory=DMSettings)
