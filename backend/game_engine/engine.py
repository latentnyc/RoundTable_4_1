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

        # Determine weapon and stats
        weapon = actor.get_weapon()
        weapon_name = "Unarmed Strike"
        damage_dice = "1d4"
        is_finesse = False
        is_ranged = False

        if weapon:
            weapon_name = weapon.get("name", "Unknown Weapon")
            weapon_data = weapon.get("data") or {}
            damage_info = weapon_data.get("damage") or {}
            damage_dice = damage_info.get("damage_dice", "1d4")

            properties = weapon_data.get("properties", [])
            for prop in properties:
                if isinstance(prop, dict):
                    prop_name = (prop.get("name") or "").lower()
                    if "finesse" in prop_name:
                        is_finesse = True

            w_type = (weapon_data.get("type") or "").lower()
            if "ranged" in w_type:
                is_ranged = True

        str_mod = actor.get_mod("strength")
        dex_mod = actor.get_mod("dexterity")

        # Determine attack modifier
        if is_ranged:
            hit_mod = dex_mod
        elif is_finesse:
            hit_mod = max(str_mod, dex_mod)
        else:
            hit_mod = str_mod

        # 1. Roll to Hit
        roll = Dice.roll("1d20")
        to_hit = roll["total"] + hit_mod

        ac = target.get_ac()

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
        # Determine attack tags for the AI Narrator
        attack_tags = []
        if weapon_name == "Unarmed Strike":
            attack_tags.append("[UNARMED STRIKE]")
        elif is_ranged:
            attack_tags.append("[RANGED WEAPON ATTACK]")
        elif is_finesse:
            attack_tags.append("[FINESSE MELEE WEAPON ATTACK]")
        else:
            attack_tags.append("[HEAVY/STANDARD MELEE WEAPON ATTACK]")

        tags_str = " ".join(attack_tags)

        result_str = f"{tags_str}\n{actor.name} attacks {target.name} with {weapon_name}. Roll: {roll['total']} + {hit_mod} = {to_hit} vs AC {ac}. "

        if is_hit:
            # 2. Roll Damage
            dmg_roll = Dice.roll(damage_dice)
            damage = dmg_roll["total"] + hit_mod
            detail_str = dmg_roll["detail"]

            # Crit double dice
            if is_crit:
                crit_roll = Dice.roll(damage_dice)
                damage += crit_roll["total"]
                detail_str += f" + {crit_roll['detail']} [CRIT]"
                result_str += f"CRITICAL HIT! "

            detail_str += f" + {hit_mod}"
            result_str += f"Hit! Damage: {damage} ({detail_str}). "

            # Apply damage (updates target object)
            damage_result_str = target.take_damage(damage)

            result_data["damage_total"] = damage
            result_data["damage_detail"] = detail_str
            result_data["target_hp_remaining"] = target.hp["current"]

            if target.hp["current"] <= 0:
                result_str += f"\n[KILLING BLOW] "

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
