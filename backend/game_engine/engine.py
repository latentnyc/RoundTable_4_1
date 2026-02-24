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
        elif action_type == "cast":
            return self._resolve_cast(actor, target, params)
        elif action_type == "check":
            return self._resolve_check(actor, params)
        elif action_type == "save":
            return self._resolve_save(actor, params)

        return "Unknown action type."

    def _resolve_attack(self, actor: CharacterSheet, target: CharacterSheet, params: dict) -> dict:
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
                result_str += f"CRITICAL HIT! "

            if damage_mod != 0:
                detail_str += f" + {damage_mod}"

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

    def _resolve_cast(self, actor: CharacterSheet, target: Optional[CharacterSheet], params: dict) -> dict:
        spell_data = params.get("spell_data")
        if not spell_data:
            return {"success": False, "message": "No spell data provided to engine."}

        # Handle simple string vs rich dict spell structure
        if isinstance(spell_data, str):
            spell_name = spell_data
            s_data = {}
        else:
            spell_name = spell_data.get("name", "Unknown Spell")
            s_data = spell_data.get("data", {})

        # Default results structure
        result_data = {
            "success": True,
            "attacker_name": actor.name,
            "target_name": target.name if target else "None",
            "spell_name": spell_name,
            "damage_total": 0,
            "damage_detail": "",
            "message": f"✨ **{actor.name}** casts **{spell_name}**" + (f" at **{target.name}**!" if target else "!")
        }

        # If we just have a string with no data, we do narrative casting only
        if not s_data:
            return result_data

        # Determine Spell Properties
        requires_attack_roll = s_data.get("attack_type") is not None
        requires_saving_throw = s_data.get("save") is not None
        dc_stat = s_data.get("save", {}).get("dc_type", {}).get("index", "dexterity") if requires_saving_throw else None

        # Determine Damage/Healing
        damage_info = s_data.get("damage")
        heal_info = s_data.get("heal_at_slot_level")

        damage_dice = None
        damage_type_name = ""
        if damage_info:
            damage_type_name = damage_info.get("damage_type", {}).get("name", "")
            # Assume casting at base level for now
            level = s_data.get("level", 1)
            dmg_at_slot = damage_info.get("damage_at_slot_level")
            dmg_at_char_level = damage_info.get("damage_at_character_level")

            if dmg_at_slot and str(level) in dmg_at_slot:
                damage_dice = dmg_at_slot[str(level)]
            elif dmg_at_char_level and "1" in dmg_at_char_level: # default parsing level 1
                damage_dice = dmg_at_char_level["1"]
            elif "damage_dice" in damage_info:
                 damage_dice = damage_info["damage_dice"]

        heal_dice = heal_info.get("1") if heal_info else None # crude grab of base level healing

        # Modifiers
        spell_atk_mod = actor.get_spell_attack_mod()
        spell_save_dc = actor.get_spell_save_dc()

        # ----------------
        # 1. Spell Attacks
        # ----------------
        if requires_attack_roll and target:
            result_data["message"] += f"\n*Spell Attack Roll:* "
            roll = Dice.roll("1d20")
            to_hit = roll["total"] + spell_atk_mod
            ac = target.get_ac()

            is_hit = to_hit >= ac
            is_crit = roll["total"] == 20

            result_data["message"] += f"{roll['total']} + {spell_atk_mod} = **{to_hit}** vs AC {ac}."

            if is_hit:
                if damage_dice:
                    dmg_roll = Dice.roll(damage_dice)
                    dmg = dmg_roll["total"]
                    detail = dmg_roll["detail"]
                    if is_crit:
                        crit_roll = Dice.roll(damage_dice)
                        dmg += crit_roll["total"]
                        detail += f" + {crit_roll['detail']} [CRIT]"
                        result_data["message"] += " **CRITICAL HIT!**"

                    result_data["damage_total"] = dmg
                    result_data["damage_detail"] = detail

                    target.take_damage(dmg)
                    result_data["target_hp_remaining"] = target.hp["current"]

                    result_data["message"] += f"\n🩸 **Hit!** Damage: **{dmg}** {damage_type_name} ({detail}). Target HP: {target.hp['current']}"
                    if target.hp["current"] <= 0:
                         result_data["message"] += " [LETHAL]"
            else:
                 result_data["message"] += f" **Miss.**"
                 result_data["target_hp_remaining"] = target.hp["current"]

        # ----------------
        # 2. Saving Throws
        # ----------------
        elif requires_saving_throw and target:
            result_data["message"] += f"\n*Saving Throw (DC {spell_save_dc} {dc_stat.upper()}):* "
            target_save_mod = target.get_save(dc_stat)
            roll = Dice.roll("1d20")
            save_total = roll["total"] + target_save_mod

            is_saved = save_total >= spell_save_dc
            result_data["message"] += f"{target.name} rolls **{save_total}** ({roll['total']} + {target_save_mod}). "

            if damage_dice:
                dmg_roll = Dice.roll(damage_dice)
                dmg = dmg_roll["total"]
                detail = dmg_roll["detail"]

                # Check half damage on save
                # SRD spells usually have 'save_success: half' or 'none' but it's nested or missing in our simpler parse
                # Most damage spells save for half, let's default to half if saving throw is used for damage
                if is_saved:
                    dmg = dmg // 2
                    result_data["message"] += "**Saved!** (Half damage)."
                else:
                    result_data["message"] += "**Failed!**"

                result_data["damage_total"] = dmg
                result_data["damage_detail"] = detail

                target.take_damage(dmg)
                result_data["target_hp_remaining"] = target.hp["current"]
                result_data["message"] += f"\n🩸 Damage: **{dmg}** {damage_type_name} ({detail}). Target HP: {target.hp['current']}"
                if target.hp["current"] <= 0:
                     result_data["message"] += " [LETHAL]"

        # ----------------
        # 3. Healing & Buffs
        # ----------------
        elif heal_dice and target:
             result_data["message"] += f"\n*Healing Burst:* "
             heal_roll = Dice.roll(heal_dice)
             # Add spellcasting modifier to healing (common for Cure Wounds etc)
             # Usually it's Dice + Mod
             heal_amt = heal_roll["total"] + actor.get_mod(actor.get_spellcasting_ability())

             # Actually heal target!
             target.hp["current"] = min(target.hp["current"] + heal_amt, target.hp["max"])
             result_data["target_hp_remaining"] = target.hp["current"]

             result_data["message"] += f"Restored **{heal_amt}** HP ({heal_roll['detail']} + Mod). Target HP: {target.hp['current']}"

        # 4. Other logic: Magic Missile, buffs, etc...
        elif damage_dice and target:
             # Auto hit damage like Magic Missile (which doesn't have an attack roll or save in basic parse)
             dmg_roll = Dice.roll(damage_dice)
             dmg = dmg_roll["total"]
             target.take_damage(dmg)
             result_data["target_hp_remaining"] = target.hp["current"]
             result_data["message"] += f"\n🎯 **Auto-Hit!** Damage: **{dmg}** {damage_type_name} ({dmg_roll['detail']}). Target HP: {target.hp['current']}"

        # If no target provided but needed
        if not target and (requires_attack_roll or requires_saving_throw or damage_dice or heal_dice):
             result_data["message"] += "\n*(Failed to resolve target mechanics)*"

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
