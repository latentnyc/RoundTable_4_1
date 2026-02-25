from typing import List
from .base import Command, CommandContext
from app.services.game_service import GameService
from app.services.loot_service import LootService
from app.services.chat_service import ChatService
from app.services.narrator_service import NarratorService
from app.services.turn_manager import TurnManager
from app.services.context_builder import build_narrative_context
from app.services.state_service import StateService

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
