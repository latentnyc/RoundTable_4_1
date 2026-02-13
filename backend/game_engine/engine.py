from typing import List, Dict, Optional, Any
from .dice import Dice
from .character_sheet import CharacterSheet

class GameEngine:
    def __init__(self):
        pass

    def resolve_action(self, actor_data: dict, action_type: str, target_data: Optional[dict] = None, params: dict = {}) -> Any:
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

    def _resolve_attack(self, actor: CharacterSheet, target: CharacterSheet, params: dict) -> dict:
        if not target:
            return {"success": False, "message": "No target specified."}

        # 1. Roll to Hit
        # Simplified: Assume using Strength for now
        hit_mod = actor.get_mod("strength")

        roll = Dice.roll("1d20")
        to_hit = roll["total"] + hit_mod

        ac = 10 + target.get_mod("dexterity") # Simplified AC

        is_hit = to_hit >= ac
        is_crit = roll["total"] == 20
        is_fumble = roll["total"] == 1

        result_data = {
            "success": True,
            "attacker_name": actor.name,
            "target_name": target.name,
            "attack_roll": roll["total"],
            "attack_mod": hit_mod,
            "attack_total": to_hit,
            "target_ac": ac,
            "is_hit": is_hit,
            "is_crit": is_crit,
            "is_fumble": is_fumble,
            "damage_total": 0,
            "damage_detail": "",
            "target_hp_remaining": target.hp["current"], # Will update below
            "message": "" # Will construct string summary for logs
        }

        # Construct summary string
        result_str = f"{actor.name} attacks {target.name}. Roll: {roll['total']} + {hit_mod} = {to_hit} vs AC {ac}. "

        if is_hit:
            # 2. Roll Damage
            # Simplified: 1d8 + Str
            dmg_roll = Dice.roll("1d8")
            damage = dmg_roll["total"] + actor.get_mod("strength")

            # Crit double dice
            if is_crit:
                crit_roll = Dice.roll("1d8")
                damage += crit_roll["total"]
                result_str += f"CRITICAL HIT! "

            result_str += f"Hit! Damage: {damage} ({dmg_roll['detail']}"
            if is_crit:
                result_str += f" + {crit_roll['detail']} CRIT"
            result_str += f" + {actor.get_mod('strength')}). "

            # Apply damage (updates target object)
            damage_result_str = target.take_damage(damage)

            result_data["damage_total"] = damage
            result_data["damage_detail"] = f"{dmg_roll['detail']} + {actor.get_mod('strength')}"
            result_data["target_hp_remaining"] = target.hp["current"]
            result_data["message"] = result_str + damage_result_str
            result_data["target_status"] = "Unconscious" if target.hp["current"] <= 0 else "Active"
        else:
            result_str += "Miss!"
            result_data["message"] = result_str
            result_data["target_status"] = "Active"

        return result_data

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

    def resolve_move(self, allowed_moves: List[Dict[str, str]], target_name: str) -> Dict[str, Any]:
        """
        Resolves a move attempt.
        allowed_moves: list of dicts with 'id' and 'name'
        target_name: user input
        """
        # 1. Normalize target
        target_norm = target_name.strip().lower()

        # 2. Search
        # Exact match first
        for move in allowed_moves:
            if move['name'].lower() == target_norm:
                return {"success": True, "target_id": move['id'], "target_name": move['name'], "message": f"Moved to {move['name']}."}

        # Fuzzy / Partial match
        # e.g. "Town" matches "Barleyrest Town Square"
        matches = []
        for move in allowed_moves:
            if target_norm in move['name'].lower():
                matches.append(move)

        if len(matches) == 1:
            move = matches[0]
            return {"success": True, "target_id": move['id'], "target_name": move['name'], "message": f"Moved to {move['name']}."}
        elif len(matches) > 1:
            names = ", ".join([m['name'] for m in matches])
            return {"success": False, "message": f"Ambiguous destination. Did you mean: {names}?"}

        return {"success": False, "message": "You cannot go there from here."}
