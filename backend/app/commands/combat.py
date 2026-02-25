from typing import List
from .base import Command, CommandContext
from app.services.game_service import GameService
from app.services.combat_service import CombatService
from app.services.turn_manager import TurnManager
from app.services.chat_service import ChatService
from app.services.narrator_service import NarratorService
from app.services.lock_service import LockService
from app.services.state_service import StateService
import logging

logger = logging.getLogger(__name__)

class AttackCommand(Command):
    name = "attack"
    aliases = ["atk", "a"]
    description = "Attack a target."
    args_help = "<target_name>"

    async def execute(self, ctx: CommandContext, args: List[str]):
        try:
            async with LockService.acquire(ctx.campaign_id):
                await self._execute_locked(ctx, args)
        except TimeoutError:
            await ctx.sio.emit('system_message', {'content': "🚫 Action blocked: Server is processing another request. Please try again."}, room=ctx.sid)

    async def _execute_locked(self, ctx: CommandContext, args: List[str]):
        if not args:
            await ctx.sio.emit('system_message', {'content': f"Usage: @{self.name} {self.args_help}"}, room=ctx.campaign_id)
            return

        target_name = " ".join(args)
        campaign_id = ctx.campaign_id
        sender_id = ctx.sender_id
        sender_name = ctx.sender_name
        sio = ctx.sio
        db = ctx.db
        sid = ctx.sid

        # Check Phase / Start Combat
        game_state = await GameService.get_game_state(campaign_id, db)
        if not game_state: return

        was_out_of_combat = (game_state.phase != 'combat')
        is_ranged = False

        if was_out_of_combat:
            actor_char = GameService._find_char_by_name(game_state, sender_name)
            if not actor_char:
                for p in game_state.party:
                    if p.id == sender_id:
                        actor_char = p
                        break
            if actor_char:
                weapon = None
                if hasattr(actor_char, 'inventory'):
                    for item in actor_char.inventory:
                        if getattr(item, 'equipped', False) and getattr(item, 'type', '') == 'weapon':
                            weapon = item
                            break
                            
                if weapon:
                    props = weapon.get('properties', []) if isinstance(weapon, dict) else getattr(weapon, 'data', {}).get('properties', [])
                    if isinstance(props, str): props = [props]
                    is_ranged = 'RANGE' in [p.upper() for p in (props or [])] or 'THROWN' in [p.upper() for p in (props or [])]

            if not is_ranged:
                # Start Combat Trigger for Melee
                start_res = await CombatService.start_combat(campaign_id, db)
                if start_res['success']:
                    await sio.emit('system_message', {'content': "⚔️ **COMBAT STARTED!** Rolling Initiative..."}, room=campaign_id)
                    await StateService.emit_state_update(campaign_id, start_res['game_state'], sio)

                    # Check if it is THIS user's turn
                    if start_res['active_entity_id'] != sender_id:
                        active_name = "Unknown"
                        for c in (start_res['game_state'].party + start_res['game_state'].enemies + start_res['game_state'].npcs):
                            if c.id == start_res['active_entity_id']:
                                active_name = c.name
                                break
                        # await sio.emit('system_message', {'content': f"Initiative Rolled! It is **{active_name}**'s turn first."}, room=campaign_id)

                        # Trigger AI Turn if it's not the player
                        from app.services.turn_manager import TurnManager
                        await TurnManager.process_turn(campaign_id, start_res['active_entity_id'], start_res['game_state'], sio, db=db)
                        await db.commit()
                        return
                game_state = start_res.get('game_state', game_state)

        # Check Logic: Is it my turn?
        if game_state.phase == 'combat':
            if game_state.active_entity_id != sender_id:
                active_name = "Unknown"
                for c in (game_state.party + game_state.enemies + game_state.npcs):
                    if c.id == game_state.active_entity_id:
                        active_name = c.name
                        break
                await sio.emit('system_message', {'content': f"🚫 It is not your turn! It is **{active_name}**'s turn."}, room=campaign_id)
                return

        # Resolve Attack
        result = await CombatService.resolution_attack(campaign_id, sender_id, sender_name, target_name, db, target_id=ctx.target_id)

        if not result['success']:
            await sio.emit('system_message', {'content': result['message']}, room=campaign_id)
            if "too far away" in result.get('message', '').lower():
                await NarratorService.narrate(
                    campaign_id=campaign_id,
                    context=result['message'] + f"\n[CRITICAL SYSTEM NOTE TO DM: The player {sender_name} attempted to melee attack {target_name}, but they are too far away on the hexagonal map. The physics engine REJECTED this attack. DO NOT narrate a missed swing or a counterattack. DO NOT advance the plot. Explain that they are out of range and must move closer first.]",
                    sio=sio,
                    db=db,
                    mode="combat_narration",
                    sid=sid
                )
            return

        # Emit Mechanics
        target_char = result.get('target_object')
        target_type = getattr(target_char, 'type', getattr(target_char, 'race', '')) if target_char else ''
        if not target_type and target_char and hasattr(target_char, 'data') and isinstance(target_char.data, dict):
            target_type = target_char.data.get('race', '')
            
        type_str = f" [{target_type.upper()}]" if target_type else ""
        mech_msg = f"⚔️ **{result['attacker_name']}** attacks **{result['target_name']}**{type_str}!\n"
        mech_msg += f"**Roll:** {result['attack_roll']} + {result['attack_mod']} = **{result['attack_total']}** vs AC {result['target_ac']}\n"
        if result['is_hit']:
            mech_msg += f"**HIT!** 🩸 Damage: **{result['damage_total']}** ({result['damage_detail']})\n"
            mech_msg += f"Target HP: {result['target_hp_remaining']}"
        else:
            mech_msg += "**MISS!** 🛡️"

        if result.get('death_msg'):
            mech_msg += f"\n\n{result['death_msg']}"

        save_result = await ChatService.save_message(campaign_id, 'system', 'System', mech_msg, db=db)
        await sio.emit('chat_message', {
            'sender_id': 'system', 'sender_name': 'System', 'content': mech_msg, 'id': save_result['id'], 'timestamp': save_result['timestamp'], 'is_system': True
        }, room=campaign_id)

        await StateService.emit_state_update(campaign_id, result['game_state'], sio)
        # Commit handled by caller or we should do it?
        # CommandContext db is passed from caller.
        # But wait, original code committed here.
        await db.commit()

        # Narration
        # Narrator service handles typing indicator internally
        narration_context = mech_msg
        if result.get('game_state') and getattr(result['game_state'], 'phase', '') != 'combat':
             narration_context += "\n[SYSTEM NOTE TO DM: Combat has just concluded! Provide a brief, atmospheric summary of the battle's aftermath. Describe the silence returning to the room, the state of the party, and explicitly ask the players what they intend to do next now that the threat has passed.]"

        await NarratorService.narrate(
            campaign_id=campaign_id,
            context=narration_context,
            sio=sio,
            db=db,
            mode="combat_narration",
            sid=sid
        )
        await db.commit()

        await db.commit()

        if was_out_of_combat and is_ranged:
            # We must now start combat
            start_res = await CombatService.start_combat(campaign_id, db)
            if start_res['success']:
                await sio.emit('system_message', {'content': "⚔️ **COMBAT STARTED!** Rolling Initiative..."}, room=campaign_id)
                await StateService.emit_state_update(campaign_id, start_res['game_state'], sio)

                active_name = "Unknown"
                for c in (start_res['game_state'].party + start_res['game_state'].enemies + start_res['game_state'].npcs):
                    if c.id == start_res['active_entity_id']:
                        active_name = c.name
                        break
                # await sio.emit('system_message', {'content': f"Initiative Rolled! It is **{active_name}**'s turn first."}, room=campaign_id)

                from app.services.turn_manager import TurnManager
                await TurnManager.process_turn(campaign_id, start_res['active_entity_id'], start_res['game_state'], sio, db=db)
                await db.commit()
            return

        # Advance Turn
        try:
            from app.services.turn_manager import TurnManager
            await TurnManager.advance_turn(campaign_id, sio, db, current_game_state=result.get('game_state'))
            await db.commit()
        except Exception as e:
            import traceback
            logger.error(f"CRITICAL ERROR in advance_turn: {e}\n{traceback.format_exc()}")

class CastCommand(Command):
    name = "cast"
    aliases = ["c"]
    description = "Cast a spell at a target or location."
    args_help = "<spell_name> [target_name]"

    async def execute(self, ctx: CommandContext, args: List[str]):
        try:
            async with LockService.acquire(ctx.campaign_id):
                await self._execute_locked(ctx, args)
        except TimeoutError:
            await ctx.sio.emit('system_message', {'content': "🚫 Action blocked: Server is processing another request. Please try again."}, room=ctx.sid)

    async def _execute_locked(self, ctx: CommandContext, args: List[str]):
        if not args:
            await ctx.sio.emit('system_message', {'content': f"Usage: @{self.name} {self.args_help}"}, room=ctx.campaign_id)
            return

        # Simple heuristic to split args: everything before ' at ' or ' on ' is spell, rest is target
        # If no explicit preposition, try to match the last word as target if it exists in the room
        # For a v1, let's just use quotes or assume the last word is the target if multiple words
        # Actually, let's just make target optional and handle it in the service
        # Let's try splitting by " at " or " on " first:
        full_args = " ".join(args).lower()
        spell_name = full_args
        target_name = ""

        if " at " in full_args:
            parts = full_args.split(" at ", 1)
            spell_name = parts[0].strip()
            target_name = parts[1].strip()
        elif " on " in full_args:
            parts = full_args.split(" on ", 1)
            spell_name = parts[0].strip()
            target_name = parts[1].strip()
        elif len(args) > 1:
             # Assume last word is target if no prepositions
             spell_name = " ".join(args[:-1]).strip()
             target_name = args[-1].strip()

        campaign_id = ctx.campaign_id
        sender_id = ctx.sender_id
        sender_name = ctx.sender_name
        sio = ctx.sio
        db = ctx.db
        sid = ctx.sid

        # Check Phase / Start Combat? Casting a spell could start combat if target is hostile
        game_state = await GameService.get_game_state(campaign_id, db)
        if not game_state: return

        was_out_of_combat = (game_state.phase != 'combat')

        # Check if target is hostile
        is_hostile_target = False
        if target_name or ctx.target_id:
            target_char_for_combat_check = GameService._find_char_by_name(game_state, target_name or "", ctx.target_id)
            if target_char_for_combat_check:
                if any(e.id == target_char_for_combat_check.id for e in game_state.enemies):
                    is_hostile_target = True
                else:
                    for n in game_state.npcs:
                        if n.id == target_char_for_combat_check.id and getattr(n, 'data', {}).get('hostile') == True:
                            is_hostile_target = True
                            break

        # If in combat, check turn
        if game_state.phase == 'combat':
            if game_state.active_entity_id != sender_id:
                active_name = "Unknown"
                for c in (game_state.party + game_state.enemies + game_state.npcs):
                    if c.id == game_state.active_entity_id:
                        active_name = c.name
                        break
                await sio.emit('system_message', {'content': f"🚫 It is not your turn! It is **{active_name}**'s turn."}, room=campaign_id)
                return

        # Resolve Cast
        result = await CombatService.resolution_cast(campaign_id, sender_id, sender_name, spell_name, target_name, db, target_id=ctx.target_id)

        if not result['success']:
            await sio.emit('system_message', {'content': result['message']}, room=campaign_id)
            return

        # Emit Mechanics
        mech_msg = result.get('message', f"✨ **{sender_name}** cast a spell!")

        save_result = await ChatService.save_message(campaign_id, 'system', 'System', mech_msg, db=db)
        await sio.emit('chat_message', {
            'sender_id': 'system', 'sender_name': 'System', 'content': mech_msg, 'id': save_result['id'], 'timestamp': save_result['timestamp'], 'is_system': True
        }, room=campaign_id)

        if 'game_state' in result:
             await StateService.emit_state_update(campaign_id, result['game_state'], sio)

        await db.commit()

        # Narration
        narration_context = mech_msg
        if result.get('game_state') and getattr(result['game_state'], 'phase', '') != 'combat':
             # Maybe combat ended?
             if game_state.phase == 'combat':
                  narration_context += "\n[SYSTEM NOTE TO DM: Combat has just concluded! Provide a brief, atmospheric summary of the battle's aftermath. Describe the silence returning to the room, the state of the party, and explicitly ask the players what they intend to do next now that the threat has passed.]"

        await NarratorService.narrate(
            campaign_id=campaign_id,
            context=narration_context,
            sio=sio,
            db=db,
            mode="combat_narration",
            sid=sid
        )
        await db.commit()

        if was_out_of_combat and is_hostile_target:
            # Start Combat Trigger
            start_res = await CombatService.start_combat(campaign_id, db)
            if start_res['success']:
                await sio.emit('system_message', {'content': "⚔️ **COMBAT STARTED!** Rolling Initiative..."}, room=campaign_id)
                await StateService.emit_state_update(campaign_id, start_res['game_state'], sio)

                # Check if it is THIS user's turn
                active_name = "Unknown"
                for c in (start_res['game_state'].party + start_res['game_state'].enemies + start_res['game_state'].npcs):
                    if c.id == start_res['active_entity_id']:
                        active_name = c.name
                        break
                # await sio.emit('system_message', {'content': f"Initiative Rolled! It is **{active_name}**'s turn first."}, room=campaign_id)

                # Trigger AI Turn if it's not the player
                from app.services.turn_manager import TurnManager
                await TurnManager.process_turn(campaign_id, start_res['active_entity_id'], start_res['game_state'], sio, db=db)
                await db.commit()
            return

        # Advance Turn if in combat AND the action wasn't a free action (casting usually takes an action)
        if result.get('game_state') and getattr(result['game_state'], 'phase', '') == 'combat':
            try:
                from app.services.turn_manager import TurnManager
                await TurnManager.advance_turn(campaign_id, sio, db, current_game_state=result.get('game_state'))
                await db.commit()
            except Exception as e:
                import traceback
                logger.error(f"CRITICAL ERROR in advance_turn (cast): {e}\n{traceback.format_exc()}")
