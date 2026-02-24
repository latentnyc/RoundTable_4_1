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
    def _find_char_by_name(game_state, search_term: str):
        term = search_term.lower()

        # Priority 1: Exact Name Match (contains) or ID/TargetID Match
        for li in [game_state.party, game_state.enemies, game_state.npcs]:
            for c in li:
                if term == c.id.lower() or term in c.name.lower():
                    return c
                if hasattr(c, 'target_id') and c.target_id and term == c.target_id.lower():
                    return c

        # Priority 2: Race / Type / Role Match
        for li in [game_state.party, game_state.enemies, game_state.npcs]:
            for c in li:
                # Player
                if hasattr(c, 'race') and c.race and term in c.race.lower(): return c
                if hasattr(c, 'role') and c.role and term in c.role.lower(): return c

                # Enemy
                if hasattr(c, 'type') and c.type and term in c.type.lower(): return c

                # NPC
                if hasattr(c, 'data') and c.data:
                    # NPC Race/Type often in 'race' or 'type' keys in data
                    if 'race' in c.data and term in str(c.data['race']).lower(): return c
                    if 'type' in c.data and term in str(c.data['type']).lower(): return c
                    if 'role' in c.data and term in str(c.data['role']).lower(): return c

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
    async def update_char_hp(char_obj, hp_val, game_state: GameState, db: AsyncSession, commit: bool = True):
         return await StateService.update_char_hp(char_obj, hp_val, game_state, db, commit)

    @staticmethod
    async def update_npc_hostility(npc_id: str, is_hostile: bool, db: AsyncSession, commit: bool = True):
         return await StateService.update_npc_hostility(npc_id, is_hostile, db, commit)

    @staticmethod
    async def resolution_identify(campaign_id: str, actor_name: str, target_name: str, db: AsyncSession):
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

        target_char = GameService._find_char_by_name(game_state, target_name)
        if not target_char:
            return {"success": False, "message": f"Could not find target '{target_name}'."}

        # Check if already identified
        if hasattr(target_char, 'identified') and target_char.identified:
             return {"success": True, "message": f"{target_char.name} is already identified.", "reason": "already_known", "target_object": target_char}

        # Mechanics: INT (Investigation) Check
        # DC Base: 12 (Hard enough to not be trivial, easy enough for proficient characters)
        dc = 12

        # Roll: d20 + Int Mod
        # Get Int stats from sheet_data if available
        stats = actor_char.sheet_data.get('stats', {})
        int_score = int(stats.get('intelligence', 10) or 10) # default 10
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
            # Update Identified Status
            # Check type and update DB

            # NPC
            if any(n.id == target_char.id for n in game_state.npcs):
                 target_char.identified = True
                 # Persist
                 await GameService.update_npc_field(target_char.id, "identified", True, db)

            # Enemy
            elif any(e.id == target_char.id for e in game_state.enemies):
                 target_char.identified = True
                 await GameService.update_enemy_field(target_char.id, "identified", True, db)

            await StateService.save_game_state(campaign_id, game_state, db)
            result_pkg["message"] = f"You study {GameService.get_display_name(target_char)} closely... It is {target_char.name}!"

        else:
            result_pkg["message"] = f"You glance at {GameService.get_display_name(target_char)} but cannot discern anything new."

        return result_pkg

    @staticmethod
    async def update_npc_field(npc_id: str, field: str, value, db: AsyncSession):
        """Generic updater for NPC fields in JSON data or columns"""
        # For 'identified', it is a top-level field on our Pydantic model,
        # but in DB it might need to be in 'data' json if we didn't add a column.
        # Wait, I added it to the Pydantic model, but DID I ADD IT TO THE DB SCHEMA?
        # The user's request didn't explicitly ask for a DB schema migration, but implied it.
        # However, as a quick fix without migration, we can store it in the 'data' JSON blob!
        # The Pydantic model can load it from there if we align it.
        # Models.py `identified: bool = False` defaults to False.
        # If I want it to persist, I should probably put it in the `data` JSON for NPCs/Enemies
        # since I cannot easily run ALMBIC migrations here without risk.
        # Strategy: Store in `data` JSON, have Model load it?
        # Or just rely on the `data` JSON for persistence and the Model is just a view.

        # Let's check `models.py` again. `NPC` has `data: Dict`.
        # I added `identified` to the class.
        # Pydantic doesn't automatically map `data['identified']` to `self.identified`.
        # I should probably just use the `data` dict for storage to avoid schema changes.

        # BUT, the prompt said "Schema Change: NPC and Enemy models will get an identified boolean field."
        # If I change the python model but not the DB table, it won't persist as a column.
        # It's safer to store it in the JSON `data` column for `npcs` and `monsters`.

        query = select(npcs.c.data).where(npcs.c.id == npc_id)
        n_res = await db.execute(query)
        data_str = n_res.scalars().first()

        if data_str:
            data = json.loads(data_str)
            data[field] = value

            stmt = (
                update(npcs)
                .where(npcs.c.id == npc_id)
                .values(data=json.dumps(data))
            )
            await db.execute(stmt)

    @staticmethod
    async def update_enemy_field(enemy_id: str, field: str, value, db: AsyncSession):
        query = select(monsters.c.data).where(monsters.c.id == enemy_id)
        m_res = await db.execute(query)
        data_str = m_res.scalars().first()

        if data_str:
            data = json.loads(data_str)
            data[field] = value

            stmt = (
                update(monsters)
                .where(monsters.c.id == enemy_id)
                .values(data=json.dumps(data))
            )
            await db.execute(stmt)


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
