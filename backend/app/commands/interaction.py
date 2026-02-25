from typing import List
from .base import Command, CommandContext
from app.services.game_service import GameService
from app.services.loot_service import LootService
from app.services.chat_service import ChatService
from app.services.narrator_service import NarratorService
from app.services.turn_manager import TurnManager
from app.services.lock_service import LockService
from app.services.state_service import StateService

class OpenCommand(Command):
    name = "open"
    aliases = ["loot", "search"]
    description = "Open a container or vessel to reveal its contents."
    args_help = "<vessel_name>"

    async def execute(self, ctx: CommandContext, args: List[str]):
        if not args:
            await ctx.sio.emit('system_message', {'content': f"Usage: @{self.name} {self.args_help}"}, room=ctx.campaign_id)
            return

        target_name = " ".join(args)

        try:
            async with LockService.acquire(ctx.campaign_id):
                result = await LootService.open_vessel(ctx.campaign_id, ctx.sender_name, target_name, ctx.db, target_id=ctx.target_id)
                await self._process_result(ctx, target_name, result)
        except TimeoutError:
            await ctx.sio.emit('system_message', {'content': "🚫 Action blocked: Server is processing another request. Please try again."}, room=ctx.sid)

    async def _process_result(self, ctx: CommandContext, target_name: str, result: dict):
        if result['success']:
            # Message to Chat
            msg = result['message']
            save_result = await ChatService.save_message(ctx.campaign_id, 'dm', 'Dungeon Master', msg, db=ctx.db) # Use DM as sender for loot findings
            # Actually, the result message "You find..." is better as a system message or a narrative response.
            # But if the player types @open, they expect a response.

            # Let's emit as a system message for now, but also maybe a chat message from the user is already there.
            # The user typed "@open corpse".
            # The response "Inside you find..." should probably be a system message or narrator.

            await ctx.sio.emit('system_message', {'content': msg}, room=ctx.campaign_id)

            if 'game_state' in result:
                await StateService.emit_state_update(ctx.campaign_id, result['game_state'], ctx.sio)

            # Trigger DM Narration (Optional, but good for flavor)
            # "As you rifle through the pockets of the goblin..."
            vessel = result.get('vessel')
            vessel_data = None
            content_str = msg

            if vessel:
                vessel_data = vessel.model_dump() if hasattr(vessel, 'model_dump') else vessel

                # Enrich item data
                from sqlalchemy import select
                from db.schema import items
                import json
                enriched = []
                for item_id in vessel_data.get('contents', []):
                    try:
                        ires = await ctx.db.execute(select(items).where(items.c.id == item_id))
                        irow = ires.mappings().fetchone()
                        if irow:
                            idata = json.loads(irow['data'])
                            desc_val = idata.get('desc', [])
                            desc_str = "\n".join([str(d) for d in desc_val]) if isinstance(desc_val, list) else str(desc_val)
                            enriched.append({
                                "id": item_id,
                                "name": idata.get('name', item_id.replace('-', ' ').replace('_', ' ').title()),
                                "description": desc_str,
                                "type": irow['type']
                            })
                        else:
                            enriched.append({
                                "id": item_id,
                                "name": item_id.replace('-', ' ').replace('_', ' ').title()
                            })
                    except Exception as e:
                        import logging
                        logging.getLogger(__name__).warning(f"Error enriching item {item_id}: {e}")
                        enriched.append({
                            "id": item_id,
                            "name": item_id.replace('-', ' ').replace('_', ' ').title()
                        })

                vessel_data['enriched_contents'] = enriched

                # Build content string for narrator
                content_names = [e['name'] for e in enriched]
                currency = vessel_data.get('currency', {})
                curr_strings = [f"{v} {k}" for k, v in currency.items() if v > 0]
                all_contents = content_names + curr_strings
                if all_contents:
                    content_str = ", ".join(all_contents)
                else:
                    content_str = "Empty"

            narrative_context = f"{ctx.sender_name} opens {vessel.name if vessel else target_name}.\nContents revealed: {content_str}"

            if "creak" in msg.lower() or "door" in target_name.lower():
                narrative_context += "\n[SYSTEM NOTE TO DM: The player ONLY opened the door, they have NOT moved through it yet. First, state that the door was opened. YOU MUST explicitly describe the room, items, or environment revealed BEYOND the door as detailed in the action report. DO NOT describe entering the new area.]"

            await NarratorService.narrate(
                campaign_id=ctx.campaign_id,
                context=narrative_context,
                sio=ctx.sio,
                db=ctx.db,
                mode="interaction_narration", # New mode or generic? "action_narration"
                sid=ctx.sid
            )

            # Emit vessel to opener for GUI Modal
            if vessel_data:
                await ctx.sio.emit('vessel_opened', {'vessel': vessel_data, 'opener_id': ctx.sender_id}, room=ctx.sid)

        else:
            await ctx.sio.emit('system_message', {'content': result.get('message', "Could not open that.")}, room=ctx.campaign_id)
            if result.get('out_of_range'):
                await NarratorService.narrate(
                    campaign_id=ctx.campaign_id,
                    context=result['message'] + f"\n[CRITICAL SYSTEM NOTE TO DM: The player's command was REJECTED by the physics engine because they are physically too far away from '{result.get('target_name', target_name)}' on the hex map. DO NOT narrate them touching or interacting with it. DO NOT advance the plot. DO NOT start combat. In 1-2 sentences, mock them playfully for trying to use telekinesis, or simply state their arms aren't that long.]",
                    sio=ctx.sio,
                    db=ctx.db,
                    mode="interaction_narration",
                    sid=ctx.sid
                )
            elif "interrupts" in result.get('message', '').lower():
                await NarratorService.narrate(
                    campaign_id=ctx.campaign_id,
                    context=result['message'],
                    sio=ctx.sio,
                    db=ctx.db,
                    mode="combat_narration",
                    sid=ctx.sid
                )
                opp_state = result.get('game_state')
                if opp_state and opp_state.phase == 'combat':
                    await TurnManager.process_turn(ctx.campaign_id, opp_state.active_entity_id, opp_state, ctx.sio, db=ctx.db)
