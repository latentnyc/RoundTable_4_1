from app.services.combat_service import CombatService
import json
import asyncio
import functools
from typing import TYPE_CHECKING
from uuid import uuid4
from sqlalchemy import select, insert, update, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import GameState, Location
from db.schema import game_states, characters, monsters, npcs, locations
from game_engine.engine import GameEngine
from app.services.state_service import StateService

if TYPE_CHECKING:
    from app.models import Player, Enemy, NPC

class GameService:
    @staticmethod
    def _find_char_by_name(game_state, search_term: str, target_id: str = None):
        if target_id:
            for li in [game_state.party, game_state.enemies, game_state.npcs]:
                for c in li:
                    if c.id == target_id:
                        return c

        if not search_term:
            return None

        term = search_term.lower()

        # Priority 1: Exact ID or target_id Match
        for li in [game_state.party, game_state.enemies, game_state.npcs]:
            for c in li:
                if term == c.id.lower():
                    return c
                if hasattr(c, 'target_id') and c.target_id and term == c.target_id.lower():
                    return c

        # Priority 2: Exact Name Match
        for li in [game_state.party, game_state.enemies, game_state.npcs]:
            for c in li:
                if term == c.name.lower():
                    return c

        # Priority 3: Prefix Name Match
        for li in [game_state.party, game_state.enemies, game_state.npcs]:
            for c in li:
                if c.name.lower().startswith(term):
                    return c

        # Priority 4: Race / Type / Role Exact Match
        for li in [game_state.party, game_state.enemies, game_state.npcs]:
            for c in li:
                # Player
                if hasattr(c, 'race') and c.race and term == c.race.lower(): return c
                if hasattr(c, 'role') and c.role and term == c.role.lower(): return c

                # Enemy
                if hasattr(c, 'type') and c.type and term == c.type.lower(): return c

                # NPC
                if hasattr(c, 'data') and c.data:
                    if 'race' in c.data and term == str(c.data['race']).lower(): return c
                    if 'type' in c.data and term == str(c.data['type']).lower(): return c
                    if 'role' in c.data and term == str(c.data['role']).lower(): return c

        # Priority 5: Substring Name Match (Fallback)
        for li in [game_state.party, game_state.enemies, game_state.npcs]:
            for c in li:
                if term in c.name.lower():
                    return c

        return None

    @staticmethod
    def _run_engine_resolution(engine, actor_data, action_type, target_data, params):
        """Helper to run synchronous engine logic in an executor."""
        return engine.resolve_action(actor_data, action_type, target_data, params)

    @staticmethod
    def get_display_name(entity):
        """Returns name or unidentified_name based on state"""
        if hasattr(entity, 'identified') and not entity.identified:
            if entity.unidentified_name:
                return entity.unidentified_name
            return "Unknown Entity"
        return entity.name

    @staticmethod
    def get_display_description(entity):
        """Returns description or unidentified_description based on state"""
        if hasattr(entity, 'identified') and not entity.identified:
            if entity.unidentified_description:
                return entity.unidentified_description
            if entity.unidentified_name: # Fallback if specific desc is missing but name implies mystery
                return f"A mysterious {entity.unidentified_name}."

        # Fallback to main description if available
        if hasattr(entity, 'description') and entity.description:
            return entity.description

        return f"You see {entity.name}."

    @staticmethod
    def get_bark(entity, trigger: str) -> str:
        """
        Retrieves a random bark for the given trigger (e.g. 'aggro', 'victory', 'death').
        Returns None if no bark is found.
        """
        import random

        # Check direct barks field (if model updated)
        if hasattr(entity, 'barks') and entity.barks:
            options = entity.barks.get(trigger)
            if options:
                return random.choice(options)

        # Fallback to data.voice.barks
        if hasattr(entity, 'data') and entity.data:
            voice = entity.data.get('voice', {})
            barks = voice.get('barks', {})
            options = barks.get(trigger)
            if options:
                return random.choice(options)

        return None


    @staticmethod
    async def get_game_state(campaign_id: str, db: AsyncSession) -> GameState:
        return await StateService.get_game_state(campaign_id, db)

    @staticmethod
    async def save_game_state(campaign_id: str, game_state: GameState, db: AsyncSession):
         return await StateService.save_game_state(campaign_id, game_state, db)



    @staticmethod
    async def resolution_identify(campaign_id: str, actor_name: str, target_name: str, db: AsyncSession, target_id: str = None):
        """
        Mechanically resolves an identify/investigate check.
        Returns a dict with result and message.
        """
        import random

        game_state = await GameService.get_game_state(campaign_id, db)
        if not game_state:
            return {"success": False, "message": "No active game state found!"}

        # Resolve Actor
        # Usually a player, but theoretically could be NPC vs NPC
        actor_char = None
        for p in game_state.party:
            if actor_name.lower() in p.name.lower():
                actor_char = p
                break

        if not actor_char:
             return {"success": False, "message": f"Could not find actor '{actor_name}'."}

        target_char = GameService._find_char_by_name(game_state, target_name, target_id)
        if not target_char:
            return {"success": False, "message": f"Could not find target '{target_name}'."}

        # Check if already identified
        if hasattr(target_char, 'identified') and target_char.identified:
             return {"success": True, "message": f"{target_char.name} is already identified.", "reason": "already_known", "target_object": target_char}

        # Mechanics: INT (Investigation) Check
        # DC Base: 12 (Hard enough to not be trivial, easy enough for proficient characters)
        dc = 12

        # Roll: d20 + Int Mod
        int_score = actor_char.stats.intelligence
        int_mod = (int_score - 10) // 2

        # Check Proficiency? (Assume Investigation proficiency if class matches or just flat for now)
        # Simplified: Just INT check

        roll = random.randint(1, 20)
        total = roll + int_mod

        is_success = total >= dc

        result_pkg = {
            "success": is_success,
            "roll_total": total,
            "roll_detail": f"{roll} (d20) + {int_mod} (INT)",
            "target_name": GameService.get_display_name(target_char),
            "actor_name": actor_char.name,
            "target_object": target_char
        }

        if is_success:
            # Update Identified Status (just update the model, StateService will persist)
            if any(n.id == target_char.id for n in game_state.npcs):
                 target_char.identified = True
            elif any(e.id == target_char.id for e in game_state.enemies):
                 target_char.identified = True

            await StateService.save_game_state(campaign_id, game_state, db)
            result_pkg["message"] = f"You study {GameService.get_display_name(target_char)} closely... It is {target_char.name}!"

        else:
            result_pkg["message"] = f"You glance at {GameService.get_display_name(target_char)} but cannot discern anything new."

        return result_pkg



    @staticmethod
    async def resolution_move(campaign_id: str, actor_name: str, direction: str, db: AsyncSession):
        game_state = await GameService.get_game_state(campaign_id, db)
        if not game_state:
            return {"success": False, "message": "No active game state."}

        interrupted, opp_msg, latest_state = await CombatService._handle_opportunity_attack(campaign_id, actor_name, "move", db, game_state)
        if interrupted:
            return {"success": False, "message": opp_msg, "game_state": latest_state}

        # Look up current location data
        from app.models import Location
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
        """
        Out of combat, AI party members attempt to stay within 3 hexes of the leader.
        They will move up to their speed.
        """
        import math

        if game_state.phase == 'combat':
            return
            
        leader = next((p for p in game_state.party if p.id == leader_id), None)
        if not leader or not leader.position:
            return

        # Helper for hex distance
        def hex_distance(q1, r1, s1, q2, r2, s2):
            return max(abs(q1 - q2), abs(r1 - r2), abs(s1 - s2))

        # Helper to get occupied hexes
        def get_obstacle_hexes():
            obstacles = set()
            for entity in [e for e in game_state.enemies if e.hp_current > 0] + game_state.npcs:
                if entity.position:
                    obstacles.add((entity.position.q, entity.position.r, entity.position.s))
            return obstacles
            
        def get_allied_hexes(ignore_id=None):
            allies = set()
            for entity in game_state.party:
                if entity.id != ignore_id and entity.position:
                    allies.add((entity.position.q, entity.position.r, entity.position.s))
            return allies

        walkable = {(h.q, h.r, h.s) for h in game_state.location.walkable_hexes}
        state_changed = False

        for member in game_state.party:
            if member.id == leader_id:
                continue
                
            # Only process AI or NPCs in party
            if not member.is_ai and member.control_mode != 'ai':
                continue
            if not member.position:
                continue

            dist = hex_distance(member.position.q, member.position.r, member.position.s, leader.position.q, leader.position.r, leader.position.s)
            
            # If they are further than 3 hexes away, they need to move
            if dist > 3:
                obstacles = get_obstacle_hexes()
                allies = get_allied_hexes(ignore_id=member.id)
                max_move = member.speed // 5 if member.speed else 6
                
                # BFS to find reachable hexes
                start_hex = (member.position.q, member.position.r, member.position.s)
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
                        if n in walkable and n not in obstacles:
                            if n not in visited or len(path) + 1 < len(visited[n]):
                                visited[n] = path + [n]
                                queue.append((n, path + [n]))
                                
                reachable_and_valid = [h for h in visited if h != start_hex and h not in allies]

                if reachable_and_valid:
                    # Sort reachable by distance to leader
                    reachable_and_valid.sort(key=lambda h: hex_distance(h[0], h[1], h[2], leader.position.q, leader.position.r, leader.position.s))
                    best_hex = reachable_and_valid[0]
                    new_dist_to_leader = hex_distance(best_hex[0], best_hex[1], best_hex[2], leader.position.q, leader.position.r, leader.position.s)
                    
                    if new_dist_to_leader < dist:
                        member.position.q = best_hex[0]
                        member.position.r = best_hex[1]
                        member.position.s = best_hex[2]
                        state_changed = True
                        path_found = visited[best_hex]
                        anim_path = [{"q": h[0], "r": h[1], "s": h[2]} for h in path_found]
                        if sio:
                            # Schedule emission for sync
                            asyncio.create_task(sio.emit('entity_path_animation', {'entity_id': member.id, 'path': anim_path}, room=campaign_id))

        if state_changed:
            await StateService.save_game_state(campaign_id, game_state, db)
            if sio:
                await StateService.emit_state_update(campaign_id, game_state, sio)

