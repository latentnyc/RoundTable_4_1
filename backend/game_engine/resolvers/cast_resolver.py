from typing import Optional, Any
from ..character_sheet import CharacterSheet
from ..dice import Dice
from .base import ActionResolver

class CastResolver(ActionResolver):
    def resolve(self, actor: CharacterSheet, target: Optional[CharacterSheet], params: dict) -> dict:
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
            result_data["message"] += "\n*Spell Attack Roll:* "
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
                 result_data["message"] += " **Miss.**"
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
             result_data["message"] += "\n*Healing Burst:* "
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
