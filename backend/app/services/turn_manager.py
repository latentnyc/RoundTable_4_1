import asyncio
import logging
import traceback
from app.services.game_service import GameService
from app.services.combat_service import CombatService
from app.services.ai_service import AIService
from app.services.chat_service import ChatService
from app.services.narrator_service import NarratorService
from db.session import AsyncSessionLocal
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)

# Global lock for turn management to prevent race conditions
_turn_locks = {}

def get_turn_lock(campaign_id: str):
    if campaign_id not in _turn_locks:
        _turn_locks[campaign_id] = asyncio.Lock()
    return _turn_locks[campaign_id]

class TurnManager:
    @staticmethod
    async def advance_turn(campaign_id: str, sio, db=None, recursion_depth=0, current_game_state=None):
        """
        Advances the turn and handles AI actions if the new active entity is an AI.
        Uses a lock to ensure only one turn advancement happens at a time.
        """
        lock = get_turn_lock(campaign_id)

        # If we can't acquire the lock immediately, it means another turn advance is in progress.
        # We should probably just return, or wait. Waiting might cause a buildup.
        # Given the game loop, dropping concurrent requests is safer than stacking them.
        if lock.locked() and recursion_depth == 0:
             logger.warning(f"Turn advancement already in progress for {campaign_id}. Skipping concurrent request.")
             return

        async with lock:
            await TurnManager._turn_loop(campaign_id, sio, db, current_game_state, advance_first=True)

    @staticmethod
    async def process_turn(campaign_id: str, active_id: str, game_state, sio, recursion_depth=0, db=None):
        """
        Process the CURRENT turn (e.g. at start of combat) without advancing index first.
        Then enters the normal turn loop (AI checks, etc).
        """
        lock = get_turn_lock(campaign_id)
        if lock.locked():
             logger.warning(f"Turn loop already in progress for {campaign_id}. Skipping process_turn.")
             return

        async with lock:
             await TurnManager._turn_loop(campaign_id, sio, db, game_state, advance_first=False)

    @staticmethod
    def _is_character_ai(game_state, character_id: str) -> bool:
        """Determines if the given character ID belongs to an AI controlled entity."""
        active_char = next((c for c in (game_state.party + game_state.enemies + game_state.npcs) if c.id == character_id), None)
        if not active_char:
            return False

        if hasattr(active_char, 'is_ai') and active_char.is_ai:
            return True
        elif hasattr(active_char, 'control_mode') and active_char.control_mode == 'ai':
            return True
        elif any(e.id == character_id for e in game_state.enemies):
            return True
        elif any(n.id == character_id for n in game_state.npcs):
            return True
        return False

    @staticmethod
    async def _advance_game_state(campaign_id: str, db, game_state):
        if db:
            active_id, next_state = await CombatService.next_turn(campaign_id, db, current_game_state=game_state, commit=False)
        else:
            async with AsyncSessionLocal() as session:
                active_id, next_state = await CombatService.next_turn(campaign_id, session, current_game_state=game_state, commit=False)
        return active_id, next_state

    @staticmethod
    async def _process_turn_step(campaign_id: str, sio, game_state, active_id: str):
         # Emit State Update
         await sio.emit('game_state_update', game_state.model_dump(), room=campaign_id)

         # Notify whose turn it is
         active_char = next((c for c in (game_state.party + game_state.enemies + game_state.npcs) if c.id == active_id), None)
         if not active_char:
             return None

         is_ai = TurnManager._is_character_ai(game_state, active_id)

         if not is_ai:
             turn_msg = f"It is now **{active_char.name}**'s turn!"
             await sio.emit('system_message', {'content': turn_msg}, room=campaign_id)

         return active_char, is_ai

    @staticmethod
    async def _turn_loop(campaign_id: str, sio, db, current_game_state, advance_first=True):
        # Iterative approach to avoid recursion limit
        game_state = current_game_state
        # Dynamic limit based on participant count, with a safe floor
        participant_count = len(game_state.turn_order) if game_state and game_state.turn_order else 10
        max_ai_turns = max(participant_count * 2, 20)
        ai_turn_count = 0

        # Flag to control if we assume the current state is the "fresh" turn to process
        # or if we need to fetch the next one immediately.
        should_advance = advance_first
        logger.debug(f"Starting Turn Loop. Max: {max_ai_turns}, AdvanceFirst: {advance_first}")

        pending_changes = False

        try:
            while ai_turn_count < max_ai_turns:
                logger.debug(f"Turn Loop Iteration {ai_turn_count}. ShouldAdvance: {should_advance}")

                # 1. Advance the turn index (if needed)
                if should_advance:
                    active_id, next_state = await TurnManager._advance_game_state(campaign_id, db, game_state)
                    if not next_state:
                        logger.info(f"Turn advance returned no state (Combat Ended or Error). Ending turn loop.")
                        break

                    game_state = next_state
                    pending_changes = True
                    logger.debug(f"Advanced turn to Index {game_state.turn_index}, Active: {active_id}")

                # Should advance for next loop
                should_advance = True
                active_id = game_state.active_entity_id if game_state else None

                if not active_id:
                    logger.error("Failed to advance turn or no turn order.")
                    break # Exit loop to save

                logger.debug(f"TurnManager -> Index: {game_state.turn_index}, ActiveID: {active_id}")

                # 2. Process Turn UI/State Updates
                step_result = await TurnManager._process_turn_step(campaign_id, sio, game_state, active_id)
                if not step_result:
                    break
                active_char, is_ai = step_result

                if not is_ai:
                    # Human turn, stop loop
                    logger.debug(f"Turn is Human ({active_char.name}). Stopping loop.")
                    break

                # 4. AI Turn Logic
                ai_turn_count += 1
                await sio.emit('typing_indicator', {'sender_id': active_id, 'is_typing': True}, room=campaign_id)
                await asyncio.sleep(2) # Pacing

                try:
                    # Use shared DB if available to ensure we see uncommitted changes (Isolation)
                    if db:
                         new_state = await TurnManager.execute_ai_turn(campaign_id, active_char, game_state, sio, db, commit=False)
                         if new_state:
                              game_state = new_state
                              pending_changes = True
                    else:
                        async with AsyncSessionLocal() as session:
                            # Refresh state from DB to be safe before acting
                            # But we have current_game_state
                            new_state = await TurnManager.execute_ai_turn(campaign_id, active_char, game_state, sio, session, commit=False)
                            if new_state:
                                 game_state = new_state
                                 pending_changes = True
                except SQLAlchemyError as e:
                    logger.error("Database error executing AI turn: %s\n%s", str(e), traceback.format_exc())
                    await sio.emit('system_message', {'content': f"AI DB Error for {active_char.name}: {e}"}, room=campaign_id)
                except Exception as e:
                    logger.error(f"Service Error: {e}", exc_info=True)
                    await sio.emit('system_message', {'content': f"AI Error for {active_char.name}: {e}"}, room=campaign_id)
                    # If AI fails, we still want to loop to next turn
                    pass

                await sio.emit('typing_indicator', {'sender_id': active_id, 'is_typing': False}, room=campaign_id)
                await asyncio.sleep(1)

                # Loop continues to next turn...

        finally:
            if pending_changes and game_state:
                logger.info(f"Batch saving game state for campaign {campaign_id}")
                if db:
                    await GameService.save_game_state(campaign_id, game_state, db)
                else:
                    async with AsyncSessionLocal() as session:
                        await GameService.save_game_state(campaign_id, game_state, session)
                        await session.commit()



    @staticmethod
    async def _select_optimal_target(campaign_id: str, actor, game_state, sio):
        import random
        targets = []
        is_actor_party = any(p.id == actor.id for p in game_state.party)

        if is_actor_party:
             # Party members (and their pets/summons) target enemies + hostile NPCs
             targets = list(game_state.enemies)
             hostile_npcs = [n for n in game_state.npcs if n.data.get('hostile') == True]
             targets.extend(hostile_npcs)

        elif any(n.id == actor.id for n in game_state.npcs):
             # NPC Logic
             is_hostile = actor.data.get('hostile') == True
             is_ally = actor.data.get('ally') == True or actor.data.get('friendly') == True

             if is_hostile:
                 # Hostile NPCs attack Party + Allied NPCs
                 targets = list(game_state.party)
                 allied_npcs = [n for n in game_state.npcs if n.data.get('ally') == True or n.data.get('friendly') == True]
                 targets.extend(allied_npcs)
             elif is_ally:
                 # Allied NPCs attack Enemies + Hostile NPCs
                 targets = list(game_state.enemies)
                 hostile_npcs = [n for n in game_state.npcs if n.data.get('hostile') == True]
                 targets.extend(hostile_npcs)
             else:
                 # Neutral NPCs target nothing (they will pass)
                 await sio.emit('system_message', {'content': f"{actor.name} watches the conflict hesitantly."}, room=campaign_id)
                 return None

        else:
             # Default Enemies target Party + Allied NPCs
             targets = list(game_state.party)
             allied_npcs = [n for n in game_state.npcs if n.data.get('ally') == True or n.data.get('friendly') == True]
             targets.extend(allied_npcs)

        valid_targets = [t for t in targets if t.hp_current > 0]

        if not valid_targets:
            await sio.emit('system_message', {'content': f"{actor.name} looks around, finding no targets."}, room=campaign_id)
            return None

        # Target Priority: Lowest Health Percentage
        valid_targets.sort(key=lambda t: (t.hp_current / t.hp_max) if t.hp_max > 0 else 1.0)
        return valid_targets[0]

    @staticmethod
    def _format_combat_log(actor, target, result: dict) -> str:
        prefix = "⚔️ "
        mech_msg = f"{prefix}**{actor.name}** attacks **{target.name}**!\n"
        mech_msg += f"**Roll:** {result.get('attack_roll','?')} + {result.get('attack_mod','?')} = **{result.get('attack_total','?')}** vs AC {result.get('target_ac','?')}\n"

        if result.get('is_hit'):
            mech_msg += f"**HIT!** 🩸 Damage: **{result.get('damage_total','0')}** ({result.get('damage_detail','')})\n"
            mech_msg += f"Target HP: {result.get('target_hp_remaining','?')}"
        else:
            mech_msg += "**MISS!** 🛡️"
        return mech_msg

    @staticmethod
    async def execute_ai_turn(campaign_id: str, actor, game_state, sio, db, commit: bool = True):
        """
        Simple AI logic: Attack closest/random hostile.
        """
        logger.debug(f"Executing AI Turn for {actor.name} (ID: {actor.id})")

        target = await TurnManager._select_optimal_target(campaign_id, actor, game_state, sio)

        if not target:
            logger.debug("No targets found. Passing turn.")
            return game_state

        # Resolve Attack
        result = await CombatService.resolution_attack(campaign_id, actor.id, actor.name, target.name, db, current_state=game_state, commit=commit)

        # Mechanics Log
        mech_msg = TurnManager._format_combat_log(actor, target, result)

        # Save & Emit Mechanics
        save_result = await ChatService.save_message(campaign_id, 'system', 'System', mech_msg, db=db)
        await sio.emit('chat_message', {
            'sender_id': 'system', 'sender_name': 'System', 'content': mech_msg, 'id': save_result['id'], 'timestamp': save_result['timestamp'], 'is_system': True
        }, room=campaign_id)

        # Emit State Update (HP)
        if result.get('game_state'):
            await sio.emit('game_state_update', result['game_state'].model_dump(), room=campaign_id)

        if commit:
            await db.commit()

        # Narration
        await NarratorService.narrate(
            campaign_id=campaign_id,
            context=mech_msg,
            sio=sio,
            db=db,
            mode="combat_narration"
        )

        return result.get('game_state')
