from pydantic import BaseModel, Field, model_validator
from typing import List, Dict, Optional, Literal, Any
from uuid import UUID, uuid4

# --- Conditions ---
class Condition(BaseModel):
    """An active condition on an entity (Blinded, Stunned, etc.)."""
    name: str                          # e.g. "Blinded", "Poisoned"
    duration: int = -1                 # Rounds remaining. -1 = permanent, 0 = expired (remove)
    expires_on: Literal["start", "end"] = "start"  # Expires at start or end of affected entity's turn
    source_id: Optional[str] = None    # Who/what applied this condition
    save_dc: Optional[int] = None      # DC for save to end early (if applicable)
    save_stat: Optional[str] = None    # Ability to save with (e.g. "wisdom")

# --- Fundamentals ---
class Coordinates(BaseModel):
    x: int
    y: int

    def distance_to(self, other: 'Coordinates') -> int:
        # Chebyshev (8-way) distance: every step, orthogonal or diagonal, costs 1 cell.
        return max(abs(self.x - other.x), abs(self.y - other.y))

    def get_line_to(self, other: 'Coordinates') -> List['Coordinates']:
        """
        True supercover line from self to other (inclusive). Includes every cell the
        segment passes through, including BOTH flanking cells at a diagonal corner
        crossing, so a diagonal wall blocks line-of-sight (no corner-cutting).
        """
        x0, y0 = self.x, self.y
        x1, y1 = other.x, other.y
        dx, dy = abs(x1 - x0), abs(y1 - y0)
        sx = 1 if x1 > x0 else -1
        sy = 1 if y1 > y0 else -1

        cells = [Coordinates(x=x0, y=y0)]
        if dx == 0 and dy == 0:
            return cells

        x, y = x0, y0
        err = dx - dy
        n = dx + dy
        while n > 0:
            e2 = 2 * err
            if e2 == 0:
                # Exact corner crossing: emit BOTH flanking cells, then step diagonally.
                cells.append(Coordinates(x=x + sx, y=y))
                cells.append(Coordinates(x=x, y=y + sy))
                x += sx
                y += sy
                err += dx - dy
                n -= 2
            elif e2 > -dy:
                err -= dy
                x += sx
                n -= 1
            else:
                err += dx
                y += sy
                n -= 1
            cells.append(Coordinates(x=x, y=y))
        return cells

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
    conditions: List[Condition] = []
    concentrating_on: Optional[str] = None  # Spell name being concentrated on
    concentration_target_id: Optional[str] = None  # Entity affected by concentration spell
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
                for key in ['race', 'stats', 'voice', 'hostile', 'friendly', 'ally', 'type', 'conditions']:
                    if key in data and key not in values:
                        values[key] = data[key]
                        
            # Flatten 'sheet_data' for Players
            sheet_data = values.get('sheet_data', {})
            if isinstance(sheet_data, dict):
                for key in ['race', 'stats']:
                    if key in sheet_data and key not in values:
                        values[key] = sheet_data[key]

            # Backward compat: migrate old status_effects: List[str] to conditions: List[Condition]
            if 'status_effects' in values and 'conditions' not in values:
                old_effects = values.pop('status_effects', [])
                if old_effects and isinstance(old_effects, list):
                    values['conditions'] = [
                        {"name": e} if isinstance(e, str) else e
                        for e in old_effects
                    ]
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
    walkable_cells: List[Coordinates] = Field(default_factory=list)
    party_locations: List[Dict[str, Any]] = Field(default_factory=list)

    @model_validator(mode='after')
    def enforce_spawn_cells_are_walkable(self) -> 'Location':
        if self.party_locations and self.walkable_cells is not None:
            existing = {(h.x, h.y) for h in self.walkable_cells}
            for p_loc in self.party_locations:
                pos = p_loc.get('position')
                if pos:
                    coord = Coordinates(**pos) if isinstance(pos, dict) else pos
                    if (coord.x, coord.y) not in existing:
                        self.walkable_cells.append(coord)
                        existing.add((coord.x, coord.y))
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
    version: int = 0
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
