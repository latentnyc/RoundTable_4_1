import asyncio
import logging
import re
from app.services.combat_service import CombatService
from app.services.ai_service import AIService
from app.services.chat_service import ChatService
from app.services.narrator_service import NarratorService
from app.services.pathfinding_service import PathfindingService
from app.services.state_service import StateService
from app.utils.grid_utils import hex_distance
from app.utils.entity_utils import EntityUtils

logger = logging.getLogger(__name__)

class AITurnService:
    @staticmethod
    async def _select_optimal_target(campaign_id: str, actor, game_state, sio):
        party_entities = [game_state.entities.get(pid) for pid in getattr(game_state, 'party_ids', []) if pid in getattr(game_state, 'entities', {})]
        enemy_entities = [game_state.entities.get(eid) for eid in getattr(game_state, 'enemy_ids', []) if eid in getattr(game_state, 'entities', {})]
        npc_entities = [game_state.entities.get(nid) for nid in getattr(game_state, 'npc_ids', []) if nid in getattr(game_state, 'entities', {})]
        
        is_party = any(p.id == actor.id for p in party_entities if p)
        
        if is_party:
            valid_enemies = [e for e in enemy_entities if e and getattr(e, 'hp_current', 0) > 0]
            hostile_npcs = [n for n in npc_entities if n and getattr(n, 'hp_current', 0) > 0 and (getattr(n, 'hostile', False) or (hasattr(n, 'data') and n.data.get('hostile', False)))]
            hostiles = valid_enemies + hostile_npcs
        else:
            hostiles = [p for p in party_entities if p and getattr(p, 'hp_current', 0) > 0]
            
        if not hostiles:
            return None
            
        if getattr(actor, 'position', None) is None:
            return hostiles[0]
            
        closest = None
        min_dist = float('inf')
        for h in hostiles:
            if getattr(h, 'position', None) is None: continue
            dist = actor.position.distance_to(h.position)
            if dist < min_dist:
                min_dist = dist
                closest = h
                
        return closest or hostiles[0]

    @staticmethod
    def _format_combat_log(actor, target, action_result):
        success = action_result.get("success", False)
        actor_name = getattr(actor, 'name', 'Unknown')
        target_name = getattr(target, 'name', 'Unknown') if target else 'Unknown'
        
        if not success:
            return f"**{actor_name}** failed to act: {action_result.get('message', 'Unknown reason')}."
            
        is_hit = action_result.get("is_hit", False)
        damage = action_result.get("total_damage", 0)
        
        if is_hit:
            return f"⚔️ **{actor_name}** hit **{target_name}** for **{damage} damage**!"
        else:
            return f"🛡️ **{actor_name}** attacked **{target_name}** but missed!"

    @staticmethod
    async def execute_ai_turn(campaign_id: str, actor, game_state, sio, db, commit: bool = True):
        """
        Simple AI logic: Attack closest/random hostile.
        """
        actor_name = EntityUtils.get_display_name(actor)
        logger.debug(f"Executing AI Turn for {actor_name} (ID: {actor.id}) at Position: q={actor.position.q}, r={actor.position.r}")

        target = await AITurnService._select_optimal_target(campaign_id, actor, game_state, sio)


        if not target:
            logger.debug("No targets found. Passing turn.")
            return game_state

        # Calculate max_attack_range based on equipment/actions
        max_attack_range = 1
        weapons = []
        is_spellcaster = False
        
        if getattr(actor, 'sheet_data', None):
            weapons = [item for item in actor.sheet_data.get('equipment', []) if isinstance(item, dict) and item.get('type') == 'Weapon']
            if actor.sheet_data.get('spells'):
                is_spellcaster = True
                
        if getattr(actor, 'data', None):
            for action in actor.data.get('actions', []):
                if not isinstance(action, dict):
                    continue
                desc = action.get('desc', '').lower()
                name = action.get('name', '').lower()
                if 'ranged weapon attack' in desc or 'range ' in desc or 'ft.' in desc or 'feet' in desc:
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
             await sio.emit('system_message', {'content': f"⚠️ {actor_name} passes their turn: Coordinates missing or trapped in void."}, room=campaign_id)
             return game_state

        dist_to_target = actor.position.distance_to(target.position)
        
        # Check LOS if within raw distance range
        has_los = False
        if dist_to_target <= max_attack_range:
            has_los = PathfindingService.check_line_of_sight(
                actor.position, 
                target.position, 
                getattr(game_state.location, 'walkable_hexes', [])
            )
                    
        needs_to_move = dist_to_target > max_attack_range or not has_los

        if needs_to_move:
            # Need to move closer to get within range/LOS
            obstacle_hexes = set()
            all_entities = list(game_state.entities.values()) if hasattr(game_state, 'entities') else []
            
            # Assume anyone living is an obstacle to walking straight through
            for entity in all_entities:
                 if getattr(entity, 'hp_current', 0) > 0 and getattr(entity, 'position', None) and entity.id != actor.id:
                      obstacle_hexes.add((entity.position.q, entity.position.r, entity.position.s))

            allied_hexes = set()
            party_ids_set = set(getattr(game_state, 'party_ids', []))
            for pid in party_ids_set:
                 p = game_state.entities.get(pid)
                 if p and p.id != actor.id and getattr(p, 'position', None):
                      allied_hexes.add((p.position.q, p.position.r, p.position.s))

            max_move = actor.speed // 5 if hasattr(actor, 'speed') and actor.speed else 6

            # BFS to find truly reachable hexes and their paths
            start_hex = (actor.position.q, actor.position.r, actor.position.s)
            
            visited = PathfindingService.find_reachable_hexes(
                start_hex, 
                max_move, 
                getattr(game_state.location, 'walkable_hexes', []), 
                obstacle_hexes
            )

            reachable_and_valid = [h for h in visited if h != start_hex and h not in allied_hexes]
            
            if reachable_and_valid:
                # Sort reachable hexes by distance to target
                reachable_and_valid.sort(key=lambda h: hex_distance(h[0], h[1], h[2], target.position.q, target.position.r, target.position.s))
                
                best_hex = reachable_and_valid[0]
                new_dist_to_target = hex_distance(best_hex[0], best_hex[1], best_hex[2], target.position.q, target.position.r, target.position.s)
                
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
                        has_los = PathfindingService.check_line_of_sight(
                            actor.position, 
                            target.position, 
                            getattr(game_state.location, 'walkable_hexes', [])
                        )

        # ── Decide: Cast spell or weapon attack? ──
        # AI prefers ranged spells when out of melee range and has Tier A damage cantrips
        use_spell = None
        if is_spellcaster and getattr(actor, 'sheet_data', None) and dist_to_target > 1 and has_los:
            from app.services.spell_service import TIER_A_SPELLS, init_spell_slots, consume_spell_slot
            actor_spells = actor.sheet_data.get('spells', [])
            for spl in actor_spells:
                spl_id = spl.get('id', '') if isinstance(spl, dict) else ''
                spl_name = spl.get('name', '') if isinstance(spl, dict) else str(spl)
                if spl_id not in TIER_A_SPELLS and not any(spl_name.lower() in ta.replace('-', ' ') for ta in TIER_A_SPELLS):
                    continue
                # Check it's a damage spell (not healing) by looking at ID
                healing_spells = {'cure-wounds', 'healing-word', 'heal'}
                if spl_id in healing_spells:
                    continue
                # Prefer cantrips (level 0) since they're free
                spl_level = spl.get('data', {}).get('level', 0) if isinstance(spl, dict) else 0
                if spl_level == 0:
                    use_spell = spl
                    break
                # Leveled spell: check if we have slots
                if spl_level > 0:
                    init_spell_slots(actor.sheet_data, getattr(actor, 'role', 'Fighter'), getattr(actor, 'level', 1))
                    current_slots = actor.sheet_data.get('spell_slots_current', {})
                    if current_slots.get(str(spl_level), 0) > 0:
                        use_spell = spl
                        # Don't break — keep looking for a cantrip (prefer free spells)

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

        # Resolve Attack or Spell Cast
        if use_spell:
            spell_name = use_spell.get('name', '') if isinstance(use_spell, dict) else str(use_spell)
            result = await CombatService.resolution_cast(campaign_id, actor.id, actor.name, spell_name, target.name, db, commit=commit, target_id=str(target.id))
        else:
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
        mech_msg = AITurnService._format_combat_log(actor, target, result)
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
