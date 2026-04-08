import json
import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from db.schema import locations
from app.models import GameState, Location
from app.services.state_service import StateService
from app.services.combat_service import CombatService
from app.utils.grid_utils import hex_distance, get_neighbors

class MovementService:
    @staticmethod
    async def resolution_move(campaign_id: str, actor_name: str, direction: str, db: AsyncSession):
        game_state = await StateService.get_game_state(campaign_id, db)
        if not game_state:
            return {"success": False, "message": "No active game state."}

        interrupted, opp_msg, latest_state = await CombatService._handle_opportunity_attack(campaign_id, actor_name, "move", db, game_state)
        if interrupted:
            return {"success": False, "message": opp_msg, "game_state": latest_state}

        # Look up current location data
        query = select(locations.c.data).where(locations.c.id == game_state.location.id)
        loc_res = await db.execute(query)
        loc_data_str = loc_res.scalar_one_or_none()

        if not loc_data_str:
            return {"success": False, "message": "Cannot determine current location layout."}

        loc_data = json.loads(loc_data_str)
        description = loc_data.get('description', {})
        connections = description.get('connections', [])

        target_conn = None
        for conn in connections:
            if conn.get('direction', '').lower() == direction.lower():
                target_conn = conn
                break

        if not target_conn:
             for conn in connections:
                 if direction.lower() in conn.get('target_id', '').lower() or direction.lower() in conn.get('description', '').lower():
                     target_conn = conn
                     break

        if not target_conn:
            return {"success": False, "message": f"There is no way to move '{direction}' from here."}

        interactables = loc_data.get('interactables', [])
        is_blocked = False
        blocking_door = None

        for item in interactables:
            if item.get('type') == 'door' and item.get('state') == 'closed':
                # Check if this specific door blocks the path we are trying to take
                conn_desc = target_conn.get('description', '').lower()
                door_name = item.get('name', '').lower()
                door_id = item.get('id', '').lower()
                move_dir = target_conn.get('direction', '').lower() or direction.lower()

                blocks_path = False
                if door_name and door_name in conn_desc:
                    blocks_path = True
                elif move_dir and move_dir in door_id:
                    blocks_path = True
                elif move_dir and move_dir in door_name:
                    blocks_path = True

                if blocks_path:
                    blocking_door = item.get('name')
                    is_blocked = True
                    break

        if is_blocked:
             return {"success": False, "message": f"The path is blocked by the {blocking_door}. You must open it first."}

        target_source_id = target_conn.get('target_id')
        query_dest = select(locations.c.id, locations.c.name, locations.c.data).where(
            locations.c.campaign_id == campaign_id,
            locations.c.source_id == target_source_id
        )
        dest_res = await db.execute(query_dest)
        dest_row = dest_res.first()

        if not dest_row:
             return {"success": False, "message": "The destination could not be found."}

        dest_data = json.loads(dest_row.data)
        dest_desc = dest_data.get('description', {})
        visual = dest_desc.get('visual', "") if isinstance(dest_desc, dict) else str(dest_desc)
        dest_interactables = dest_data.get('interactables', [])

        geometry_data = dest_data.get('geometry')
        geometry_obj = None
        if geometry_data:
            from app.models import LocationGeometry
            geometry_obj = LocationGeometry(**geometry_data)

        game_state.location = Location(
            id=dest_row.id,
            source_id=target_source_id,
            name=dest_row.name,
            description=visual,
            interactables=dest_interactables,
            geometry=geometry_obj
        )
        game_state.vessels = []

        await StateService.save_game_state(campaign_id, game_state, db)

        return {
             "success": True,
             "message": f"**{actor_name}** moved the party to **{dest_row.name}**.",
             "game_state": game_state
        }

    @staticmethod
    async def process_ai_following(campaign_id: str, leader_id: str, db: AsyncSession, sio, game_state: GameState):
        if getattr(game_state, 'phase', '') == 'combat':
            return
            
        leader = next((p for p in game_state.party if getattr(p, 'id', '') == leader_id), None)
        leader_pos = getattr(leader, 'position', None) if leader else None
        if not leader or not leader_pos:
            return

        def get_obstacle_hexes():
            obstacles = set()
            all_enemies = [e for e in game_state.enemies if getattr(e, 'hp_current', 0) > 0]
            for entity in all_enemies + game_state.npcs:
                pos = getattr(entity, 'position', None)
                if pos:
                    obstacles.add((getattr(pos, 'q', pos.get('q') if isinstance(pos, dict) else None), getattr(pos, 'r', pos.get('r') if isinstance(pos, dict) else None), getattr(pos, 's', pos.get('s') if isinstance(pos, dict) else None)))
            # remove Nones
            return {o for o in obstacles if None not in o}
            
        def get_allied_hexes(ignore_id=None):
            allies = set()
            for entity in game_state.party:
                eid = getattr(entity, 'id', None)
                pos = getattr(entity, 'position', None)
                if eid != ignore_id and pos:
                    allies.add((getattr(pos, 'q', pos.get('q') if isinstance(pos, dict) else None), getattr(pos, 'r', pos.get('r') if isinstance(pos, dict) else None), getattr(pos, 's', pos.get('s') if isinstance(pos, dict) else None)))
            return {a for a in allies if None not in a}

        walkable = {(h.q, h.r, h.s) for h in getattr(game_state.location, 'walkable_hexes', [])}
        state_changed = False

        l_q = getattr(leader_pos, 'q', leader_pos.get('q') if isinstance(leader_pos, dict) else 0)
        l_r = getattr(leader_pos, 'r', leader_pos.get('r') if isinstance(leader_pos, dict) else 0)
        l_s = getattr(leader_pos, 's', leader_pos.get('s') if isinstance(leader_pos, dict) else 0)

        for member in game_state.party:
            mid = getattr(member, 'id', '')
            if mid == leader_id:
                continue
                
            is_ai = getattr(member, 'is_ai', False)
            control_mode = getattr(member, 'control_mode', '')
            if not is_ai and control_mode != 'ai':
                continue
                
            m_pos = getattr(member, 'position', None)
            if not m_pos:
                continue

            m_q = getattr(m_pos, 'q', m_pos.get('q') if isinstance(m_pos, dict) else 0)
            m_r = getattr(m_pos, 'r', m_pos.get('r') if isinstance(m_pos, dict) else 0)
            m_s = getattr(m_pos, 's', m_pos.get('s') if isinstance(m_pos, dict) else 0)

            dist = hex_distance(m_q, m_r, m_s, l_q, l_r, l_s)
            
            if dist > 3:
                obstacles = get_obstacle_hexes()
                allies = get_allied_hexes(ignore_id=mid)
                m_speed = getattr(member, 'speed', 30)
                max_move = (m_speed // 5) if m_speed else 6
                
                start_hex = (m_q, m_r, m_s)
                queue = [(start_hex, [])]
                visited = {start_hex: []}
                
                while queue:
                    curr, path = queue.pop(0)
                    if len(path) >= max_move:
                        continue
                    for n in get_neighbors(curr):
                        if n in walkable and n not in obstacles:
                            if n not in visited or len(path) + 1 < len(visited[n]):
                                visited[n] = path + [n]
                                queue.append((n, path + [n]))
                                
                reachable_and_valid = [h for h in visited if h != start_hex and h not in allies]

                if reachable_and_valid:
                    reachable_and_valid.sort(key=lambda h: hex_distance(h[0], h[1], h[2], l_q, l_r, l_s))
                    best_hex = reachable_and_valid[0]
                    new_dist_to_leader = hex_distance(best_hex[0], best_hex[1], best_hex[2], l_q, l_r, l_s)
                    
                    if new_dist_to_leader < dist:
                        if isinstance(m_pos, dict):
                            m_pos['q'] = best_hex[0]
                            m_pos['r'] = best_hex[1]
                            m_pos['s'] = best_hex[2]
                        else:
                            m_pos.q = best_hex[0]
                            m_pos.r = best_hex[1]
                            m_pos.s = best_hex[2]
                        state_changed = True
                        path_found = visited[best_hex]
                        anim_path = [{"q": h[0], "r": h[1], "s": h[2]} for h in path_found]
                        if sio:
                            asyncio.create_task(sio.emit('entity_path_animation', {'entity_id': mid, 'path': anim_path}, room=campaign_id))

        if state_changed:
            await StateService.save_game_state(campaign_id, game_state, db)
            if sio:
                await StateService.emit_state_update(campaign_id, game_state, sio)
