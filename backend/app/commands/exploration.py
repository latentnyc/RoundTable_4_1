from typing import List
from .base import Command, CommandContext
from app.services.game_service import GameService
from app.services.loot_service import LootService
from app.services.chat_service import ChatService
from app.services.narrator_service import NarratorService
from app.services.turn_manager import TurnManager
from app.services.context_builder import build_narrative_context
from app.services.state_service import StateService
from app.services.lock_service import LockService

class MoveCommand(Command):
    name = "move"
    aliases = ["mv", "goto"]
    description = "Move the party to a new location."
    args_help = "<location_name>"

    async def execute(self, ctx: CommandContext, args: List[str]):
        if not args:
            await ctx.sio.emit('system_message', {'content': f"Usage: @{self.name} {self.args_help}"}, room=ctx.campaign_id)
            return

        target_name = " ".join(args)

        move_result = await GameService.resolution_move(ctx.campaign_id, ctx.sender_name, target_name, ctx.db)

        if move_result['success']:
            # 1. Emit System Message instantly for player feedback
            await ctx.sio.emit('system_message', {'content': move_result['message']}, room=ctx.campaign_id)

            # 2. Trigger DM Narration while the old image is still visible
            rich_context = await build_narrative_context(ctx.db, ctx.campaign_id, move_result['game_state'])
            await NarratorService.narrate(
                campaign_id=ctx.campaign_id,
                context=rich_context,
                sio=ctx.sio,
                db=ctx.db,
                mode="move_narration",
                sid=ctx.sid
            )

            # 3. Emit Game State Update to trigger the UI changes and Image Generation
            await StateService.emit_state_update(ctx.campaign_id, move_result['game_state'], ctx.sio)

            await ctx.db.commit()
        else:
            await ctx.sio.emit('system_message', {'content': move_result.get('message', "Move failed.")}, room=ctx.campaign_id)
            if "interrupts" in move_result.get('message', '').lower():
                await NarratorService.narrate(
                    campaign_id=ctx.campaign_id,
                    context=move_result['message'],
                    sio=ctx.sio,
                    db=ctx.db,
                    mode="combat_narration",
                    sid=ctx.sid
                )
                opp_state = move_result.get('game_state')
                if opp_state and opp_state.phase == 'combat':
                    await TurnManager.process_turn(ctx.campaign_id, opp_state.active_entity_id, opp_state, ctx.sio, db=ctx.db)
class IdentifyCommand(Command):
    name = "identify"
    aliases = ["id", "examine", "investigate", "inspect"]
    description = "Investigate an entity to learn its true nature."
    args_help = "<target_name>"

    async def execute(self, ctx: CommandContext, args: List[str]):
        if not args:
            await ctx.sio.emit('system_message', {'content': f"Usage: @{self.name} {self.args_help}"}, room=ctx.campaign_id)
            return

        target_name = " ".join(args)

        result = await GameService.resolution_identify(ctx.campaign_id, ctx.sender_name, target_name, ctx.db, target_id=ctx.target_id)

        # Persist system message (The Roll)
        roll_msg = f"🔍 **{result.get('actor_name', ctx.sender_name)}** investigates **{result.get('target_name', target_name)}**.\n"
        roll_msg += f"**Roll:** {result.get('roll_detail', '?')} = **{result.get('roll_total', '?')}**"
        if result.get('success'):
            roll_msg += " (SUCCESS)"
        else:
            roll_msg += " (FAILURE)"

        save_result = await ChatService.save_message(ctx.campaign_id, 'system', 'System', roll_msg, db=ctx.db)
        await ctx.sio.emit('chat_message', {
            'sender_id': 'system', 'sender_name': 'System', 'content': roll_msg, 'id': save_result['id'], 'timestamp': save_result['timestamp'], 'is_system': True
        }, room=ctx.campaign_id)

        # Trigger DM Narration
        outcome_context = roll_msg
        if result.get('success'):
            t_obj = result.get('target_object')
            if hasattr(t_obj, 'name'):
                outcome_context += f"\n[SYSTEM SECRET]: The target is truly {t_obj.name.upper()} ({getattr(t_obj, 'role', '')} {getattr(t_obj, 'race', '')})."

        await NarratorService.narrate(
            campaign_id=ctx.campaign_id,
            context=outcome_context,
            sio=ctx.sio,
            db=ctx.db,
            mode="identify_narration",
            sid=ctx.sid
        )
        await ctx.db.commit()

class EquipCommand(Command):
    name = "equip"
    aliases = ["eq", "wield", "wear"]
    description = "Equip an item from your backpack."
    args_help = "<item_name>"

    async def execute(self, ctx: CommandContext, args: List[str]):
        if not args:
            await ctx.sio.emit('system_message', {'content': f"Usage: @{self.name} {self.args_help}"}, room=ctx.campaign_id)
            return

        item_name = " ".join(args)

        # Basic ID lookup by replacing spaces with hyphens, real implementation might do fuzzy matching
        item_id = item_name.lower().replace(' ', '-')
        if not (item_id.startswith('wpn-') or item_id.startswith('arm-') or item_id.startswith('itm-')):
             # Naive fallback: try wpn- first
             item_id = f"wpn-{item_id}"

        result = await LootService.equip_item(ctx.campaign_id, ctx.sender_id, item_id, True, ctx.db)

        if result['success']:
            await ctx.sio.emit('system_message', {'content': f"**{ctx.sender_name}** equipped **{item_name.title()}**."}, room=ctx.campaign_id)
            game_state = await GameService.get_game_state(ctx.campaign_id, ctx.db)
            if game_state:
                 await StateService.emit_state_update(ctx.campaign_id, game_state, ctx.sio)
        else:
            await ctx.sio.emit('system_message', {'content': result.get('message', "Failed to equip item.")}, room=ctx.campaign_id)

class UnequipCommand(Command):
    name = "unequip"
    aliases = ["uneq", "remove", "doff"]
    description = "Remove an equipped item."
    args_help = "<item_name>"

    async def execute(self, ctx: CommandContext, args: List[str]):
        if not args:
            await ctx.sio.emit('system_message', {'content': f"Usage: @{self.name} {self.args_help}"}, room=ctx.campaign_id)
            return

        item_name = " ".join(args)

        # Basic ID lookup
        item_id = item_name.lower().replace(' ', '-')
        if not (item_id.startswith('wpn-') or item_id.startswith('arm-') or item_id.startswith('itm-')):
             item_id = f"wpn-{item_id}"

        result = await LootService.equip_item(ctx.campaign_id, ctx.sender_id, item_id, False, ctx.db)

        if result['success']:
            await ctx.sio.emit('system_message', {'content': f"**{ctx.sender_name}** unequipped **{item_name.title()}**."}, room=ctx.campaign_id)
            game_state = await GameService.get_game_state(ctx.campaign_id, ctx.db)
            if game_state:
                 await StateService.emit_state_update(ctx.campaign_id, game_state, ctx.sio)
        else:
            await ctx.sio.emit('system_message', {'content': result.get('message', "Failed to unequip item.")}, room=ctx.campaign_id)


class RestCommand(Command):
    name = "rest"
    aliases = ["longrest", "shortrest", "camp"]
    description = "Rest to recover HP and spell slots."
    args_help = "[short|long]"

    async def execute(self, ctx: CommandContext, args: List[str]):
        try:
            async with LockService.acquire(ctx.campaign_id):
                await self._execute_locked(ctx, args)
        except TimeoutError:
            await ctx.sio.emit('system_message', {'content': "🚫 Action blocked: Server is busy."}, room=ctx.sid)

    async def _execute_locked(self, ctx: CommandContext, args: List[str]):
        game_state = await GameService.get_game_state(ctx.campaign_id, ctx.db)
        if not game_state:
            return

        if game_state.phase == 'combat':
            await ctx.sio.emit('system_message', {'content': "🚫 You cannot rest during combat!"}, room=ctx.campaign_id)
            return

        rest_type = "long"
        if args and args[0].lower() in ("short", "s"):
            rest_type = "short"

        from app.services.spell_service import restore_spell_slots, init_spell_slots

        healed = []
        slots_restored = []

        for p in game_state.party:
            role = getattr(p, 'role', 'Fighter')
            level = getattr(p, 'level', 1)

            # HP recovery
            if rest_type == "long":
                old_hp = p.hp_current
                p.hp_current = p.hp_max
                if p.hp_current > old_hp:
                    healed.append(f"{p.name} ({old_hp} -> {p.hp_max} HP)")
            else:
                # Short rest: recover with hit dice (simplified: heal 25% of max)
                old_hp = p.hp_current
                heal_amt = max(1, p.hp_max // 4)
                p.hp_current = min(p.hp_max, p.hp_current + heal_amt)
                if p.hp_current > old_hp:
                    healed.append(f"{p.name} (+{p.hp_current - old_hp} HP)")

            # Spell slot recovery
            if hasattr(p, 'sheet_data') and p.sheet_data.get('spells'):
                init_spell_slots(p.sheet_data, role, level)
                old_slots = dict(p.sheet_data.get('spell_slots_current', {}))
                restore_spell_slots(p.sheet_data, role, level, rest_type)
                new_slots = p.sheet_data.get('spell_slots_current', {})

                restored_any = any(new_slots.get(k, 0) > old_slots.get(k, 0) for k in new_slots)
                if restored_any:
                    slots_restored.append(p.name)

        await StateService.save_game_state(ctx.campaign_id, game_state, ctx.db)
        await ctx.db.commit()
        await StateService.emit_state_update(ctx.campaign_id, game_state, ctx.sio)

        # Build result message
        rest_label = "Long Rest" if rest_type == "long" else "Short Rest"
        msg = f"🏕️ **{rest_label} Complete!**\n"
        if healed:
            msg += "\n".join(f"  💚 {h}" for h in healed)
        else:
            msg += "  Everyone was already at full health."
        if slots_restored:
            msg += f"\n  ✨ Spell slots restored for: {', '.join(slots_restored)}"

        await ctx.sio.emit('system_message', {'content': msg}, room=ctx.campaign_id)

        await NarratorService.narrate(
            campaign_id=ctx.campaign_id,
            context=msg,
            sio=ctx.sio,
            db=ctx.db,
            mode="move_narration",
            sid=ctx.sid,
        )
        await ctx.db.commit()


class CheckCommand(Command):
    name = "check"
    aliases = ["roll", "skill"]
    description = "Make an ability or skill check."
    args_help = "<skill_or_ability> [dc]"

    SKILL_TO_ABILITY = {
        "acrobatics": "dexterity", "animal handling": "wisdom", "arcana": "intelligence",
        "athletics": "strength", "deception": "charisma", "history": "intelligence",
        "insight": "wisdom", "intimidation": "charisma", "investigation": "intelligence",
        "medicine": "wisdom", "nature": "intelligence", "perception": "wisdom",
        "performance": "charisma", "persuasion": "charisma", "religion": "intelligence",
        "sleight of hand": "dexterity", "stealth": "dexterity", "survival": "wisdom",
        # Also allow raw ability checks
        "strength": "strength", "dexterity": "dexterity", "constitution": "constitution",
        "intelligence": "intelligence", "wisdom": "wisdom", "charisma": "charisma",
        "str": "strength", "dex": "dexterity", "con": "constitution",
        "int": "intelligence", "wis": "wisdom", "cha": "charisma",
    }

    async def execute(self, ctx: CommandContext, args: List[str]):
        if not args:
            skills_list = ", ".join(sorted(set(k for k in self.SKILL_TO_ABILITY.keys() if len(k) > 3)))
            await ctx.sio.emit('system_message', {
                'content': f"Usage: @check <skill> [dc]\nAvailable: {skills_list}"
            }, room=ctx.campaign_id)
            return

        # Parse skill name and optional DC
        dc = None
        skill_parts = []
        for a in args:
            if a.isdigit():
                dc = int(a)
            else:
                skill_parts.append(a.lower())

        skill_name = " ".join(skill_parts)
        ability = self.SKILL_TO_ABILITY.get(skill_name)
        if not ability:
            await ctx.sio.emit('system_message', {
                'content': f"Unknown skill or ability: '{skill_name}'. Type @check for a list."
            }, room=ctx.campaign_id)
            return

        game_state = await GameService.get_game_state(ctx.campaign_id, ctx.db)
        if not game_state:
            return

        # Find the player's character
        actor = None
        for p in game_state.party:
            if p.id == ctx.sender_id:
                actor = p
                break
        if not actor:
            await ctx.sio.emit('system_message', {'content': "Could not find your character."}, room=ctx.campaign_id)
            return

        # Roll the check
        from game_engine.dice import Dice
        from game_engine.character_sheet import CharacterSheet

        sheet = CharacterSheet(actor.model_dump())
        ability_mod = sheet.get_mod(ability)

        # Proficiency: check if character has this skill in their proficiencies
        prof_bonus = 0
        proficient_skills = []
        if hasattr(actor, 'sheet_data') and isinstance(actor.sheet_data, dict):
            proficient_skills = actor.sheet_data.get('skills', [])
        if skill_name in proficient_skills or skill_name.replace(" ", "_") in proficient_skills:
            prof_bonus = sheet.get_proficiency_bonus()

        roll = Dice.roll("1d20")
        total = roll["total"] + ability_mod + prof_bonus

        # Build message
        is_skill = skill_name in self.SKILL_TO_ABILITY and skill_name not in ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma", "str", "dex", "con", "int", "wis", "cha")
        check_label = f"{skill_name.title()} ({ability[:3].upper()})" if is_skill else ability.title()
        prof_str = " + Prof" if prof_bonus > 0 else ""

        msg = f"🎲 **{actor.name}** — {check_label} Check\n"
        msg += f"Roll: {roll['total']} + {ability_mod}{prof_str} = **{total}**"

        if dc is not None:
            success = total >= dc
            msg += f" vs DC {dc}: {'**Success!**' if success else '**Failure.**'}"

        save_result = await ChatService.save_message(ctx.campaign_id, 'system', 'System', msg, db=ctx.db)
        await ctx.sio.emit('chat_message', {
            'sender_id': 'system', 'sender_name': 'System', 'content': msg,
            'id': save_result['id'], 'timestamp': save_result['timestamp'],
            'is_system': True, 'message_type': 'system'
        }, room=ctx.campaign_id)
        await ctx.db.commit()
