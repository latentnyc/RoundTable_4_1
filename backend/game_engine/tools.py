from typing import Optional, Type, List
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from .engine import GameEngine
from sqlalchemy.ext.asyncio import AsyncSession

engine = GameEngine()

# --- INPUT MODELS ---

class AttackInput(BaseModel):
    attacker_name: str = Field(description="Name of the entity attacking")
    target_name: str = Field(description="Name of the entity being attacked")
    weapon: Optional[str] = Field(default="sword", description="Weapon used (flavor text for now)")

class CheckInput(BaseModel):
    character_name: str = Field(description="Name of the entity making the check")
    stat: str = Field(description="Stat to check (strength, dexterity, constitution, intelligence, wisdom, charisma)")
    dc: int = Field(default=10, description="Difficulty Class of the check")

class MoveInput(BaseModel):
    actor_name: str = Field(description="Name of the character requesting the move")
    direction: str = Field(description="Direction or target destination (e.g. 'north', 'south', 'Barleyrest Town Square')")

class EndTurnInput(BaseModel):
    reason: Optional[str] = Field(default="", description="Reason for ending turn")

# --- TOOLS ---

class AttackTool(BaseTool):
    name: str = "attack"
    description: str = "Perform an attack against a target. Uses Strength by default."
    args_schema: Type[BaseModel] = AttackInput

    def _run(self, attacker_name: str, target_name: str, weapon: str = "sword") -> str:
        # Fallback to mock data for synchronous execution without DB context
        mock_actor = {"name": attacker_name, "stats": {"strength": 16, "dexterity": 12}, "hp": {"current": 20, "max": 20}}
        mock_target = {"name": target_name, "stats": {"dexterity": 10}, "hp": {"current": 10, "max": 10}}
        return engine.resolve_action(mock_actor, "attack", mock_target)

    async def execute_with_db(self, db: AsyncSession, campaign_id: str, attacker_name: str, target_name: str, weapon: str = "sword") -> str:
        """Asynchronously executes the attack resolution using the active database session."""
        from app.services.combat_service import CombatService
        res = await CombatService.resolution_attack(
            campaign_id=campaign_id,
            attacker_id=None,
            attacker_name=attacker_name,
            target_name=target_name,
            db=db,
            commit=True
        )
        if not res.get("success"):
            return f"Attack failed: {res.get('message')}"
        
        msg = res.get("message", "")
        if "bark" in res:
            msg += f"\n{res['bark']}"
        if "death_msg" in res:
            msg += f"\n{res['death_msg']}"
        return msg

class CheckTool(BaseTool):
    name: str = "check"
    description: str = "Perform an ability check."
    args_schema: Type[BaseModel] = CheckInput

    def _run(self, character_name: str, stat: str, dc: int) -> str:
        mock_actor = {"name": character_name, "stats": {"strength": 16, "dexterity": 12, "wisdom": 14}, "hp": {"current": 20, "max": 20}}
        return engine.resolve_action(mock_actor, "check", params={"stat": stat, "dc": dc})

    async def execute_with_db(self, db: AsyncSession, campaign_id: str, character_name: str, stat: str, dc: int) -> str:
        """Asynchronously executes the check resolution using the active database session."""
        from app.services.state_service import StateService
        from app.services.game_service import GameService
        
        game_state = await StateService.get_game_state(campaign_id, db)
        if not game_state:
            return "No active game state found."
            
        actor_char = GameService._find_char_by_name(game_state, character_name)
        if not actor_char:
            return f"Character '{character_name}' not found."
            
        actor_data = actor_char.model_dump() if hasattr(actor_char, 'model_dump') else actor_char.dict()
        return engine.resolve_action(actor_data, "check", params={"stat": stat, "dc": dc})

class MoveTool(BaseTool):
    name: str = "move"
    description: str = "Move the party to a connected location."
    args_schema: Type[BaseModel] = MoveInput

    def _run(self, actor_name: str, direction: str) -> str:
        return "To move, the user should type @move <location>."

    async def execute_with_db(self, db: AsyncSession, campaign_id: str, actor_name: str, direction: str) -> str:
        """Asynchronously executes the move resolution using the active database session."""
        from app.services.game_service import GameService
        res = await GameService.resolution_move(
            campaign_id=campaign_id,
            actor_name=actor_name,
            direction=direction,
            db=db
        )
        return res.get("message", "Move failed.")

class EndTurnTool(BaseTool):
    name: str = "end_turn"
    description: str = "Ends the current player's turn to pass the initiative to the next character in combat. Use this when the player explicitly states they are done with their turn or declines further actions after being prompted."
    args_schema: Type[BaseModel] = EndTurnInput

    def _run(self, reason: str = "") -> str:
        return "[SYSTEM_COMMAND:END_TURN]"

    async def execute_with_db(self, db: AsyncSession, campaign_id: str, reason: str = "") -> str:
        """Asynchronously executes turn ending/advancement using the active database session."""
        from app.services.combat_service import CombatService
        active_id, gs = await CombatService.next_turn(campaign_id, db, commit=True)
        if active_id:
            from app.services.game_service import GameService
            active_entity = GameService._find_char_by_name(gs, active_id)
            entity_name = active_entity.name if active_entity else "Unknown"
            return f"[SYSTEM_COMMAND:END_TURN]\nTurn passed. It is now {entity_name}'s turn."
        return "[SYSTEM_COMMAND:END_TURN]\nTurn ended."

# List of tools to bind to the LLM
game_tools = [AttackTool(), CheckTool(), MoveTool(), EndTurnTool()]
