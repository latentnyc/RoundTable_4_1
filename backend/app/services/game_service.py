import json
import asyncio
import functools
from uuid import uuid4
from sqlalchemy import select, insert, update, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import GameState, Location
from db.schema import game_states, characters, monsters, npcs, locations
from game_engine.engine import GameEngine

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
    def generate_loot(entity) -> list[str]:
        """
        Generates a list of item IDs based on the entity's loot table.
        """
        import random
        
        loot_items = []
        
        # Access loot data
        loot_data = None
        if hasattr(entity, 'loot') and entity.loot:
            loot_data = entity.loot
        elif hasattr(entity, 'data') and entity.data:
            loot_data = entity.data.get('loot')
            
        if not loot_data:
            return []
            
        # 1. Guaranteed Items
        guaranteed = loot_data.get('guaranteed', [])
        loot_items.extend(guaranteed)
        
        # 2. Random Items
        random_drops = loot_data.get('random', [])
        for drop in random_drops:
            chance = drop.get('chance', 0.0)
            if random.random() < chance:
                item_id = drop.get('item_id')
                if item_id:
                    loot_items.append(item_id)
        
        return loot_items

    @staticmethod
    async def get_game_state(campaign_id: str, db: AsyncSession) -> GameState:
        # Import models locally to avoid circular imports if any
        from app.models import Player, Enemy, NPC
        
        query = (
            select(game_states.c.state_data)
            .where(game_states.c.campaign_id == campaign_id)
            .order_by(desc(game_states.c.updated_at), desc(game_states.c.id))
            .limit(1)
        )
        result = await db.execute(query)
        state_data_str = result.scalar()

        if not state_data_str:
            return None
        
        state_data = json.loads(state_data_str)
        
        # HYDRATION LOGIC
        # Check if 'party' is list of strings (IDs) -> Lightweight Mode
        # If list of dicts -> Old/Monolithic Mode
        
        if state_data.get('party') and isinstance(state_data['party'][0], str):
            # 1. Hydrate Party
            party_ids = state_data['party']
            party_objs = []
            if party_ids:
                q = select(characters).where(characters.c.id.in_(party_ids))
                rows = (await db.execute(q)).fetchall()
                # Rows to objects
                # Need to merge sheet_data with columns?
                # Actually usage is mostly sheet_data.
                # Player model expects fields.
                start_map = {r.id: r for r in rows}
                # Preserve order from IDs list
                for pid in party_ids:
                    if pid in start_map:
                        r = start_map[pid]
                        # r.sheet_data is string
                        s_data = json.loads(r.sheet_data)
                        # Ensure ID/Name/etc match
                        # Merge DB columns into data for Model init
                        s_data['id'] = r.id
                        s_data['name'] = r.name
                        s_data['role'] = r.role
                        # s_data might have 'hp_current' from save
                        party_objs.append(Player(**s_data))
            state_data['party'] = party_objs

            # 2. Hydrate Enemies
            enemy_ids = state_data.get('enemies', [])
            enemy_objs = []
            if enemy_ids:
                q = select(monsters).where(monsters.c.id.in_(enemy_ids))
                rows = (await db.execute(q)).fetchall()
                row_map = {r.id: r for r in rows}
                for eid in enemy_ids:
                    if eid in row_map:
                        r = row_map[eid]
                        d = json.loads(r.data)
                        
                        # Prepare init dict
                        # Start with the data blob as the 'data' field
                        init_d = {'data': d}
                        
                        # Override/Ensure top-level fields match DB columns
                        init_d['id'] = r.id
                        init_d['name'] = r.name
                        init_d['type'] = r.type
                        
                        # Extract promoted fields from data if they exist to satisfy Pydantic
                        # (Because 'hp_current' is required by Entity, and we saved it in data)
                        if 'hp_current' in d: init_d['hp_current'] = d['hp_current']
                        if 'hp_max' in d: init_d['hp_max'] = d['hp_max']
                        if 'is_ai' in d: init_d['is_ai'] = d['is_ai']
                        if 'position' in d: init_d['position'] = d['position']
                        
                        enemy_objs.append(Enemy(**init_d))
            state_data['enemies'] = enemy_objs

            # 3. Hydrate NPCs
            npc_ids = state_data.get('npcs', [])
            npc_objs = []
            if npc_ids:
                q = select(npcs).where(npcs.c.id.in_(npc_ids))
                rows = (await db.execute(q)).fetchall()
                row_map = {r.id: r for r in rows}
                for nid in npc_ids:
                    if nid in row_map:
                        r = row_map[nid]
                        d = json.loads(r.data)
                        
                        init_d = {'data': d}
                        init_d['id'] = r.id
                        init_d['name'] = r.name
                        init_d['role'] = r.role
                        
                        if 'hp_current' in d: init_d['hp_current'] = d['hp_current']
                        if 'hp_max' in d: init_d['hp_max'] = d['hp_max']
                        if 'is_ai' in d: init_d['is_ai'] = d['is_ai']
                        if 'position' in d: init_d['position'] = d['position']
                        
                        if not r.role and 'role' in d: init_d['role'] = d['role']
                        
                        npc_objs.append(NPC(**init_d))
            state_data['npcs'] = npc_objs
            
        return GameState(**state_data)

    @staticmethod
    async def save_game_state(campaign_id: str, game_state: GameState, db: AsyncSession):
        from datetime import datetime, timezone
        from sqlalchemy import bindparam
        
        # 1. Update Entities in their specific tables (Batched)
        
        # --- PARTY ---
        if game_state.party:
            party_ids = [p.id for p in game_state.party]
            existing_pids = (await db.scalars(select(characters.c.id).where(characters.c.id.in_(party_ids)))).all()
            existing_pid_set = set(existing_pids)
            
            p_updates = []
            p_inserts = []
            
            for p in game_state.party:
                if not p.sheet_data: p.sheet_data = {}
                # Sync transient fields
                p.sheet_data['hp_current'] = p.hp_current
                p.sheet_data['hp_max'] = p.hp_max
                p.sheet_data['position'] = p.position.model_dump()
                p.sheet_data['is_ai'] = p.is_ai
                p.sheet_data['control_mode'] = p.control_mode
                
                record = {
                    "b_id": p.id,
                    "b_sheet_data": json.dumps(p.sheet_data)
                }
                
                if p.id in existing_pid_set:
                    p_updates.append(record)
                else:
                    # Full insert record - use normal keys for insert
                    insert_rec = {
                        "id": p.id,
                        "sheet_data": json.dumps(p.sheet_data),
                        "user_id": p.user_id if p.user_id else "system",
                        "campaign_id": campaign_id,
                        "name": p.name,
                        "role": p.role,
                        "control_mode": p.control_mode
                    }
                    p_inserts.append(insert_rec)
            
            if p_updates:
                stmt = update(characters).\
                    where(characters.c.id == bindparam('b_id')).\
                    values(sheet_data=bindparam('b_sheet_data'))
                await db.execute(stmt, p_updates)

            if p_inserts:
                await db.execute(insert(characters), p_inserts)

        # --- ENEMIES ---
        if game_state.enemies:
            enemy_ids = [e.id for e in game_state.enemies]
            existing_eids = (await db.scalars(select(monsters.c.id).where(monsters.c.id.in_(enemy_ids)))).all()
            existing_eid_set = set(existing_eids)
            
            e_updates = []
            e_inserts = []
            
            for e in game_state.enemies:
                e_data = e.model_dump()
                record = {
                    "b_id": e.id,
                    "b_data": json.dumps(e_data)
                }
                
                if e.id in existing_eid_set:
                    e_updates.append(record)
                else:
                    insert_rec = {
                        "id": e.id,
                        "data": json.dumps(e_data),
                        "campaign_id": campaign_id,
                        "name": e.name,
                        "type": e.type
                    }
                    e_inserts.append(insert_rec)

            if e_updates:
                stmt = update(monsters).\
                    where(monsters.c.id == bindparam('b_id')).\
                    values(data=bindparam('b_data'))
                await db.execute(stmt, e_updates)

            if e_inserts:
                await db.execute(insert(monsters), e_inserts)

        # --- NPCs ---
        if game_state.npcs:
            npc_ids = [n.id for n in game_state.npcs]
            existing_nids = (await db.scalars(select(npcs.c.id).where(npcs.c.id.in_(npc_ids)))).all()
            existing_nid_set = set(existing_nids)
            
            n_updates = []
            n_inserts = []
            
            for n in game_state.npcs:
                if not n.data: n.data = {}
                n.data['hp_current'] = n.hp_current
                n.data['hp_max'] = n.hp_max
                n.data['position'] = n.position.model_dump()
                n.data['identified'] = n.identified
                n.data['is_ai'] = n.is_ai
                
                record = {
                    "b_id": n.id,
                    "b_data": json.dumps(n.data)
                }
                
                if n.id in existing_nid_set:
                    n_updates.append(record)
                else:
                    insert_rec = {
                        "id": n.id,
                        "data": json.dumps(n.data),
                        "campaign_id": campaign_id,
                        "name": n.name,
                        "role": n.role
                    }
                    n_inserts.append(insert_rec)
            
            if n_updates:
                stmt = update(npcs).\
                    where(npcs.c.id == bindparam('b_id')).\
                    values(data=bindparam('b_data'))
                await db.execute(stmt, n_updates)

            if n_inserts:
                await db.execute(insert(npcs), n_inserts)

        # 2. Save Lightweight GameState (Skeleton)
        state_dict = game_state.model_dump()
        state_dict['party'] = [p.id for p in game_state.party]
        state_dict['enemies'] = [e.id for e in game_state.enemies]
        state_dict['npcs'] = [n.id for n in game_state.npcs]
        
        stmt = insert(game_states).values(
            id=str(uuid4()),
            campaign_id=campaign_id,
            turn_index=game_state.turn_index,
            phase=game_state.phase,
            state_data=json.dumps(state_dict),
            updated_at=datetime.now(timezone.utc)
        )
        await db.execute(stmt)

    @staticmethod
    async def update_char_hp(char_obj, hp_val, game_state: GameState, db: AsyncSession):
        """
        Updates the HP of a character/enemy/npc in the database.
        """
    @staticmethod
    async def update_char_hp(char_obj, hp_val, game_state: GameState, db: AsyncSession, commit: bool = True):
        """
        Updates the HP of a character/enemy/npc in the database.
        """
        # Update Object in Verification (Memory)
        # Update Object in Verification (Memory)
        char_obj.hp_current = hp_val
        
        if commit:
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
    async def update_npc_hostility(npc_id: str, is_hostile: bool, db: AsyncSession, commit: bool = True):
        if commit:
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
    async def start_combat(campaign_id: str, db: AsyncSession):
        """
        Initiates combat:
        1. Rolls initiative for all entities.
        2. Sorts turn order.
        3. Sets phase to 'combat'.
        4. Sets active entity.
        5. Returns the updated game state including the new turn order.
        """
        import random
        
        # We need to lock this transaction or check specifically for race conditions.
        # Ideally, we'd use select for update, but SQLite doesn't support it fully in the same way.
        # Instead, we rely on the check below.
        
        game_state = await GameService.get_game_state(campaign_id, db)
        if not game_state:
            return {"success": False, "message": "No active game state found!"}
        
        # Race Condition Fix: Double Check Phase
        if game_state.phase == 'combat':
            return {"success": False, "message": "Combat already in progress.", "game_state": game_state}

        # Helper to get Dex Mod
        def get_dex_mod(entity):
            # Try Player sheet_data
            if hasattr(entity, 'sheet_data'):
                stats = entity.sheet_data.get('stats', {})
                dex = int(stats.get('dexterity', 10) or 10)
                return (dex - 10) // 2
            
            # Try Enemy/NPC data
            if hasattr(entity, 'data'):
                stats = entity.data.get('stats', {})
                # Some monsters might have 'dex' or 'dexterity'
                dex = int(stats.get('dexterity', stats.get('dex', 10)) or 10)
                return (dex - 10) // 2
            
            return 0

        # Roll Initiative
        combatants = []
        
        # 1. Party
        for p in game_state.party:
            roll = random.randint(1, 20)
            mod = get_dex_mod(p)
            total = roll + mod
            p.initiative = total
            combatants.append(p)

        # 2. Enemies
        for e in game_state.enemies:
            roll = random.randint(1, 20)
            mod = get_dex_mod(e)
            total = roll + mod
            e.initiative = total
            combatants.append(e)

        # 3. NPCs
        for n in game_state.npcs:
            roll = random.randint(1, 20)
            mod = get_dex_mod(n)
            total = roll + mod
            n.initiative = total
            combatants.append(n)

        # Sort Logic: Total Descending
        combatants.sort(key=lambda x: x.initiative, reverse=True)
        
        game_state.turn_order = [c.id for c in combatants]
        game_state.phase = 'combat'
        game_state.turn_index = 0
        if game_state.turn_order:
            game_state.active_entity_id = game_state.turn_order[0]
            
        await GameService.save_game_state(campaign_id, game_state, db)
        
        return {
            "success": True, 
            "message": "Combat Started!", 
            "turn_order": game_state.turn_order,
            "active_entity_id": game_state.active_entity_id,
            "game_state": game_state
        }

    @staticmethod
    async def next_turn(campaign_id: str, db: AsyncSession, current_game_state=None, commit: bool = True):
        """
        Advances to the next turn.
        Returns the new active entity ID and the GameState.
        """
        game_state = current_game_state
        if not game_state:
            game_state = await GameService.get_game_state(campaign_id, db)

        if not game_state or not game_state.turn_order:
            return None, None

        # Advance Index
        current_idx = game_state.turn_index
        next_idx = (current_idx + 1) % len(game_state.turn_order)
        
        game_state.turn_index = next_idx
        game_state.active_entity_id = game_state.turn_order[next_idx]
        
        if commit:
            await GameService.save_game_state(campaign_id, game_state, db)
        
        return game_state.active_entity_id, game_state

    @staticmethod
    async def resolution_attack(campaign_id: str, attacker_id: str, attacker_name: str, target_name: str, db: AsyncSession, current_state=None, commit: bool = True):
        """
        Mechanically resolves an attack.
        Returns a dict with results and the updated game state elements.
        """
        game_state = current_state
        if not game_state:
            game_state = await GameService.get_game_state(campaign_id, db)
        if not game_state:
            return {"success": False, "message": "No active game state found!"}


        actor_char = GameService._find_char_by_name(game_state, attacker_id)
        # Fallback if attacker ID is not found (e.g. system test or mismatched ID), try name
        if not actor_char:
             actor_char = GameService._find_char_by_name(game_state, attacker_name)

        target_char = GameService._find_char_by_name(game_state, target_name)

        if not actor_char or not target_char:
            return {"success": False, "message": f"Could not find actor '{attacker_name}' or target '{target_name}'."}

        # Engine Resolution
        engine = GameEngine()
        actor_data = actor_char.model_dump() if hasattr(actor_char, 'model_dump') else actor_char.dict()
        target_data = target_char.model_dump() if hasattr(target_char, 'model_dump') else target_char.dict()

        # Run synchronous engine logic in a thread pool to avoid blocking the event loop
        loop = asyncio.get_running_loop()
        action_result = await loop.run_in_executor(
            None, 
            functools.partial(
                GameService._run_engine_resolution, 
                engine, 
                actor_data, 
                "attack", 
                target_data, 
                {}
            )
        )

        if action_result.get("success"):
            new_hp = action_result.get("target_hp_remaining")
            await GameService.update_char_hp(target_char, new_hp, game_state, db, commit=commit)

            # Hostility
            is_npc = any(n.id == target_char.id for n in game_state.npcs)
            if is_npc:
                # Check current hostility
                if 'hostile' not in target_char.data or not target_char.data['hostile']:
                    await GameService.update_npc_hostility(target_char.id, True, db, commit=commit)
                    target_char.data['hostile'] = True # Update local state object too

            # Barks
            bark_msg = None
            if new_hp > 0:
                # Aggro Bark
                bark = GameService.get_bark(target_char, 'aggro')
                if bark:
                    bark_msg = f"{GameService.get_display_name(target_char)} shouts: \"{bark}\""
            else:
                # Death Bark
                bark = GameService.get_bark(target_char, 'death')
                if bark:
                    bark_msg = f"{GameService.get_display_name(target_char)} gasps: \"{bark}\""

            # Loot on Death
            loot_drops = []
            if new_hp <= 0:
                drops = GameService.generate_loot(target_char)
                if drops:
                    loot_drops = drops
                    # Logic to add to location or killer would go here
                    # For now, just logging it in the result for the frontend/narrator
                    action_result['loot_dropped'] = loot_drops

            # Save State
            if commit:
                await GameService.save_game_state(campaign_id, game_state, db)

            # Add object references to result for calling code to use
            action_result['actor_object'] = actor_char
            action_result['target_object'] = target_char
            action_result['game_state'] = game_state
            if bark_msg:
                action_result['bark'] = bark_msg

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

            await GameService.save_game_state(campaign_id, game_state, db)
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
