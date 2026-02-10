from typing import List, Dict, Optional
from .dice import Dice
from .character_sheet import CharacterSheet

class GameEngine:
    def __init__(self):
        pass

    def resolve_action(self, actor_data: dict, action_type: str, target_data: Optional[dict] = None, params: dict = {}) -> str:
        """
        Central resolution method for tool calls.
        """
        actor = CharacterSheet(actor_data)
        target = CharacterSheet(target_data) if target_data else None
        
        if action_type == "attack":
            return self._resolve_attack(actor, target, params)
        elif action_type == "check":
            return self._resolve_check(actor, params)
        elif action_type == "save":
            return self._resolve_save(actor, params)
        
        return "Unknown action type."

    def _resolve_attack(self, actor: CharacterSheet, target: CharacterSheet, params: dict) -> str:
        if not target:
            return "No target specified."
            
        # 1. Roll to Hit
        # Simplified: Assume using Strength for now
        hit_mod = actor.get_mod("strength") 
        # TODO: Proficiency bonus
        
        roll = Dice.roll("1d20")
        to_hit = roll["total"] + hit_mod
        
        ac = 10 + target.get_mod("dexterity") # Simplified AC
        
        result = f"{actor.name} attacks {target.name}. Roll: {roll['total']} + {hit_mod} = {to_hit} vs AC {ac}. "
        
        if to_hit >= ac:
            # 2. Roll Damage
            # Simplified: 1d8 + Str
            dmg_roll = Dice.roll("1d8")
            damage = dmg_roll["total"] + actor.get_mod("strength")
            result += f"Hit! Damage: {damage} ({dmg_roll['detail']} + {actor.get_mod('strength')}). "
            result += target.take_damage(damage)
        else:
            result += "Miss!"
            
        return result

    def _resolve_check(self, actor: CharacterSheet, params: dict) -> str:
        stat = params.get("stat", "strength")
        dc = params.get("dc", 10)
        
        mod = actor.get_mod(stat)
        roll = Dice.roll("1d20")
        total = roll["total"] + mod
        
        success = total >= dc
        return f"{actor.name} {stat} check: {total} ({roll['total']} + {mod}) vs DC {dc}. {'Success!' if success else 'Failure.'}"

    def _resolve_save(self, actor: CharacterSheet, params: dict) -> str:
        stat = params.get("stat", "dexterity")
        dc = params.get("dc", 10)
        
        mod = actor.get_save(stat)
        roll = Dice.roll("1d20")
        total = roll["total"] + mod
        
        success = total >= dc
        return f"{actor.name} {stat} save: {total} ({roll['total']} + {mod}) vs DC {dc}. {'Success!' if success else 'Failure.'}"
