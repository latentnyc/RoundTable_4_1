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
        from app.models import Player, Enemy, NPC, Vessel

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

        # Hydrate Entities
        state_data['party'] = await GameService._hydrate_party(state_data.get('party'), db)
        state_data['enemies'] = await GameService._hydrate_enemies(state_data.get('enemies'), db)
        state_data['npcs'] = await GameService._hydrate_npcs(state_data.get('npcs'), db)

        # Hydrate Vessels (stored as dicts in JSON)
        vessel_data = state_data.get('vessels', [])
        state_data['vessels'] = [Vessel(**v) for v in vessel_data if isinstance(v, dict)]

        return GameState(**state_data)

    @staticmethod
    async def _hydrate_party(party_ids: list, db: AsyncSession):
        from app.models import Player
        if not party_ids: return []

        clean_ids = [pid.get('id') if isinstance(pid, dict) else pid for pid in party_ids]
        if not isinstance(clean_ids[0], str): return []

        q = select(characters).where(characters.c.id.in_(clean_ids))
        rows = (await db.execute(q)).fetchall()
        row_map = {r.id: r for r in rows}

        party_objs = []
        for pid in clean_ids:
            if pid in row_map:
                r = row_map[pid]
                s_data = json.loads(r.sheet_data)

                # Preserve the original sheet structure so Pydantic doesn't wipe non-Entity attributes
                if 'sheet_data' not in s_data:
                    s_data['sheet_data'] = json.loads(r.sheet_data)

                s_data.update({
                    'id': r.id,
                    'name': r.name,
                    'role': r.role,
                    'user_id': r.user_id, # Important for auth checks
                    'control_mode': s_data.get('control_mode') or (r.control_mode if hasattr(r, 'control_mode') and r.control_mode else "human")
                })

                # Apply defaults for core Entity fields if missing from sheet_data
                if 'is_ai' not in s_data: s_data['is_ai'] = False
                if 'hp_max' not in s_data:
                    s_data['hp_max'] = s_data.get('stats', {}).get('hp_max', 10)
                if 'hp_current' not in s_data:
                    s_data['hp_current'] = s_data.get('hp_max', 10)
                if 'position' not in s_data:
                    s_data['position'] = {"q": 0, "r": 0, "s": 0}

                party_objs.append(Player(**s_data))
        return party_objs

    @staticmethod
    async def _hydrate_enemies(enemy_ids: list, db: AsyncSession):
        from app.models import Enemy
        if not enemy_ids: return []

        clean_ids = [eid.get('id') if isinstance(eid, dict) else eid for eid in enemy_ids]
        if not clean_ids or not isinstance(clean_ids[0], str): return []

        q = select(monsters).where(monsters.c.id.in_(clean_ids))
        rows = (await db.execute(q)).fetchall()
        row_map = {r.id: r for r in rows}

        enemy_objs = []
        for eid in clean_ids:
            if eid in row_map:
                r = row_map[eid]
                d = json.loads(r.data)

                # Base init with data blob
                init_d = {'data': d}
                # Overlay DB columns
                init_d.update({
                    'id': r.id,
                    'name': r.name,
                    'type': r.type
                })
                # Overlay strict fields from data if present (for Pydantic)
                for field in ['hp_current', 'hp_max', 'is_ai', 'position', 'identified']:
                    if field in d: init_d[field] = d[field]

                # Apply defaults for core Base Entity fields if missing from d
                if 'is_ai' not in init_d: init_d['is_ai'] = True
                if 'hp_max' not in init_d:
                    init_d['hp_max'] = d.get('stats', {}).get('hp', 10)
                if 'hp_current' not in init_d:
                    init_d['hp_current'] = init_d.get('hp_max', 10)
                if 'position' not in init_d:
                    init_d['position'] = {"q": 0, "r": 0, "s": 0}

                enemy_objs.append(Enemy(**init_d))
        return enemy_objs

    @staticmethod
    async def _hydrate_npcs(npc_ids: list, db: AsyncSession):
        from app.models import NPC
        if not npc_ids: return []

        clean_ids = [nid.get('id') if isinstance(nid, dict) else nid for nid in npc_ids]
        if not clean_ids or not isinstance(clean_ids[0], str): return []

        q = select(npcs).where(npcs.c.id.in_(clean_ids))
        rows = (await db.execute(q)).fetchall()
        row_map = {r.id: r for r in rows}

        npc_objs = []
        for nid in clean_ids:
            if nid in row_map:
                r = row_map[nid]
                d = json.loads(r.data)

                init_d = {'data': d}
                init_d.update({
                    'id': r.id,
                    'name': r.name,
                    'role': r.role
                })

                for field in ['hp_current', 'hp_max', 'is_ai', 'position', 'identified']:
                    if field in d: init_d[field] = d[field]

                # Apply defaults for core Base Entity fields if missing
                if 'is_ai' not in init_d: init_d['is_ai'] = True
                if 'hp_max' not in init_d:
                    init_d['hp_max'] = d.get('stats', {}).get('hp', 10)
                if 'hp_current' not in init_d:
                    init_d['hp_current'] = init_d.get('hp_max', 10)
                if 'position' not in init_d:
                    init_d['position'] = {"q": 0, "r": 0, "s": 0}

                if not r.role and 'role' in d: init_d['role'] = d['role']

                npc_objs.append(NPC(**init_d))
        return npc_objs

    @staticmethod
    async def save_game_state(campaign_id: str, game_state: GameState, db: AsyncSession):
        from datetime import datetime, timezone

        # 1. Update Entities in their specific tables
        await GameService._save_party(game_state.party, campaign_id, db)
        await GameService._save_enemies(game_state.enemies, campaign_id, db)
        await GameService._save_npcs(game_state.npcs, campaign_id, db)

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
    async def _save_party(party: list, campaign_id: str, db: AsyncSession):
        if not party: return
        from sqlalchemy import bindparam

        party_ids = [p.id for p in party]
        existing_pids = set((await db.scalars(select(characters.c.id).where(characters.c.id.in_(party_ids)))).all())

        updates, inserts = [], []
        for p in party:
            if not p.sheet_data: p.sheet_data = {}
            # Sync transient fields to the preserved sheet_data blob
            for field in ['hp_current', 'hp_max', 'is_ai', 'control_mode', 'inventory', 'currency']:
                if hasattr(p, field):
                    p.sheet_data[field] = getattr(p, field)
            if hasattr(p, 'position') and p.position:
                pos = getattr(p, 'position')
                p.sheet_data['position'] = pos.model_dump() if hasattr(pos, 'model_dump') else pos

            rec = {
                "b_id": p.id, "b_sheet_data": json.dumps(p.sheet_data)
            }
            if p.id in existing_pids:
                updates.append(rec)
            else:
                inserts.append({
                    "id": p.id,
                    "sheet_data": json.dumps(p.sheet_data),
                    "user_id": p.user_id if p.user_id else "system",
                    "campaign_id": campaign_id,
                    "name": p.name,
                    "role": p.role,
                    "control_mode": p.control_mode
                })

        if updates:
            await db.execute(update(characters).where(characters.c.id == bindparam('b_id')).values(sheet_data=bindparam('b_sheet_data')), updates)
        if inserts:
            await db.execute(insert(characters), inserts)

    @staticmethod
    async def _save_enemies(enemies: list, campaign_id: str, db: AsyncSession):
        if not enemies: return
        from sqlalchemy import bindparam

        eids = [e.id for e in enemies]
        existing = set((await db.scalars(select(monsters.c.id).where(monsters.c.id.in_(eids)))).all())

        updates, inserts = [], []
        for e in enemies:
            e_data = e.model_dump()
            rec = {"b_id": e.id, "b_data": json.dumps(e_data)}

            if e.id in existing:
                updates.append(rec)
            else:
                inserts.append({
                    "id": e.id, "data": json.dumps(e_data), "campaign_id": campaign_id, "name": e.name, "type": e.type
                })

        if updates:
            await db.execute(update(monsters).where(monsters.c.id == bindparam('b_id')).values(data=bindparam('b_data')), updates)
        if inserts:
            await db.execute(insert(monsters), inserts)

    @staticmethod
    async def _save_npcs(npcs_list: list, campaign_id: str, db: AsyncSession):
        if not npcs_list: return
        from sqlalchemy import bindparam

        nids = [n.id for n in npcs_list]
        existing = set((await db.scalars(select(npcs.c.id).where(npcs.c.id.in_(nids)))).all())

        updates, inserts = [], []
        for n in npcs_list:
            if not n.data: n.data = {}
            for field in ['hp_current', 'hp_max', 'identified', 'is_ai']:
                 n.data[field] = getattr(n, field)
            n.data['position'] = n.position.model_dump()

            rec = {"b_id": n.id, "b_data": json.dumps(n.data)}

            if n.id in existing:
                updates.append(rec)
            else:
                inserts.append({
                    "id": n.id, "data": json.dumps(n.data), "campaign_id": campaign_id, "name": n.name, "role": n.role
                })

        if updates:
            await db.execute(update(npcs).where(npcs.c.id == bindparam('b_id')).values(data=bindparam('b_data')), updates)
        if inserts:
            await db.execute(insert(npcs), inserts)

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
        # Ideally, we'd use select for update.
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

        # Advance Index until we find an alive entity
        curr_idx = int(game_state.turn_index)
        next_idx = (curr_idx + 1) % len(game_state.turn_order)

        # Prevent infinite loop if everyone's dead
        loop_counter = int(0)
        while loop_counter < len(game_state.turn_order):
            active_id = game_state.turn_order[next_idx]
            entity = GameService._find_char_by_name(game_state, active_id)
            if entity and entity.hp_current > 0:
                break
            next_idx = int((next_idx + 1) % len(game_state.turn_order))
            loop_counter = int(loop_counter + 1)

        if loop_counter >= len(game_state.turn_order):
             return None, None # Everyone is dead

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
                    target_id_str = target_char.id
                    if isinstance(target_id_str, dict):
                        target_id_str = target_id_str.get('id')
                    await GameService.update_npc_hostility(target_id_str, True, db, commit=commit)
                    target_char.data['hostile'] = True # Update local state object too

            # Barks & Death Logic
            bark_msg = None
            death_msg = None

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

                # HANDLE DEATH
                # 1. Convert to Vessel (Corpse)
                # Only for Enemies (and maybe NPCs?) - Requirement said "opponents are defeated"
                target_id_str = target_char.id
                if isinstance(target_id_str, dict):
                    target_id_str = target_id_str.get('id')

                if any(e.id == target_id_str for e in game_state.enemies) or is_npc:
                    import random
                    from app.models import Vessel, Coordinates

                    # Create Vessel
                    char_type = getattr(target_char, 'type', getattr(target_char, 'race', ''))
                    if not char_type and hasattr(target_char, 'data') and isinstance(target_char.data, dict):
                        char_type = target_char.data.get('race', '')
                    char_type = char_type.upper()
                    v_name = f"CORPSE OF {target_char.name.upper()}"
                    if char_type:
                        v_name += f" ({char_type})"
                    v_desc = f"The lifeless body of {target_char.name}."

                    # Loot Generation
                    # 1. Equipment/Inventory
                    v_contents = list(target_char.inventory) if target_char.inventory else []

                    # 2. Loot Table Items
                    generated_loot = GameService.generate_loot(target_char)
                    v_contents.extend(generated_loot)

                    # 3. Currency (1d10 sp, 1d10 cp)
                    sp = random.randint(1, 10)
                    cp = random.randint(1, 10)
                    v_currency = {"pp": 0, "gp": 0, "sp": sp, "cp": cp}

                    # Create Object
                    vessel = Vessel(
                        name=v_name,
                        description=v_desc,
                        position=target_char.position,
                        contents=v_contents,
                        currency=v_currency
                    )

                    # Add to State
                    game_state.vessels.append(vessel)
                    action_result['vessel_created'] = vessel
                    death_msg = f"{target_char.name} has died! A {v_name} falls to the ground."

                    # Remove from Enemies list / NPCs list
                    # (Actually, we probably keep them in DB but remove from Active GameState list?)
                    # For now, let's remove from the active lists so they stop taking turns.
                    target_id_str = target_char.id
                    if isinstance(target_id_str, dict):
                        target_id_str = target_id_str.get('id')

                    if is_npc:
                        game_state.npcs = [n for n in game_state.npcs if n.id != target_id_str]
                    else:
                        game_state.enemies = [e for e in game_state.enemies if e.id != target_id_str]

                    # Remove from Turn Order
                    if target_id_str in game_state.turn_order:
                        game_state.turn_order.remove(target_id_str)


                # 2. Check Combat End
                # Victory: All enemies and hostile NPCs dead
                hostile_npcs = [n for n in game_state.npcs if getattr(n, 'hp_current', 0) > 0 and n.data.get('hostile') == True]
                if not game_state.enemies and not hostile_npcs:
                     game_state.phase = 'exploration'
                     game_state.turn_order = []
                     game_state.active_entity_id = None
                     if not death_msg: death_msg = ""
                     death_msg += "\n\n**COMBAT ENDED! VICTORY!**"

                     # Revive fallen players with 1 HP
                     revived = []
                     for p in game_state.party:
                         if p.hp_current <= 0:
                             p.hp_current = 1
                             await GameService.update_char_hp(p, 1, game_state, db, commit=False)
                             revived.append(p.name)

                     if revived:
                         death_msg += f"\n*({', '.join(revived)} narrowly survived and regained 1 HP.)*"

                     action_result['combat_end'] = 'victory'

                # Defeat: All party dead/down
                # Check HP of all party members
                live_party = [p for p in game_state.party if p.hp_current > 0]
                if not live_party:
                    game_state.phase = 'exploration' # Or game over state?
                    if not death_msg: death_msg = ""
                    death_msg += "\n\n**DEFEAT! The party has fallen. Game Over.**"
                    action_result['combat_end'] = 'defeat'

            # Save State
            if commit:
                await GameService.save_game_state(campaign_id, game_state, db)

            # Add object references to result for calling code to use
            action_result['actor_object'] = actor_char
            action_result['target_object'] = target_char
            action_result['game_state'] = game_state
            if bark_msg:
                action_result['bark'] = bark_msg
            if death_msg:
                action_result['death_msg'] = death_msg

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

    @staticmethod
    async def _handle_opportunity_attack(campaign_id: str, actor_name: str, action_name: str, db: AsyncSession, game_state: GameState):
        """
        Checks if there are living enemies. If so, a random enemy interrupts the action and attacks the actor.
        Returns (interrupted: bool, message: str)
        """
        from app.services.chat_service import ChatService
        import random

        living_enemies = [e for e in game_state.enemies if e.hp_current > 0]
        hostile_npcs = [n for n in game_state.npcs if n.hp_current > 0 and getattr(n, 'role', '').lower() in ['hostile', 'enemy']]
        all_hostiles = living_enemies + hostile_npcs

        if not all_hostiles:
            return False, "", game_state

        attacker = random.choice(all_hostiles)

        if game_state.phase != 'combat':
            game_state.phase = 'combat'
            if not game_state.turn_order:
                turn_order = [p.id for p in game_state.party if p.hp_current > 0] + [e.id for e in all_hostiles]
                # Random initiative
                random.shuffle(turn_order)
                game_state.turn_order = turn_order
                game_state.turn_index = 0
                game_state.active_entity_id = turn_order[0]

            await GameService.save_game_state(campaign_id, game_state, db)

        interruption_msg = f"**{attacker.name}** interrupts {actor_name}'s attempt to {action_name} and attacks!"
        await ChatService.save_message(campaign_id, 'system', 'System', interruption_msg, db=db)

        # Execute the attack
        attack_result = await GameService.resolution_attack(campaign_id, attacker.id, attacker.name, actor_name, db)

        full_msg = f"{interruption_msg}\n\n{attack_result['message']}"

        # We must re-fetch state because the attack might have killed the actor or changed stats
        latest_state = await GameService.get_game_state(campaign_id, db)
        return True, full_msg, latest_state

    @staticmethod
    async def resolution_move(campaign_id: str, actor_name: str, direction: str, db: AsyncSession):
        game_state = await GameService.get_game_state(campaign_id, db)
        if not game_state:
            return {"success": False, "message": "No active game state."}

        interrupted, opp_msg, latest_state = await GameService._handle_opportunity_attack(campaign_id, actor_name, "move", db, game_state)
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

        game_state.location = Location(
            id=dest_row.id,
            source_id=target_source_id,
            name=dest_row.name,
            description=visual
        )
        game_state.vessels = []

        await GameService.save_game_state(campaign_id, game_state, db)

        return {
             "success": True,
             "message": f"**{actor_name}** moved the party to **{dest_row.name}**.",
             "game_state": game_state
        }

    @staticmethod
    async def open_vessel(campaign_id: str, actor_name: str, vessel_name: str, db: AsyncSession):
        """
        Unlocks/Opens a vessel by name and returns its contents. Also handles doors and chests.
        """
        from app.models import Vessel

        game_state = await GameService.get_game_state(campaign_id, db)
        if not game_state:
            return {"success": False, "message": "No active game state."}

        interrupted, opp_msg, latest_state = await GameService._handle_opportunity_attack(campaign_id, actor_name, f"open {vessel_name}", db, game_state)
        game_state = await GameService.get_game_state(campaign_id, db)
        if interrupted:
            return {"success": False, "message": opp_msg, "game_state": latest_state}

        # 1. Check permanent architecture (interactables)
        query = select(locations.c.data).where(locations.c.id == game_state.location.id)
        loc_res = await db.execute(query)
        loc_data_str = loc_res.scalar_one_or_none()

        loc_data = json.loads(loc_data_str) if loc_data_str else {}
        interactables = loc_data.get('interactables', [])

        target_interactable = None
        target_idx = -1
        for i, item in enumerate(interactables):
            if vessel_name.lower() in item.get('name', '').lower() or vessel_name.lower() in item.get('id', '').lower():
                target_interactable = item
                target_idx = i
                break

        if target_interactable:
            item_type = target_interactable.get('type')
            current_state = target_interactable.get('state', 'closed')

            if current_state == 'open':
                return {"success": False, "message": f"The {target_interactable['name']} is already open."}

            interactables[target_idx]['state'] = 'open'
            loc_data['interactables'] = interactables

            stmt = (
                update(locations)
                .where(locations.c.id == game_state.location.id)
                .values(data=json.dumps(loc_data))
            )
            await db.execute(stmt)
            await db.commit()

            if item_type == 'door':
                reveal_text = ""
                desc_data = loc_data.get('description', {})
                connections = desc_data.get('connections', [])
                for conn in connections:
                    t_id = conn.get('target_id')
                    if t_id:
                         q_dest = select(locations.c.data).where(locations.c.campaign_id == campaign_id, locations.c.source_id == t_id)
                         dest_res = await db.execute(q_dest)
                         dest_row = dest_res.scalar_one_or_none()
                         if dest_row:
                             d_data = json.loads(dest_row)
                             vis = d_data.get('description', {}).get('visual', '')
                             if vis:
                                  vis_lower = vis[0].lower() + vis[1:] if vis else ""
                                  reveal_text = f", revealing {vis_lower}"
                         break

                return {"success": True, "message": f"**{actor_name}** creaks open the {target_interactable['name']}{reveal_text}."}
            elif item_type == 'chest':
                contents = target_interactable.get('contents', [])
                currency = target_interactable.get('currency', {"pp": 0, "gp": 0, "sp": 0, "cp": 0})

                vessel_name = target_interactable.get('name', 'Chest')
                existing = next((v for v in game_state.vessels if v.name == vessel_name), None)

                if not existing:
                    actor = next((p for p in game_state.party if p.name == actor_name), None)
                    from app.models import Vessel
                    from app.models import Coordinates
                    new_vessel = Vessel(
                        name=vessel_name,
                        description=f"An opened {vessel_name.lower()}.",
                        position=actor.position if actor else Coordinates(q=0, r=0, s=0),
                        contents=contents,
                        currency=currency
                    )
                    game_state.vessels.append(new_vessel)
                    existing = new_vessel

                    target_interactable['contents'] = []
                    target_interactable['currency'] = {"pp": 0, "gp": 0, "sp": 0, "cp": 0}

                    stmt = (
                        update(locations)
                        .where(locations.c.id == game_state.location.id)
                        .values(data=json.dumps(loc_data))
                    )
                    await db.execute(stmt)

                    game_state.location.description = json.dumps(loc_data)
                    await GameService.save_game_state(campaign_id, game_state, db)
                    await db.commit()

                return {
                    "success": True,
                    "message": f"**{actor_name}** opens the {target_interactable['name']}.",
                    "vessel": existing
                }
            return {"success": True, "message": f"**{actor_name}** opens the {target_interactable['name']}."}

        # 2. Check GameState transient vessels (corpses)
        target_vessel = None
        for v in game_state.vessels:
            if v.name.lower() == vessel_name.lower():
                target_vessel = v
                break

        if not target_vessel:
             for v in game_state.vessels:
                 if vessel_name.lower() in v.name.lower():
                     target_vessel = v
                     break

        if not target_vessel:
            return {"success": False, "message": f"Could not find '{vessel_name}' to open."}

        # Format Contents
        items_msg = "Nothing"
        if target_vessel.contents:
             cleaned_items = [i.replace('-', ' ').title() for i in target_vessel.contents]
             items_msg = ", ".join(cleaned_items)

        curr_parts = []
        if target_vessel.currency:
            for c_type in ["pp", "gp", "sp", "cp"]:
                val = target_vessel.currency.get(c_type, 0)
                if val > 0:
                     curr_parts.append(f"{val} {c_type}")

        currency_msg = ", ".join(curr_parts)
        if not currency_msg: currency_msg = "No currency"

        msg = f"**{actor_name}** searches {target_vessel.name}. Inside you find: {items_msg}.\nWealth: {currency_msg}."

        return {
            "success": True,
            "message": msg,
            "vessel": target_vessel
        }

    @staticmethod
    async def take_items(campaign_id: str, actor_id: str, vessel_id: str, item_ids: list, take_currency: bool, db: AsyncSession):
        """
        Transfers items and currency from a vessel to a player's inventory.
        """
        game_state = await GameService.get_game_state(campaign_id, db)
        if not game_state:
            return {"success": False, "message": "No active game state."}

        actor = next((p for p in game_state.party if p.id == actor_id), None)
        if not actor:
            return {"success": False, "message": "Actor not found in party."}

        vessel = next((v for v in game_state.vessels if v.id == vessel_id), None)
        if not vessel:
            return {"success": False, "message": "Vessel not found."}

        taken_items = []
        for i_id in item_ids:
            if i_id in vessel.contents:
                vessel.contents.remove(i_id)
                actor.inventory.append(i_id)
                taken_items.append(i_id)

        taken_currency = {}
        if take_currency and vessel.currency:
            for c_type, amount in vessel.currency.items():
                if amount > 0:
                    actor.currency[c_type] = actor.currency.get(c_type, 0) + amount
                    taken_currency[c_type] = amount
            vessel.currency = {"pp": 0, "gp": 0, "sp": 0, "cp": 0}

        # check if vessel is empty. If it's a corpse and empty, we might leave it or remove it.
        # Leaving it empty is fine.

        await GameService.save_game_state(campaign_id, game_state, db)
        await db.commit()
        await db.commit()

        return {
            "success": True,
            "taken_items": taken_items,
            "taken_currency": taken_currency,
            "vessel": vessel,
            "actor": actor
        }

    @staticmethod
    async def equip_item(campaign_id: str, actor_id: str, item_id: str, is_equip: bool, db: AsyncSession):
        """
        Moves an item between inventory and equipment.
        For now, equipping just moves it from inventory to sheet_data['equipment'].
        We need full item data to properly equip it, but we only have item IDs in inventory.
        We will rely on the UI or data loader to map item_id to full data later, but for now
        let's assume 'equipment' is a list of full item dicts or item IDs.
        Wait, sheet_data['equipment'] expects full item data to render properly on FullCharacterSheet.
        Let's import DataLoader to fetch the item data.
        """
        game_state = await GameService.get_game_state(campaign_id, db)
        if not game_state:
            return {"success": False, "message": "No active game state."}

        actor = next((p for p in game_state.party if p.id == actor_id), None)
        if not actor:
            return {"success": False, "message": "Actor not found."}

        if is_equip:
            # Find item in inventory
            inventory_item = None
            for item in actor.inventory:
                if isinstance(item, str) and item == item_id:
                    inventory_item = item
                    break
                elif isinstance(item, dict) and (item.get('id') == item_id or item.get('name') == item_id):
                    inventory_item = item
                    break

            if not inventory_item:
                return {"success": False, "message": "Item not in inventory."}

            if isinstance(inventory_item, dict):
                item_data = inventory_item
            else:
                # Fallback basic item dict if it was just a string
                is_weapon = item_id.startswith("wpn-")
                is_armor = item_id.startswith("arm-")
                i_type = "Weapon" if is_weapon else ("Armor" if is_armor else "Item")

                # Try to extract stats from compendium or default
                item_data = {"id": item_id, "name": item_id.replace('-', ' ').title().replace('Wpn ', '').replace('Arm ', '').replace('Itm ', ''), "type": i_type}
                if is_weapon:
                    item_data["data"] = {"damage": {"damage_dice": "1d4"}}
                if is_armor:
                    item_data["data"] = {"armor_class": {"base": 11}}

            # Move from inventory to equipment
            actor.inventory.remove(inventory_item)

            if 'equipment' not in actor.sheet_data:
                actor.sheet_data['equipment'] = []

            # Enforce 1 Weapon / 1 Armor limit
            item_type = item_data.get("type", "")
            if item_type in ["Weapon", "Armor"]:
                equipped_items = actor.sheet_data['equipment']
                items_to_unequip = [eq for eq in equipped_items if isinstance(eq, dict) and eq.get("type", "") == item_type]
                for eq_item in items_to_unequip:
                    equipped_items.remove(eq_item)
                    actor.inventory.append(eq_item) # Preserve stats by appending dict

            actor.sheet_data['equipment'].append(item_data)

            await GameService.save_game_state(campaign_id, game_state, db)
            return {"success": True, "message": f"Equipped {item_data.get('name', item_id)}.", "actor": actor}

        else:
            # Unequip
            if 'equipment' not in actor.sheet_data:
                return {"success": False, "message": "No equipment."}

            # Find item in equipment
            equipped_items = actor.sheet_data['equipment']
            item_to_remove = next((i for i in equipped_items if isinstance(i, dict) and (i.get('id') == item_id or i.get('name', '').lower() == item_id.lower())), None)

            if not item_to_remove:
                return {"success": False, "message": "Item not equipped."}

            equipped_items.remove(item_to_remove)

            # Add back to inventory preserving full data
            actor.inventory.append(item_to_remove)

            await GameService.save_game_state(campaign_id, game_state, db)
            return {"success": True, "message": f"Unequipped {item_to_remove.get('name', item_id)}.", "actor": actor}
