from typing import Optional, Any
from ..character_sheet import CharacterSheet

class ActionResolver:
    """Base interface for action resolvers in the game engine."""
    def resolve(self, actor: CharacterSheet, target: Optional[CharacterSheet], params: dict) -> Any:
        raise NotImplementedError("Subclasses must implement resolve()")
