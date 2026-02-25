from pydantic import BaseModel, Field, model_validator
from typing import List, Dict, Optional, Literal, Any
from uuid import UUID, uuid4

# --- Fundamentals ---
class Coordinates(BaseModel):
    q: int
    r: int
    s: int # s = -q - r

    def distance_to(self, other: 'Coordinates') -> int:
        return max(abs(self.q - other.q), abs(self.r - other.r), abs(self.s - other.s))

    def get_line_to(self, other: 'Coordinates') -> List['Coordinates']:
        def cube_lerp(aq: float, ar: float, b_q: float, b_r: float, t: float):
            return (aq + (b_q - aq) * t, ar + (b_r - ar) * t, (-aq-ar) + ((-b_q-b_r) - (-aq-ar)) * t)
        
        def cube_round(frac_q: float, frac_r: float, frac_s: float):
            q, r, s = round(frac_q), round(frac_r), round(frac_s)
            q_diff, r_diff, s_diff = abs(q - frac_q), abs(r - frac_r), abs(s - frac_s)
            if q_diff > r_diff and q_diff > s_diff:
                q = -r - s
            elif r_diff > s_diff:
                r = -q - s
            else:
                s = -q - r
            return (int(q), int(r), int(s))

        N = self.distance_to(other)
        if N == 0:
            return [self]
            
        # Nudge to break ties exactly on hex edges
        a_q, a_r = float(self.q) + 1e-6, float(self.r) + 2e-6
        b_q, b_r = float(other.q) + 1e-6, float(other.r) + 2e-6
        
        results = []
        for i in range(N + 1):
            t = float(i) / N
            fq, fr, fs = cube_lerp(a_q, a_r, b_q, b_r, t)
            rq, rr, rs = cube_round(fq, fr, fs)
            results.append(Coordinates(q=rq, r=rr, s=rs))
        return results

class Stats(BaseModel):
    model_config = {"populate_by_name": True}
    strength: int = Field(10, alias="str")
    dexterity: int = Field(10, alias="dex")
    constitution: int = Field(10, alias="con")
    intelligence: int = Field(10, alias="int")
    wisdom: int = Field(10, alias="wis")
    charisma: int = Field(10, alias="cha")

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
    inventory: List[str] = []
    status_effects: List[str] = []
    barks: Optional[Dict[str, List[str]]] = None
    knowledge: List[Dict[str, Any]] = []
    loot: Optional[Dict[str, Any]] = None
    currency: Dict[str, int] = {"pp": 0, "gp": 0, "sp": 0, "cp": 0}
    identified: bool = True
    
    # Newly promoted explicit fields from 'data' / 'sheet_data'
    race: str = "Unknown"
    stats: Stats = Field(default_factory=Stats)
    voice: Dict[str, Any] = {}

    @model_validator(mode='before')
    @classmethod
    def flatten_data_fields(cls, values: Any) -> Any:
        # Gracefully handle loading if incoming values is a dict
        if isinstance(values, dict):
            # Flatten 'data' for Enemies/NPCs
            data = values.get('data', {})
            if isinstance(data, dict):
                for key in ['race', 'stats', 'voice', 'hostile', 'friendly', 'ally', 'type']:
                    if key in data and key not in values:
                        values[key] = data[key]
                        
            # Flatten 'sheet_data' for Players
            sheet_data = values.get('sheet_data', {})
            if isinstance(sheet_data, dict):
                for key in ['race', 'stats']:
                    if key in sheet_data and key not in values:
                        values[key] = sheet_data[key]
        return values

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
    level: int = 1
    xp: int = 0
    user_id: Optional[str] = None
    # Now just a catch-all for truly generic things, core properties promoted
    sheet_data: Dict[str, Any] = {}

class Enemy(Entity):
    type: str # e.g. "Goblin"
    identified: bool = False
    hostile: bool = True
    ally: bool = False
    data: Dict[str, Any] = {}

# --- Game State ---
class NPC(Entity):
    role: str # e.g. "Shopkeeper"
    identified: bool = False
    
    # Explicit diplomacy fields
    hostile: bool = False
    friendly: bool = False
    ally: bool = False
    
    data: Dict[str, Any] = {} # Catch-all for schedules, remaining unstructured params

class DMSettings(BaseModel):
    strictness_level: Literal["strict", "normal", "relaxed", "cinematic"] = "normal"
    dice_fudging: bool = True
    narrative_focus: Literal["low", "medium", "high"] = "high"

class Location(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    source_id: Optional[str] = None # The ID from the JSON (e.g. loc_tavern)
    name: str
    description: str
    interactables: List[Dict[str, Any]] = []
    walkable_hexes: List[Coordinates] = Field(default_factory=list)
    party_locations: List[Dict[str, Any]] = Field(default_factory=list)

    @model_validator(mode='after')
    def enforce_spawn_hexes_are_walkable(self) -> 'Location':
        if self.party_locations and self.walkable_hexes is not None:
            existing = {(h.q, h.r, h.s) for h in self.walkable_hexes}
            for p_loc in self.party_locations:
                pos = p_loc.get('position')
                if pos:
                    coord = Coordinates(**pos) if isinstance(pos, dict) else pos
                    if (coord.q, coord.r, coord.s) not in existing:
                        self.walkable_hexes.append(coord)
                        existing.add((coord.q, coord.r, coord.s))
        return self

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
    discovered_locations: List[Location] = Field(default_factory=list)
    party: List[Player]
    enemies: List[Enemy] = []
    npcs: List[NPC] = []
    vessels: List[Vessel] = []
    turn_order: List[str] = []
    combat_log: List[LogEntry] = []
    dm_settings: DMSettings = Field(default_factory=DMSettings)
    has_moved_this_turn: bool = False
    has_acted_this_turn: bool = False
