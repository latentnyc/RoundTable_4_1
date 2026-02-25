import logging
import asyncio
from typing import Optional, List, Tuple
from langchain_core.tools import tool

from app.services.game_service import GameService
from app.services.loot_service import LootService
from app.services.state_service import StateService
from db.session import AsyncSessionLocal
from app.models import Coordinates
from app.socket_manager import sio

logger = logging.getLogger(__name__)

def create_interact_tool(campaign_id: str, character_name: str, db=None):
    """Factory to create a stateful interact tool for a specific AI character."""
    
    @tool
    async def interact_with_object(target_name: str) -> str:
        """Use this to open doors, loot corpses, search chests, or interact with an object on the map.
        It will automatically move your character up to 25 feet towards the object if necessary.
        If it's too far (more than 25 feet), or if there are multiple objects matching the name, it will ask for clarification.
        """
        session = db
        if not session:
            # Fallback if testing outside of a provided db scope
            async with AsyncSessionLocal() as temp_session:
                return await _run_interact(target_name, temp_session)
        else:
            return await _run_interact(target_name, session)

    async def _run_interact(target_name: str, session) -> str:
        try:
            game_state = await GameService.get_game_state(campaign_id, session)
            if not game_state:
                return "Error: Game state not found."

            # Find the actor
            actor = None
            for p in game_state.party + game_state.npcs:
                if getattr(p, 'name', '') == character_name:
                    actor = p
                    break
                    
            if not actor:
                 return "Error: Could not locate your character on the map."

            # Find matching interactables and vessels
            matches = []
            interactables = getattr(game_state.location, 'interactables', [])
            for item in interactables:
                # check if name or id matches
                iname = item.get('name', '')
                iid = item.get('id', '')
                if target_name.lower() in iname.lower() or target_name.lower() in iid.lower():
                    matches.append(("interactable", item))

            for v in getattr(game_state, 'vessels', []):
                if target_name.lower() in v.name.lower():
                    matches.append(("vessel", v))

            if len(matches) > 1:
                names = [m[1].get('name') if m[0] == 'interactable' else m[1].name for m in matches]
                # Filter out exact identical names to avoid "Found multiple: door, door"
                unique_names = list(set(names))
                if len(unique_names) > 1:
                     return f"Found multiple objects matching '{target_name}': {', '.join(unique_names)}. Ask the player to clarify which one they mean."
                # If they are all called "Wooden Door", we will just pick the closest one below.
                
            elif len(matches) == 0:
                return f"Could not find any object matching '{target_name}' nearby."

            # Find the closest match out of all matches
            best_match = None
            best_dist = float('inf')
            for m_type, m_obj in matches:
                 if m_type == 'interactable':
                     tp = m_obj.get('position', {})
                     t_pos = Coordinates(q=tp.get('q', 0), r=tp.get('r', 0), s=tp.get('s', 0))
                 else:
                     t_pos = m_obj.position
                     
                 dist = actor.position.distance_to(t_pos)
                 if dist < best_dist:
                     best_dist = dist
                     best_match = (m_type, m_obj, t_pos)

            obj_type, target, t_pos = best_match
            
            # Check distance
            max_reach = 6 # 5 hex movement (25ft) + 1 hex interact reach

            if best_dist > max_reach:
                 return f"The object is {best_dist * 5} feet away. You can only move up to 25 feet and interact at 5 feet (30 feet total reach). Inform the player it is too far to reach."
            
            # If distance > 1, we need to move
            if best_dist > 1:
                obstacle_hexes = set()
                for entity in [e for e in game_state.enemies if e.hp_current > 0] + game_state.party + game_state.npcs:
                    if entity.id != actor.id and getattr(entity, 'position', None):
                        obstacle_hexes.add((entity.position.q, entity.position.r, entity.position.s))

                walkable = {(h.q, h.r, h.s) for h in game_state.location.walkable_hexes}
                max_move = actor.speed // 5 if hasattr(actor, 'speed') and actor.speed else 6

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

                # Find hexes adjacent to target
                target_adj = get_neighbors((t_pos.q, t_pos.r, t_pos.s))
                valid_destinations = [h for h in target_adj if h in visited]

                if not valid_destinations:
                     return f"There is no walkable path to reach the {target_name}."

                # Pick the shortest path destination
                valid_destinations.sort(key=lambda h: len(visited[h]))
                best_hex = valid_destinations[0]

                actor.position.q = best_hex[0]
                actor.position.r = best_hex[1]
                actor.position.s = best_hex[2]

                # Emit animation
                if sio:
                    anim_path = [{"q": h[0], "r": h[1], "s": h[2]} for h in visited[best_hex]]
                    await sio.emit('entity_path_animation', {'entity_id': actor.id, 'path': anim_path}, room=campaign_id)
                    
                    # Apply local state change before acting
                    await StateService.emit_state_update(campaign_id, game_state, sio)
                    await asyncio.sleep(0.5) # Let animation play briefly

            # Now act on it using LootService rules
            act_target_name = None
            target_id = None
            if obj_type == 'interactable':
                 target_id = target.get('id')
                 act_target_name = target.get('name')
            else:
                 act_target_name = target.name
                 
            result = await LootService.open_vessel(campaign_id, actor.name, act_target_name, session, target_id=target_id)
            
            # Note: open_vessel performs distance validation and saves/commits the DB state automatically if successful.
            if result.get("success"):
                 if sio:
                     if "game_state" in result:
                         await StateService.emit_state_update(campaign_id, result["game_state"], sio)
                     if "message" in result:
                         await sio.emit('chat_message', {
                             'sender_id': 'system',
                             'sender_name': 'System',
                             'content': result['message'],
                             'timestamp': "Just now",
                             'is_system': True,
                             'message_type': 'narration'
                         }, room=campaign_id)
                 return f"Successfully moved to and opened the {act_target_name}. Tell the player what you did."
            else:
                 return f"Failed to open '{act_target_name}': {result.get('message')}"

        except Exception as e:
            logger.error(f"Error in interact_with_object tool: {e}", exc_info=True)
            return f"An error occurred while trying to interact: {e}"

    return interact_with_object
