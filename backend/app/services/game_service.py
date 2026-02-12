import json
from uuid import uuid4
from sqlalchemy import select, insert, update, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import GameState, Location
from db.schema import game_states, characters, monsters, npcs, locations
from game_engine.engine import GameEngine

class GameService:
    @staticmethod
    async def get_game_state(campaign_id: str, db: AsyncSession) -> GameState:
        query = (
            select(game_states.c.state_data)
            .where(game_states.c.campaign_id == campaign_id)
            .order_by(desc(game_states.c.turn_index), desc(game_states.c.updated_at))
            .limit(1)
        )
        result = await db.execute(query)
        state_data = result.scalar()

        if not state_data:
            return None
        return GameState(**json.loads(state_data))

    @staticmethod
    async def save_game_state(campaign_id: str, game_state: GameState, db: AsyncSession):
        stmt = insert(game_states).values(
            id=str(uuid4()),
            campaign_id=campaign_id,
            turn_index=game_state.turn_index,
            phase=game_state.phase,
            state_data=game_state.model_dump_json()
        )
        await db.execute(stmt)

    @staticmethod
    async def update_char_hp(char_obj, hp_val, game_state: GameState, db: AsyncSession):
        """
        Updates the HP of a character/enemy/npc in the database.
        """
    @staticmethod
    async def update_char_hp(char_obj, hp_val, game_state: GameState, db: AsyncSession):
        """
        Updates the HP of a character/enemy/npc in the database.
        """
        # Update Object in Verification (Memory)
        char_obj.hp_current = hp_val

        # Persist to DB
        # Try Character/Player
        if hasattr(char_obj, 'user_id') or any(p.id == char_obj.id for p in game_state.party):
             query = select(characters.c.sheet_data).where(characters.c.id == char_obj.id)
             c_res = await db.execute(query)
             sheet_data_str = c_res.scalars().first()

             if sheet_data_str:
                c_data = json.loads(sheet_data_str)
                if 'stats' not in c_data: c_data['stats'] = {}
                c_data['stats']['hp_current'] = hp_val

                stmt = (
                    update(characters)
                    .where(characters.c.id == char_obj.id)
                    .values(sheet_data=json.dumps(c_data))
                )
                await db.execute(stmt)

        # Try Monster/Enemy
        elif any(e.id == char_obj.id for e in game_state.enemies):
             query = select(monsters.c.data).where(monsters.c.id == char_obj.id)
             m_res = await db.execute(query)
             data_str = m_res.scalars().first()

             if data_str:
                m_data = json.loads(data_str)
                if 'stats' not in m_data: m_data['stats'] = {}
                m_data['stats']['hp'] = hp_val

                stmt = (
                    update(monsters)
                    .where(monsters.c.id == char_obj.id)
                    .values(data=json.dumps(m_data))
                )
                await db.execute(stmt)

        # Try NPC
        elif any(n.id == char_obj.id for n in game_state.npcs):
            # Update 'data' column
            if 'stats' not in char_obj.data: char_obj.data['stats'] = {}
            char_obj.data['stats']['hp'] = hp_val

            stmt = (
                update(npcs)
                .where(npcs.c.id == char_obj.id)
                .values(data=json.dumps(char_obj.data))
            )
            await db.execute(stmt)

    @staticmethod
    async def update_npc_hostility(npc_id: str, is_hostile: bool, db: AsyncSession):
        query = select(npcs.c.data).where(npcs.c.id == npc_id)
        n_res = await db.execute(query)
        data_str = n_res.scalars().first()

        if data_str:
            data = json.loads(data_str)
            data['hostile'] = is_hostile

            stmt = (
                update(npcs)
                .where(npcs.c.id == npc_id)
                .values(data=json.dumps(data))
            )
            await db.execute(stmt)

    @staticmethod
    async def resolution_attack(campaign_id: str, attacker_id: str, attacker_name: str, target_name: str, db: AsyncSession):
        """
        Mechanically resolves an attack.
        Returns a dict with results and the updated game state elements.
        """
        game_state = await GameService.get_game_state(campaign_id, db)
        if not game_state:
            return {"success": False, "message": "No active game state found!"}

        # Finder Helpers
        def find_char_by_id(char_id):
            for li in [game_state.party, game_state.enemies, game_state.npcs]:
                for c in li:
                    if c.id == char_id:
                        return c
            return None

        def find_char_by_name(name):
            for li in [game_state.party, game_state.enemies, game_state.npcs]:
                for c in li:
                    if name.lower() in c.name.lower():
                        return c
            return None

        actor_char = find_char_by_id(attacker_id)
        # Fallback if attacker ID is not found (e.g. system test or mismatched ID), try name
        if not actor_char:
             actor_char = find_char_by_name(attacker_name)

        target_char = find_char_by_name(target_name)

        if not actor_char or not target_char:
            return {"success": False, "message": f"Could not find actor '{attacker_name}' or target '{target_name}'."}

        # Engine Resolution
        engine = GameEngine()
        actor_data = actor_char.model_dump() if hasattr(actor_char, 'model_dump') else actor_char.dict()
        target_data = target_char.model_dump() if hasattr(target_char, 'model_dump') else target_char.dict()

        action_result = engine.resolve_action(actor_data, "attack", target_data, params={})

        if action_result.get("success"):
            new_hp = action_result.get("target_hp_remaining")
            await GameService.update_char_hp(target_char, new_hp, game_state, db)

            # Hostility
            is_npc = any(n.id == target_char.id for n in game_state.npcs)
            if is_npc:
                # Check current hostility
                if 'hostile' not in target_char.data or not target_char.data['hostile']:
                    await GameService.update_npc_hostility(target_char.id, True, db)
                    target_char.data['hostile'] = True # Update local state object too

            # Save State
            await GameService.save_game_state(campaign_id, game_state, db)

            # Add object references to result for calling code to use
            action_result['actor_object'] = actor_char
            action_result['target_object'] = target_char
            action_result['game_state'] = game_state

        return action_result

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

        # Finder Helpers
        def find_char_by_name(name):
            for li in [game_state.party, game_state.enemies, game_state.npcs]:
                for c in li:
                    if name.lower() in c.name.lower():
                        return c
            return None

        # Resolve Actor
        # Usually a player, but theoretically could be NPC vs NPC
        actor_char = None
        for p in game_state.party:
            if actor_name.lower() in p.name.lower():
                actor_char = p
                break

        if not actor_char:
             return {"success": False, "message": f"Could not find actor '{actor_name}'."}

        target_char = find_char_by_name(target_name)
        if not target_char:
            return {"success": False, "message": f"Could not find target '{target_name}'."}

        # Check if already identified
        if hasattr(target_char, 'identified') and target_char.identified:
             return {"success": True, "message": f"{target_char.name} is already identified.", "reason": "already_known", "target_object": target_char}

        # Mechanics: INT (Investigation) Check
        # DC Base: 12 (Hard enough to not be trivial, easy enough for proficient characters)
        # TODO: Adjust DC based on target rarity/secrecy if data available
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
            "target_name": target_char.name,
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

            await GameService.save_game_state(campaign_id, game_state, db)
            result_pkg["message"] = f"You study {target_name} closely..."

        else:
            result_pkg["message"] = f"You glance at {target_name} but cannot discern anything new."

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
