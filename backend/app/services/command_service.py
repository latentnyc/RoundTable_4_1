import logging
import asyncio
from app.services.game_service import GameService
from app.services.chat_service import ChatService
from app.services.narrator_service import NarratorService
from app.services.turn_manager import TurnManager
from app.services.context_builder import build_narrative_context
from db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)

class CommandService:
    @staticmethod
    async def handle_move(campaign_id: str, sender_id: str, sender_name: str, target_name: str, sio, sid=None):
        async with AsyncSessionLocal() as db:
            move_result = await GameService.resolution_move(campaign_id, target_name, db)

            if move_result['success']:
                # Emit updates
                await sio.emit('game_state_update', move_result['game_state'].model_dump(), room=campaign_id)
                await sio.emit('system_message', {'content': move_result['message']}, room=campaign_id)

                # Trigger DM Narration
                rich_context = await build_narrative_context(db, campaign_id, move_result['game_state'])
                await NarratorService.narrate(
                    campaign_id=campaign_id,
                    context=rich_context,
                    sio=sio,
                    db=db,
                    mode="move_narration"
                )

                await db.commit()
                await sio.emit('typing_indicator', {'sender_id': 'dm', 'is_typing': False}, room=campaign_id)

            else:
                await sio.emit('system_message', {'content': move_result.get('message', "Move failed.")}, room=campaign_id)

    @staticmethod
    async def handle_identify(campaign_id: str, sender_id: str, sender_name: str, target_name: str, sio, sid=None):
        async with AsyncSessionLocal() as db:
             result = await GameService.resolution_identify(campaign_id, sender_name, target_name, db)

             # Persist system message (The Roll)
             roll_msg = f"🔍 **{result.get('actor_name', sender_name)}** investigates **{result.get('target_name', target_name)}**.\n"
             roll_msg += f"**Roll:** {result.get('roll_detail', '?')} = **{result.get('roll_total', '?')}**"
             if result.get('success'):
                 roll_msg += " (SUCCESS)"
             else:
                 roll_msg += " (FAILURE)"

             save_result = await ChatService.save_message(campaign_id, 'system', 'System', roll_msg, db=db)
             await sio.emit('chat_message', {
                'sender_id': 'system', 'sender_name': 'System', 'content': roll_msg, 'id': save_result['id'], 'timestamp': save_result['timestamp'], 'is_system': True
             }, room=campaign_id)

             # Trigger DM Narration (only if success usually, but let's narrate failure too if we want? The current logic narrate always)
             # Provide context to DM
             outcome_context = roll_msg
             if result.get('success'):
                 t_obj = result.get('target_object')
                 if hasattr(t_obj, 'name'):
                    outcome_context += f"\n[SYSTEM SECRET]: The target is truly {t_obj.name.upper()} ({getattr(t_obj, 'role', '')} {getattr(t_obj, 'race', '')})."

             await NarratorService.narrate(
                 campaign_id=campaign_id,
                 context=outcome_context,
                 sio=sio,
                 db=db,
                 mode="identify_narration"
             )
             await db.commit()

    @staticmethod
    async def handle_attack(campaign_id: str, sender_id: str, sender_name: str, target_name: str, sio, sid=None):
        async with AsyncSessionLocal() as db:
             # Check Phase / Start Combat
             game_state = await GameService.get_game_state(campaign_id, db)
             if not game_state: return

             if game_state.phase != 'combat':
                 # Start Combat Trigger
                 start_res = await GameService.start_combat(campaign_id, db)
                 if start_res['success']:
                     await sio.emit('system_message', {'content': "⚔️ **COMBAT STARTED!** Rolling Initiative..."}, room=campaign_id)
                     await sio.emit('game_state_update', start_res['game_state'].model_dump(), room=campaign_id)

                     # Check if it is THIS user's turn
                     if start_res['active_entity_id'] != sender_id:
                         active_name = "Unknown"
                         for c in (start_res['game_state'].party + start_res['game_state'].enemies + start_res['game_state'].npcs):
                             if c.id == start_res['active_entity_id']:
                                 active_name = c.name
                                 break
                         await sio.emit('system_message', {'content': f"Initiative Rolled! It is **{active_name}**'s turn first."}, room=campaign_id)

                         # NEW: Trigger AI Turn if it's not the player
                         await TurnManager.process_turn(campaign_id, start_res['active_entity_id'], start_res['game_state'], sio, db=db)

                         await db.commit()
                         return
                 game_state = start_res.get('game_state', game_state)

             # Check Logic: Is it my turn?
             if game_state.active_entity_id != sender_id:
                  active_name = "Unknown"
                  for c in (game_state.party + game_state.enemies + game_state.npcs):
                      if c.id == game_state.active_entity_id:
                          active_name = c.name
                          break
                  await sio.emit('system_message', {'content': f"🚫 It is not your turn! It is **{active_name}**'s turn."}, room=campaign_id)
                  return

             # Resolve Attack
             result = await GameService.resolution_attack(campaign_id, sender_id, sender_name, target_name, db)

             if not result['success']:
                 await sio.emit('system_message', {'content': result['message']}, room=campaign_id)
                 return

             # Emit Mechanics
             mech_msg = f"⚔️ **{result['attacker_name']}** attacks **{result['target_name']}**!\n"
             mech_msg += f"**Roll:** {result['attack_roll']} + {result['attack_mod']} = **{result['attack_total']}** vs AC {result['target_ac']}\n"
             if result['is_hit']:
                mech_msg += f"**HIT!** 🩸 Damage: **{result['damage_total']}** ({result['damage_detail']})\n"
                mech_msg += f"Target HP: {result['target_hp_remaining']}"
             else:
                mech_msg += "**MISS!** 🛡️"

             save_result = await ChatService.save_message(campaign_id, 'system', 'System', mech_msg, db=db)
             await sio.emit('chat_message', {
                'sender_id': 'system', 'sender_name': 'System', 'content': mech_msg, 'id': save_result['id'], 'timestamp': save_result['timestamp'], 'is_system': True
             }, room=campaign_id)

             await sio.emit('game_state_update', result['game_state'].model_dump(), room=campaign_id)
             await db.commit() # Commit mechanics

             # Narration
             await NarratorService.narrate(
                 campaign_id=campaign_id,
                 context=mech_msg,
                 sio=sio,
                 db=db,
                 mode="combat_narration"
             )
             await db.commit() # Commit narration

             # Advance Turn
             try:
                 await TurnManager.advance_turn(campaign_id, sio, db, current_game_state=result.get('game_state'))
                 await db.commit()
             except Exception as e:
                 import traceback
                 logger.error(f"CRITICAL ERROR in advance_turn: {e}\n{traceback.format_exc()}")
