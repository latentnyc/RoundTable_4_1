from typing import Optional, Type, List
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from .engine import GameEngine

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

class EndTurnInput(BaseModel):
    reason: Optional[str] = Field(default="", description="Reason for ending turn")

# --- TOOLS ---

class AttackTool(BaseTool):
    name: str = "attack"
    description: str = "Perform an attack against a target. Uses Strength by default."
    args_schema: Type[BaseModel] = AttackInput

    def _run(self, attacker_name: str, target_name: str, weapon: str = "sword") -> str:
        # In a real app, we'd look up the full character data from DB using the name
        # For now, we mock the data lookup or pass it in context

        # MOCK DATA LOOKUP
        # This is where we'd fetch from the DB
        # For prototype, we'll just invent stats if they don't exist
        mock_actor = {"name": attacker_name, "stats": {"strength": 16, "dexterity": 12}, "hp": {"current": 20, "max": 20}}
        mock_target = {"name": target_name, "stats": {"dexterity": 10}, "hp": {"current": 10, "max": 10}}

        return engine.resolve_action(mock_actor, "attack", mock_target)

class CheckTool(BaseTool):
    name: str = "check"
    description: str = "Perform an ability check."
    args_schema: Type[BaseModel] = CheckInput

    def _run(self, character_name: str, stat: str, dc: int) -> str:
        mock_actor = {"name": character_name, "stats": {"strength": 16, "dexterity": 12, "wisdom": 14}, "hp": {"current": 20, "max": 20}}
        return engine.resolve_action(mock_actor, "check", params={"stat": stat, "dc": dc})

class MoveInput(BaseModel):
    target_name: str = Field(description="Name of the location to move to")

class MoveTool(BaseTool):
    name: str = "move"
    description: str = "Move the party to a connected location."
    args_schema: Type[BaseModel] = MoveInput

    def _run(self, target_name: str) -> str:
        # NOTE: This tool is context-dependent and usually run by the System directly properly
        # If the LLM uses it, we might not have the 'allowed_moves' context here easily
        # unless we inject it into the tool instance or use a global.
        # For now, this is a placeholder to let the LLM know it CAN move.
        # The actual resolution happens in chat.py handling @move.
        # If the LLM *calls* this, we should probably output a special string that chat.py intercepts,
        # OR we just say "Please use the @move command".
        return "To move, the user should type @move <location>."

class EndTurnTool(BaseTool):
    name: str = "end_turn"
    description: str = "Ends the current player's turn to pass the initiative to the next character in combat. Use this when the player explicitly states they are done with their turn or declines further actions after being prompted."
    args_schema: Type[BaseModel] = EndTurnInput

    def _run(self, reason: str = "") -> str:
        return "[SYSTEM_COMMAND:END_TURN]"

# List of tools to bind to the LLM
game_tools = [AttackTool(), CheckTool(), MoveTool(), EndTurnTool()]
