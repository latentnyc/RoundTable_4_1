import asyncio
import logging
import traceback
from app.services.game_service import GameService
from app.services.ai_service import AIService
from app.services.chat_service import ChatService
from app.services.narrator_service import NarratorService
from db.session import AsyncSessionLocal

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
                
                # Active ID check happens inside loop now
                
                # 1. Advance the turn index (if needed)
                if should_advance:
                    if db:
                        active_id, game_state = await GameService.next_turn(campaign_id, db, current_game_state=game_state, commit=False)
                    else:
                        async with AsyncSessionLocal() as session:
                            active_id, game_state = await GameService.next_turn(campaign_id, session, current_game_state=game_state, commit=False)
                    
                    pending_changes = True
                    logger.debug(f"Advanced turn to Index {game_state.turn_index}, Active: {active_id}")
                
                # Should advance for next loop
                should_advance = True
                active_id = game_state.active_entity_id if game_state else None

                if not active_id:
                    logger.error("Failed to advance turn or no turn order.")
                    break # Exit loop to save
    
                # LOGGING
                logger.debug(f"TurnManager -> Index: {game_state.turn_index}, ActiveID: {active_id}")
                # System message for debugging removed to clean up user chat
    
                # Emit State Update
                await sio.emit('game_state_update', game_state.model_dump(), room=campaign_id)
                
                # 2. Notify whose turn it is
                active_char = next((c for c in (game_state.party + game_state.enemies + game_state.npcs) if c.id == active_id), None)
                if active_char:
                    turn_msg = f"It is now **{active_char.name}**'s turn!"
                    await sio.emit('system_message', {'content': turn_msg}, room=campaign_id)
    
                if not active_char:
                     break
    
                # 3. Check if AI
                is_ai = False
                if hasattr(active_char, 'is_ai') and active_char.is_ai:
                    is_ai = True
                elif any(e.id == active_id for e in game_state.enemies):
                    is_ai = True
                elif any(n.id == active_id for n in game_state.npcs):
                    is_ai = True
                
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
                except Exception as e:
                    logger.error(f"Error executing AI turn: {e}\n{traceback.format_exc()}")
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
    async def execute_ai_turn(campaign_id: str, actor, game_state, sio, db, commit: bool = True):
        """
        Simple AI logic: Attack closest/random hostile.
        """
        import random
        
        # Determine Targets
        # If actor is a Player (AI controlled), target enemies.
        targets = []
        is_actor_party = any(p.id == actor.id for p in game_state.party)
        logger.debug(f"Executing AI Turn for {actor.name} (ID: {actor.id}). Is Party: {is_actor_party}")
        
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
                 targets = []
                 await sio.emit('system_message', {'content': f"{actor.name} watches the conflict hesitantly."}, room=campaign_id)
                 return game_state

        else:
             # Default Enemies target Party + Allied NPCs
             targets = list(game_state.party)
             allied_npcs = [n for n in game_state.npcs if n.data.get('ally') == True or n.data.get('friendly') == True]
             targets.extend(allied_npcs)
             
        valid_targets = [t for t in targets if t.hp_current > 0]
        logger.debug(f"Found {len(valid_targets)} valid targets.")
        
        if not valid_targets:
            # No targets? Pass turn.
            logger.debug("No targets found. Passing turn.")
            await sio.emit('system_message', {'content': f"{actor.name} looks around, finding no targets."}, room=campaign_id)
            return game_state

        # Target Priority: Lowest Health Percentage
        # This makes the AI ruthless and focuses fire on weakened targets.
        valid_targets.sort(key=lambda t: (t.hp_current / t.hp_max) if t.hp_max > 0 else 1.0)
        
        # Pick the lowest health one
        target = valid_targets[0]
        
        # Resolve Attack
        result = await GameService.resolution_attack(campaign_id, actor.id, actor.name, target.name, db, current_state=game_state, commit=commit)
        
        # Mechanics Log
        prefix = "⚔️ "
        mech_msg = f"{prefix}**{actor.name}** attacks **{target.name}**!\n"
        mech_msg += f"**Roll:** {result.get('attack_roll','?')} + {result.get('attack_mod','?')} = **{result.get('attack_total','?')}** vs AC {result.get('target_ac','?')}\n"
        
        if result.get('is_hit'):
            mech_msg += f"**HIT!** 🩸 Damage: **{result.get('damage_total','0')}** ({result.get('damage_detail','')})\n"
            mech_msg += f"Target HP: {result.get('target_hp_remaining','?')}"
        else:
            mech_msg += "**MISS!** 🛡️"

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
