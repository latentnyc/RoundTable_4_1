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

# Global lock for turn management used to be here, but we now use LockService for distributed locking
from app.services.lock_service import LockService
from app.services.state_service import StateService

class TurnManager:
    @staticmethod
    async def advance_turn(campaign_id: str, sio, db=None, recursion_depth=0, current_game_state=None):
        """
        Advances the turn and handles AI actions if the new active entity is an AI.
        """
        # We start the loop. The loop itself will acquire/release locks per step.
        await TurnManager._turn_loop(campaign_id, sio, db, current_game_state, advance_first=True)

    @staticmethod
    async def process_turn(campaign_id: str, active_id: str, game_state, sio, recursion_depth=0, db=None):
        """
        Process the CURRENT turn (e.g. at start of combat) without advancing index first.
        Then enters the normal turn loop (AI checks, etc).
        """
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
    async def _process_turn_step(campaign_id: str, sio, game_state, active_id: str, db=None):
         # Emit State Update
         await StateService.emit_state_update(campaign_id, game_state, sio)

         # Notify whose turn it is
         active_char = next((c for c in (game_state.party + game_state.enemies + game_state.npcs) if c.id == active_id), None)
         if not active_char:
             return None

         is_ai = TurnManager._is_character_ai(game_state, active_id)

         if not is_ai:
             turn_msg = f"It is now **{active_char.name}**'s turn!"
             # Let the DM or character narrate the turn directly instead of announcing it redundantly
             # await sio.emit('system_message', {'content': turn_msg}, room=campaign_id)
             
             if db:
                 context_str = f"[SYSTEM NOTE TO DM: It is currently {active_char.name}'s turn. Provide a brief 1-sentence atmospheric summary of the current battle situation, then explicitly ask {active_char.name} what they would like to do. Do NOT narrate an action, simply prompt them for their turn.]"
                 await NarratorService.narrate(
                     campaign_id=campaign_id,
                     context=context_str,
                     sio=sio,
                     db=db,
                     mode="turn_start_narration"
                 )

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

                # 1. Acquire Lock for Turn State Mutation
                try:
                    async with LockService.acquire(campaign_id):
                        if should_advance:
                            # Re-fetch state securely under lock if we yielded previously
                            if not advance_first and ai_turn_count > 0:
                                if db:
                                    game_state = await GameService.get_game_state(campaign_id, db)
                                else:
                                    async with AsyncSessionLocal() as session:
                                        game_state = await GameService.get_game_state(campaign_id, session)

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

                        # 2. Process Turn UI/State Updates (Still under lock to ensure consistency)
                        step_result = await TurnManager._process_turn_step(campaign_id, sio, game_state, active_id, db=db)
                        if not step_result:
                            break
                        active_char, is_ai = step_result

                        if not is_ai:
                            # Human turn, stop loop
                            logger.debug(f"Turn is Human ({active_char.name}). Stopping loop.")
                            break

                        # 4. AI Turn Logic (Phase 1: Setup)
                        ai_turn_count += 1
                        await sio.emit('typing_indicator', {'sender_id': active_id, 'is_typing': True}, room=campaign_id)
                        
                        # Save state before dropping lock for sleep
                        if pending_changes and game_state:
                            logger.info(f"Saving pre-AI turn state for campaign {campaign_id}")
                            if db:
                                await GameService.save_game_state(campaign_id, game_state, db)
                                await db.commit()
                            else:
                                async with AsyncSessionLocal() as session:
                                    await GameService.save_game_state(campaign_id, game_state, session)
                                    await session.commit()
                            pending_changes = False

                except TimeoutError:
                    logger.warning(f"Lock timeout during turn loop setup for {campaign_id}")
                    break

                # -- LOCK DROPPED --
                # Pacing sleep outside the lock to let humans interact with the app.
                await asyncio.sleep(2)

                # -- REACQUIRE LOCK for AI Action --
                try:
                    async with LockService.acquire(campaign_id):
                        # Always refresh state in case humans moved!
                        if db:
                            game_state = await GameService.get_game_state(campaign_id, db)
                        else:
                            async with AsyncSessionLocal() as session:
                                game_state = await GameService.get_game_state(campaign_id, session)
                                
                        # Execute the Turn
                        try:
                            # Re-resolve active_char from the newly fetched state so mutations apply to the correct object tree
                            active_char = next((c for c in (game_state.party + game_state.enemies + game_state.npcs) if c.id == active_id), None)
                            if not active_char:
                                break

                            # Use shared DB if available to ensure we see uncommitted changes (Isolation)
                            if db:
                                 new_state = await TurnManager.execute_ai_turn(campaign_id, active_char, game_state, sio, db, commit=False)
                                 if new_state:
                                      game_state = new_state
                                      pending_changes = True
                            else:
                                async with AsyncSessionLocal() as session:
                                    new_state = await TurnManager.execute_ai_turn(campaign_id, active_char, game_state, sio, session, commit=False)
                                    if new_state:
                                         game_state = new_state
                                         pending_changes = True
                                         
                            # Save state after AI action BEFORE dropping lock for next sleep
                            if pending_changes and game_state:
                                if db:
                                    await GameService.save_game_state(campaign_id, game_state, db)
                                    await db.commit()
                                else:
                                    async with AsyncSessionLocal() as session:
                                        await GameService.save_game_state(campaign_id, game_state, session)
                                        await session.commit()
                                pending_changes = False
                                
                        except SQLAlchemyError as e:
                            logger.error("Database error executing AI turn: %s\n%s", str(e), traceback.format_exc())
                            await sio.emit('system_message', {'content': f"AI DB Error for {active_char.name}: {e}"}, room=campaign_id)
                        except Exception as e:
                            logger.error(f"Service Error: {e}", exc_info=True)
                            await sio.emit('system_message', {'content': f"AI Error for {active_char.name}: {e}"}, room=campaign_id)
                            # If AI fails, we still want to loop to next turn
                            pass
                            
                except TimeoutError:
                    logger.warning(f"Lock timeout during AI action for {campaign_id}")
                    break

                # -- LOCK DROPPED --
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

        # Target Priority: Absolute Lowest HP
        valid_targets.sort(key=lambda t: t.hp_current)
        return valid_targets[0]

    @staticmethod
    def _format_combat_log(actor, target, result: dict) -> str:
        prefix = "⚔️ "
        target_type = getattr(target, 'type', getattr(target, 'race', ''))
        if not target_type and hasattr(target, 'data') and isinstance(target.data, dict):
            target_type = target.data.get('race', '')
            
        type_str = f" [{target_type.upper()}]" if target_type else ""
        mech_msg = f"{prefix}**{actor.name}** attacks **{target.name}**{type_str}!\n"

        weapon_tags = []
        if result.get('weapon_name'):
            if result.get('is_ranged'):
                weapon_tags.append('[RANGED WEAPON ATTACK]')
            elif result.get('is_finesse'):
                weapon_tags.append('[FINESSE MELEE WEAPON ATTACK]')
            else:
                weapon_tags.append('[HEAVY/STANDARD MELEE WEAPON ATTACK]')
        else:
            weapon_tags.append('[UNARMED STRIKE]')
            
        tag_str = " ".join(weapon_tags)
        if tag_str:
             mech_msg += f"{tag_str}\n"

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
        logger.debug(f"Executing AI Turn for {actor.name} (ID: {actor.id}) at Position: q={actor.position.q}, r={actor.position.r}")

        target = await TurnManager._select_optimal_target(campaign_id, actor, game_state, sio)

        if not target:
            logger.debug("No targets found. Passing turn.")
            return game_state

        # Calculate max_attack_range based on equipment/actions
        max_attack_range = 1
        weapons = []
        is_spellcaster = False
        
        if hasattr(actor, 'sheet_data'):
            weapons = [item for item in actor.sheet_data.get('equipment', []) if isinstance(item, dict) and item.get('type') == 'Weapon']
            if actor.sheet_data.get('spells'):
                is_spellcaster = True
                
        if hasattr(actor, 'data'):
            for action in actor.data.get('actions', []):
                desc = action.get('desc', '').lower()
                name = action.get('name', '').lower()
                if 'ranged weapon attack' in desc or 'range ' in desc or 'ft.' in desc or 'feet' in desc:
                    import re
                    match = re.search(r'range\s+(\d+)', desc)
                    if match:
                        dist_ft = int(match.group(1))
                        max_attack_range = max(max_attack_range, dist_ft // 5)
                if 'spellcasting' in name or 'spell' in name:
                    is_spellcaster = True

        for w in weapons:
            w_type = w.get('data', {}).get('type', '').lower()
            if 'ranged' in w_type:
                normal_range = w.get('data', {}).get('range', {}).get('normal', 120)
                if isinstance(normal_range, int):
                    max_attack_range = max(max_attack_range, normal_range // 5)
                    
        if is_spellcaster and max_attack_range <= 1:
            max_attack_range = 12 # 60ft fallback for typical cantrips

        if actor.position is None or target.position is None:
             await sio.emit('system_message', {'content': f"⚠️ {actor.name} passes their turn: Coordinates missing or trapped in void."}, room=campaign_id)
             return game_state

        dist_to_target = actor.position.distance_to(target.position)
        
        # Check LOS if within raw distance range
        has_los = False
        if dist_to_target <= max_attack_range:
            walkable_set = {(h.q, h.r, h.s) for h in getattr(game_state.location, 'walkable_hexes', [])}
            los_path = actor.position.get_line_to(target.position)
            has_los = True
            for point in los_path:
                if (point.q, point.r, point.s) not in walkable_set:
                    has_los = False
                    break
                    
        needs_to_move = dist_to_target > max_attack_range or not has_los

        if needs_to_move:
            # Need to move closer to get within range/LOS
            obstacle_hexes = set()
            for entity in [e for e in game_state.enemies if e.hp_current > 0] + game_state.npcs:
                if entity.id != actor.id and entity.position:
                    obstacle_hexes.add((entity.position.q, entity.position.r, entity.position.s))

            allied_hexes = set()
            for p in game_state.party:
                if p.id != actor.id and p.position:
                    allied_hexes.add((p.position.q, p.position.r, p.position.s))

            walkable = {(h.q, h.r, h.s) for h in game_state.location.walkable_hexes}
            max_move = actor.speed // 5 if hasattr(actor, 'speed') and actor.speed else 6

            # BFS to find truly reachable hexes and their paths
            start_hex = (actor.position.q, actor.position.r, actor.position.s)
            
            def get_neighbors(curr):
                return [
                    (curr[0]+1, curr[1], curr[2]-1),
                    (curr[0]+1, curr[1]-1, curr[2]),
                    (curr[0], curr[1]-1, curr[2]+1),
                    (curr[0]-1, curr[1], curr[2]+1),
                    (curr[0]-1, curr[1]+1, curr[2]),
                    (curr[0], curr[1]+1, curr[2]-1)
                ]
                
            queue = [(start_hex, [])]
            visited = {start_hex: []}
            
            while queue:
                curr, path = queue.pop(0)
                
                if len(path) >= max_move:
                    continue
                    
                for n in get_neighbors(curr):
                    if n in walkable and n not in obstacle_hexes:
                        if n not in visited or len(path) + 1 < len(visited[n]):
                            visited[n] = path + [n]
                            queue.append((n, path + [n]))

            reachable_and_valid = [h for h in visited if h != start_hex and h not in allied_hexes]
            
            if reachable_and_valid:
                # Sort reachable hexes by distance to target
                reachable_and_valid.sort(key=lambda h: max(abs(h[0] - target.position.q), abs(h[1] - target.position.r), abs(h[2] - target.position.s)))
                
                best_hex = reachable_and_valid[0]
                new_dist_to_target = max(abs(best_hex[0] - target.position.q), abs(best_hex[1] - target.position.r), abs(best_hex[2] - target.position.s))
                
                if new_dist_to_target < dist_to_target:
                    actor.position.q = best_hex[0]
                    actor.position.r = best_hex[1]
                    actor.position.s = best_hex[2]
                    
                    logger.debug(f"AI {actor.name} moved to Position: q={actor.position.q}, r={actor.position.r}")
                    
                    anim_path = [{"q": h[0], "r": h[1], "s": h[2]} for h in visited[best_hex]]
                    await sio.emit('entity_path_animation', {'entity_id': actor.id, 'path': anim_path}, room=campaign_id)
                    
                    # We MUST save the game state here so the move is permanent
                    if commit:
                        logger.debug(f"Saving Game State for {actor.name} move out of combat.")
                        await StateService.save_game_state(campaign_id, game_state, db)
                        await db.commit()
                        logger.debug(f"Game State DB Commit for {actor.name} complete.")
                        
                    # Also need to emit game_state_update so other clients see new position definitively
                    await StateService.emit_state_update(campaign_id, game_state, sio)
                    # wait a little bit for the animation to play before attacking if they do attack
                    await asyncio.sleep(len(visited[best_hex]) * 0.15)
                    
                    # Update dist_to_target after moving
                    dist_to_target = actor.position.distance_to(target.position)
                    
                    # Recalculate LOS from new position
                    if dist_to_target <= max_attack_range:
                        walkable_set = {(h.q, h.r, h.s) for h in getattr(game_state.location, 'walkable_hexes', [])}
                        los_path = actor.position.get_line_to(target.position)
                        has_los = True
                        for point in los_path:
                            if (point.q, point.r, point.s) not in walkable_set:
                                has_los = False
                                break

        if dist_to_target > max_attack_range or not has_los:
            # Still couldn't reach
            dash_msg = f"💨 **{actor.name}** dashes toward **{target.name}**, but cannot reach them this turn."
            save_result = await ChatService.save_message(campaign_id, 'system', 'System', dash_msg, db=db)
            await sio.emit('chat_message', {
                'sender_id': 'system', 'sender_name': 'System', 'content': dash_msg, 'id': save_result['id'], 'timestamp': save_result['timestamp'], 'is_system': True, 'message_type': 'system'
            }, room=campaign_id)
            
            await NarratorService.narrate(
                campaign_id=campaign_id,
                context=dash_msg,
                sio=sio,
                db=db,
                mode="combat_narration"
            )
            
            # Save the dash (which did not result in an attack) to ensure any move is kept.
            if commit:
                await StateService.save_game_state(campaign_id, game_state, db)
                await db.commit()
                
            return game_state

        # Resolve Attack (now we are adjacent)
        result = await CombatService.resolution_attack(campaign_id, actor.id, actor.name, target.name, db, current_state=game_state, commit=commit, target_id=str(target.id))

        if not result.get("success"):
            err_msg = result.get("message", f"**{actor.name}** fails to attack **{target.name}**.")
            save_result = await ChatService.save_message(campaign_id, 'system', 'System', err_msg, db=db)
            await sio.emit('chat_message', {
                'sender_id': 'system', 'sender_name': 'System', 'content': err_msg, 'id': save_result['id'], 'timestamp': save_result['timestamp'], 'is_system': True, 'message_type': 'system'
            }, room=campaign_id)
            
            # Save the new state anyways (the movement still happened)
            if commit and result.get('game_state'):
                await StateService.save_game_state(campaign_id, result['game_state'], db)
                await db.commit()
                
            return result.get('game_state', game_state)

        # Mechanics Log
        mech_msg = TurnManager._format_combat_log(actor, target, result)
        logger.debug(f"AI {actor.name} completed Attack Resolution. Result HP: {result.get('target_hp_remaining')}, Position check: q={actor.position.q}, r={actor.position.r}")

        # Save & Emit Mechanics
        is_actor_party = any(p.id == actor.id for p in game_state.party)
        
        if is_actor_party:
             # Formulate hidden context
             hidden_ctx = f"You attempt to attack {target.name} and roll a total of {result.get('attack_total', '?')}."

             bark = await AIService.generate_bark(campaign_id, actor, hidden_ctx, db)
             if bark:
                 # Override mech_msg formatting for the DM, skipping the public system broadcast
                 dm_mech_context = f"[MECHANICS: {mech_msg.replace('**', '').replace('⚔️ ', '')}]"
                 
                 save_result = await ChatService.save_message(campaign_id, actor.id, actor.name, bark, db=db)
                 await sio.emit('chat_message', {
                     'sender_id': actor.id, 'sender_name': actor.name, 'content': bark, 'id': save_result['id'], 'timestamp': save_result['timestamp'], 'is_system': False, 'message_type': 'chat'
                 }, room=campaign_id)
                 
                 mech_msg = dm_mech_context
             else:
                 save_result = await ChatService.save_message(campaign_id, 'system', 'System', mech_msg, db=db)
                 await sio.emit('chat_message', {
                     'sender_id': 'system', 'sender_name': 'System', 'content': mech_msg, 'id': save_result['id'], 'timestamp': save_result['timestamp'], 'is_system': True, 'message_type': 'system'
                 }, room=campaign_id)
        else:
             # Standard System Emit
             save_result = await ChatService.save_message(campaign_id, 'system', 'System', mech_msg, db=db)
             await sio.emit('chat_message', {
                 'sender_id': 'system', 'sender_name': 'System', 'content': mech_msg, 'id': save_result['id'], 'timestamp': save_result['timestamp'], 'is_system': True, 'message_type': 'system'
             }, room=campaign_id)

        # Emit State Update (HP)
        if result.get('game_state'):
            await StateService.emit_state_update(campaign_id, result['game_state'], sio)

        if commit:
            logger.debug(f"Committing DB changes after {actor.name} action loop. Position should still be q={actor.position.q}, r={actor.position.r}.")
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
