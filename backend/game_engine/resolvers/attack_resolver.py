from typing import Optional, Any
from ..character_sheet import CharacterSheet
from ..dice import Dice
from .base import ActionResolver

class AttackResolver(ActionResolver):
    def resolve(self, actor: CharacterSheet, target: Optional[CharacterSheet], params: dict) -> dict:
        if not target:
            return {"success": False, "message": "No target specified."}

        # Determine weapon and stats
        weapon_name = params.get("weapon_name", "Unarmed Strike")
        damage_dice = params.get("weapon_damage_dice", "1d4")
        is_finesse = params.get("is_finesse", False)
        is_ranged = params.get("is_ranged", False)

        # If a weapon exists and we need further parsing (like properties)
        weapon = actor.get_weapon()
        if weapon and not params.get("weapon_name"):
            # Fallback if params weren't passed
            weapon_name = weapon.get("name", "Unknown Weapon")
            weapon_data = weapon.get("data") or {}
            damage_info = weapon_data.get("damage")
            if isinstance(damage_info, dict):
                damage_dice = damage_info.get("damage_dice", "1d4")
            elif isinstance(damage_info, str):
                damage_dice = damage_info.split()[0] if damage_info else "1d4"
            else:
                damage_dice = "1d4"

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

            # Off-hand attacks don't add positive ability modifiers to damage
            is_offhand = params.get("is_offhand", False)
            damage_mod = hit_mod
            if is_offhand and damage_mod > 0:
                damage_mod = 0

            damage = dmg_roll["total"] + damage_mod
            detail_str = dmg_roll["detail"]

            # Crit double dice
            if is_crit:
                crit_roll = Dice.roll(damage_dice)
                damage += crit_roll["total"]
                detail_str += f" + {crit_roll['detail']} [CRIT]"
                result_str += "CRITICAL HIT! "

            if damage_mod != 0:
                detail_str += f" + {damage_mod}"

            result_str += f"Hit! Damage: {damage} ({detail_str}). "

            # Apply damage (updates target object)
            damage_result_str = target.take_damage(damage)

            result_data["damage_total"] = damage
            result_data["damage_detail"] = detail_str
            result_data["target_hp_remaining"] = target.hp["current"]

            if target.hp["current"] <= 0:
                result_str += "\n[KILLING BLOW] "

            result_data["message"] = result_str + damage_result_str
            result_data["target_status"] = "Unconscious" if target.hp["current"] <= 0 else "Active"
        else:
            result_str += "Miss!"
            result_data["message"] = result_str
            result_data["target_status"] = "Active"

        return result_data
