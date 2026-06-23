import json
import logging
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, insert, desc, bindparam
from sqlalchemy.dialects.postgresql import insert as pg_insert
from db.schema import game_states, characters, monsters, npcs
from app.models import GameState, Player, Enemy, NPC, Vessel

logger = logging.getLogger(__name__)

class StateService:
    """
    Handles all hydration, persistence, and querying of the GameState and its entities.
    Extracted from GameService to adhere to the Single Responsibility Principle.

    Commit contract (Phase 1)
    --------------------------
    Persistence methods here STAGE writes only; they never call ``db.commit()``.
    The owner of the ``AsyncSession`` (the caller that opened it — a command
    dispatcher, a socket handler, etc.) owns the transaction boundary and is
    responsible for committing exactly once on success / rolling back on error.
    This keeps a single logical operation atomic across the entity tables and the
    ``game_states`` row instead of fragmenting it into several partial commits.
    """
    _last_broadcasted_state = {}

    @classmethod
    def clear_campaign_state(cls, campaign_id: str):
        cls._last_broadcasted_state.pop(campaign_id, None)

    @staticmethod
    async def emit_state_update(campaign_id: str, game_state: 'GameState', sio):
        import jsonpatch
        new_state_dict = game_state.model_dump()
        old_state_dict = StateService._last_broadcasted_state.get(campaign_id)

        if old_state_dict:
            patch = jsonpatch.make_patch(old_state_dict, new_state_dict)
            if patch.patch: # Only emit if there are actual changes
                # Version-gated delta: the client applies it only if it currently holds
                # base_version, otherwise it requests a full-state resync. (A full
                # game_state_update carries its own version, read directly by the client.)
                await sio.emit('game_state_patch', {
                    'patch': patch.patch,
                    'base_version': old_state_dict.get('version', 0),
                    'version': new_state_dict.get('version', 0),
                }, room=campaign_id)
        else:
            await sio.emit('game_state_update', new_state_dict, room=campaign_id)

        StateService._last_broadcasted_state[campaign_id] = new_state_dict

    @staticmethod
    async def get_game_state(campaign_id: str, db: AsyncSession) -> GameState:
        # One upserted row per campaign (see save_game_state); the order_by is a
        # defensive tiebreaker for the brief window before the dedup migration runs.
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
        state_data['party'] = await StateService._hydrate_party(state_data.get('party'), db)
        state_data['enemies'] = await StateService._hydrate_enemies(state_data.get('enemies'), db)
        state_data['npcs'] = await StateService._hydrate_npcs(state_data.get('npcs'), db)

        # Hydrate Vessels (stored as dicts in JSON)
        vessel_data = state_data.get('vessels', [])
        state_data['vessels'] = [Vessel(**v) for v in vessel_data if isinstance(v, dict)]

        return GameState(**state_data)

    @staticmethod
    async def save_game_state(campaign_id: str, game_state: GameState, db: AsyncSession):
        """Stage the full game state for persistence (entities + skeleton row).

        Does NOT commit — see the class-level commit contract. The session owner
        commits the whole unit of work atomically.
        """
        from datetime import datetime, timezone

        # Auto-increment state version for client-side gap detection
        game_state.version += 1

        # 1. Update Entities in their specific tables
        await StateService._save_party(game_state.party, campaign_id, db)
        await StateService._save_enemies(game_state.enemies, campaign_id, db)
        await StateService._save_npcs(game_state.npcs, campaign_id, db)

        # 2. Save Lightweight GameState (Skeleton).
        # ONE upserted row per campaign_id (unique constraint uq_game_states_campaign_id):
        # deterministic to read back, and never an append-log race under rapid AI-turn saves.
        state_dict = game_state.model_dump()
        state_dict['party'] = [p.id for p in game_state.party]
        state_dict['enemies'] = [e.id for e in game_state.enemies]
        state_dict['npcs'] = [n.id for n in game_state.npcs]
        state_json = json.dumps(state_dict)
        now = datetime.now(timezone.utc)

        stmt = pg_insert(game_states).values(
            id=str(uuid4()),
            campaign_id=campaign_id,
            turn_index=game_state.turn_index,
            phase=game_state.phase,
            state_data=state_json,
            updated_at=now,
        ).on_conflict_do_update(
            index_elements=['campaign_id'],
            set_={
                'turn_index': game_state.turn_index,
                'phase': game_state.phase,
                'state_data': state_json,
                'updated_at': now,
            },
        )
        await db.execute(stmt)

    @staticmethod
    def _normalize_inventory(inventory) -> list:
        """Coerce an inventory list to canonical item-ID strings.

        The Entity model declares ``inventory: List[str]``; equip/loot paths can
        transiently hold item dicts in memory. Normalizing on the persistence
        boundary keeps the stored shape uniform and the save/load round-trip
        idempotent.
        """
        if not inventory:
            return []
        clean = []
        for item in inventory:
            if isinstance(item, str):
                clean.append(item)
            elif isinstance(item, dict):
                iid = item.get('id') or item.get('name')
                if iid:
                    clean.append(str(iid))
        return clean

    @staticmethod
    def _flag_all_default(kind: str, entity_id, name, hp_max, ac, position):
        """Warn when an entity hydrates to the all-default skeleton (10 HP / AC 10 / 0,0),
        which usually means its persisted data was missing or malformed."""
        pos = position if isinstance(position, dict) else {}
        if hp_max == 10 and ac == 10 and pos.get('x', 0) == 0 and pos.get('y', 0) == 0:
            logger.warning(
                "Hydration produced all-default stats for %s id=%s name=%r "
                "(hp_max=10, ac=10, pos=0,0) — check persisted data.",
                kind, entity_id, name,
            )

    @staticmethod
    async def _hydrate_party(party_ids: list, db: AsyncSession) -> list['Player']:
        if not party_ids: return []

        clean_ids = [str(pid.get('id')) if isinstance(pid, dict) else str(pid) for pid in party_ids]
        if not clean_ids: return []

        q = select(characters).where(characters.c.id.in_(clean_ids))
        rows = (await db.execute(q)).fetchall()
        row_map = {r.id: r for r in rows}

        party_objs: list[Player] = []
        for pid in clean_ids:
            if pid in row_map:
                r = row_map[pid]
                try:
                    s_data = json.loads(r.sheet_data) if r.sheet_data else {}
                except json.JSONDecodeError as e:
                    logger.error(
                        "Corrupt sheet_data for character id=%s name=%r: %s | raw=%.200r",
                        r.id, r.name, e, r.sheet_data,
                    )
                    raise ValueError(f"Corrupt sheet_data JSON for character {r.id}") from e

                # Preserve the original sheet structure so Pydantic doesn't wipe non-Entity attributes
                if 'sheet_data' not in s_data:
                    s_data['sheet_data'] = json.loads(r.sheet_data) if r.sheet_data else {}

                s_data.update({
                    'id': str(r.id),
                    'name': str(r.name) if r.name else "Unknown",
                    'role': str(r.role) if r.role else "Unknown",
                    'race': str(r.race) if r.race else "Human",
                    'user_id': str(r.user_id) if r.user_id else None, # Important for auth checks
                    'control_mode': str(s_data.get('control_mode') or (r.control_mode if hasattr(r, 'control_mode') and r.control_mode else "human"))
                })

                # Apply defaults for core Entity fields if missing from sheet_data
                if 'is_ai' not in s_data: s_data['is_ai'] = False
                if 'hp_max' not in s_data:
                    s_data['hp_max'] = int(s_data.get('stats', {}).get('hp_max', 10))
                if 'hp_current' not in s_data:
                    s_data['hp_current'] = int(s_data.get('hp_max', 10))
                if 'position' not in s_data:
                    s_data['position'] = {"x": 0, "y": 0}

                # Normalize inventory to canonical id-strings (model is List[str]).
                if 'inventory' in s_data:
                    s_data['inventory'] = StateService._normalize_inventory(s_data['inventory'])

                # Calculate actual AC based on stats and equipment
                from game_engine.character_sheet import CharacterSheet
                temp_sheet = CharacterSheet(s_data)
                s_data['ac'] = temp_sheet.get_ac()

                StateService._flag_all_default("character", r.id, r.name, s_data.get('hp_max'), s_data.get('ac'), s_data.get('position'))
                party_objs.append(Player(**s_data))
        return party_objs

    @staticmethod
    async def _hydrate_enemies(enemy_ids: list, db: AsyncSession) -> list['Enemy']:
        if not enemy_ids: return []

        clean_ids = [str(eid.get('id')) if isinstance(eid, dict) else str(eid) for eid in enemy_ids]
        if not clean_ids: return []

        q = select(monsters).where(monsters.c.id.in_(clean_ids))
        rows = (await db.execute(q)).fetchall()
        row_map = {r.id: r for r in rows}

        enemy_objs: list[Enemy] = []
        for eid in clean_ids:
            if eid in row_map:
                r = row_map[eid]
                try:
                    d = json.loads(r.data) if r.data else {}
                except json.JSONDecodeError as e:
                    logger.error(
                        "Corrupt data for monster id=%s name=%r: %s | raw=%.200r",
                        r.id, r.name, e, r.data,
                    )
                    raise ValueError(f"Corrupt data JSON for monster {r.id}") from e

                # Base init with data blob
                init_d = {'data': d}
                # Overlay DB columns
                init_d.update({
                    'id': str(r.id),
                    'name': str(r.name) if r.name else "Unknown",
                    'type': str(r.type) if r.type else "Unknown"
                })
                # Overlay strict fields from data if present (for Pydantic)
                for field in ['hp_current', 'hp_max', 'is_ai', 'position', 'identified']:
                    if field in d: init_d[field] = d[field]

                # Apply defaults for core Base Entity fields if missing from d
                if 'is_ai' not in init_d: init_d['is_ai'] = True
                if 'hp_max' not in init_d:
                    init_d['hp_max'] = int(d.get('stats', {}).get('hp', 10))
                if 'hp_current' not in init_d:
                    init_d['hp_current'] = int(init_d.get('hp_max', 10))
                if 'position' not in init_d:
                    init_d['position'] = {"x": 0, "y": 0}
                if 'ac' not in init_d:
                    init_d['ac'] = int(d.get('stats', {}).get('ac', 10))

                StateService._flag_all_default("monster", r.id, r.name, init_d.get('hp_max'), init_d.get('ac'), init_d.get('position'))
                enemy_objs.append(Enemy(**init_d))
        return enemy_objs

    @staticmethod
    async def _hydrate_npcs(npc_ids: list, db: AsyncSession) -> list['NPC']:
        if not npc_ids: return []

        clean_ids = [str(nid.get('id')) if isinstance(nid, dict) else str(nid) for nid in npc_ids]
        if not clean_ids: return []

        q = select(npcs).where(npcs.c.id.in_(clean_ids))
        rows = (await db.execute(q)).fetchall()
        row_map = {r.id: r for r in rows}

        npc_objs: list[NPC] = []
        for nid in clean_ids:
            if nid in row_map:
                r = row_map[nid]
                try:
                    d = json.loads(r.data) if r.data else {}
                except json.JSONDecodeError as e:
                    logger.error(
                        "Corrupt data for npc id=%s name=%r: %s | raw=%.200r",
                        r.id, r.name, e, r.data,
                    )
                    raise ValueError(f"Corrupt data JSON for npc {r.id}") from e

                init_d = {'data': d}
                init_d.update({
                    'id': str(r.id),
                    'name': str(r.name) if r.name else "Unknown",
                    'role': str(r.role) if r.role else "Unknown"
                })

                for field in ['hp_current', 'hp_max', 'is_ai', 'position', 'identified']:
                    if field in d: init_d[field] = d[field]

                # Apply defaults for core Base Entity fields if missing
                if 'is_ai' not in init_d: init_d['is_ai'] = True
                if 'hp_max' not in init_d:
                    init_d['hp_max'] = int(d.get('stats', {}).get('hp', 10))
                if 'hp_current' not in init_d:
                    init_d['hp_current'] = int(init_d.get('hp_max', 10))
                if 'position' not in init_d:
                    init_d['position'] = {"x": 0, "y": 0}
                if 'ac' not in init_d:
                    init_d['ac'] = int(d.get('stats', {}).get('ac', 10))

                if not r.role and 'role' in d: init_d['role'] = str(d['role'])

                StateService._flag_all_default("npc", r.id, r.name, init_d.get('hp_max'), init_d.get('ac'), init_d.get('position'))
                npc_objs.append(NPC(**init_d))
        return npc_objs

    @staticmethod
    async def _save_party(party: list, campaign_id: str, db: AsyncSession):
        if not party: return

        party_ids = [p.id for p in party]
        existing_pids = set((await db.scalars(select(characters.c.id).where(characters.c.id.in_(party_ids)))).all())

        updates, inserts = [], []
        for p in party:
            if not p.sheet_data: p.sheet_data = {}
            # Sync transient fields to the preserved sheet_data blob (the source of truth)
            for field in ['hp_current', 'hp_max', 'is_ai', 'control_mode', 'currency']:
                if hasattr(p, field):
                    p.sheet_data[field] = getattr(p, field)
            # Normalize inventory to canonical id-strings before persisting.
            if hasattr(p, 'inventory'):
                p.sheet_data['inventory'] = StateService._normalize_inventory(p.inventory)
            if hasattr(p, 'position') and p.position:
                pos = getattr(p, 'position')
                p.sheet_data['position'] = pos.model_dump() if hasattr(pos, 'model_dump') else pos

            sheet_json = json.dumps(p.sheet_data)
            if p.id in existing_pids:
                # Rewrite scalar columns from the entity too, so columns never drift
                # from the blob (hydration overlays these columns over the blob).
                updates.append({
                    "b_id": p.id,
                    "b_sheet_data": sheet_json,
                    "b_name": p.name,
                    "b_role": p.role,
                    "b_control_mode": p.control_mode,
                })
            else:
                inserts.append({
                    "id": p.id,
                    "sheet_data": sheet_json,
                    "user_id": p.user_id if p.user_id else "system",
                    "campaign_id": campaign_id,
                    "name": p.name,
                    "role": p.role,
                    "control_mode": p.control_mode
                })

        if updates:
            await db.execute(
                update(characters)
                .where(characters.c.id == bindparam('b_id'))
                .values(
                    sheet_data=bindparam('b_sheet_data'),
                    name=bindparam('b_name'),
                    role=bindparam('b_role'),
                    control_mode=bindparam('b_control_mode'),
                ),
                updates,
            )
        if inserts:
            await db.execute(insert(characters), inserts)

    @staticmethod
    async def _save_enemies(enemies: list, campaign_id: str, db: AsyncSession):
        if not enemies: return

        eids = [e.id for e in enemies]
        existing = set((await db.scalars(select(monsters.c.id).where(monsters.c.id.in_(eids)))).all())

        updates, inserts = [], []
        for e in enemies:
            e_data = e.model_dump()
            if e.id in existing:
                # Keep scalar columns (name/type) in sync with the blob on update.
                updates.append({"b_id": e.id, "b_data": json.dumps(e_data), "b_name": e.name, "b_type": e.type})
            else:
                inserts.append({
                    "id": e.id, "data": json.dumps(e_data), "campaign_id": campaign_id, "name": e.name, "type": e.type
                })

        if updates:
            await db.execute(
                update(monsters)
                .where(monsters.c.id == bindparam('b_id'))
                .values(data=bindparam('b_data'), name=bindparam('b_name'), type=bindparam('b_type')),
                updates,
            )
        if inserts:
            await db.execute(insert(monsters), inserts)

    @staticmethod
    async def _save_npcs(npcs_list: list, campaign_id: str, db: AsyncSession):
        if not npcs_list: return

        nids = [n.id for n in npcs_list]
        existing = set((await db.scalars(select(npcs.c.id).where(npcs.c.id.in_(nids)))).all())

        updates, inserts = [], []
        for n in npcs_list:
            if not n.data: n.data = {}
            for field in ['hp_current', 'hp_max', 'identified', 'is_ai', 'hostile', 'friendly', 'ally']:
                 n.data[field] = getattr(n, field)
            n.data['position'] = n.position.model_dump()
            n.data['conditions'] = [c.model_dump() for c in n.conditions] if n.conditions else []

            if n.id in existing:
                # Keep scalar columns (name/role) in sync with the blob on update.
                updates.append({"b_id": n.id, "b_data": json.dumps(n.data), "b_name": n.name, "b_role": n.role})
            else:
                inserts.append({
                    "id": n.id, "data": json.dumps(n.data), "campaign_id": campaign_id, "name": n.name, "role": n.role
                })

        if updates:
            await db.execute(
                update(npcs)
                .where(npcs.c.id == bindparam('b_id'))
                .values(data=bindparam('b_data'), name=bindparam('b_name'), role=bindparam('b_role')),
                updates,
            )
        if inserts:
            await db.execute(insert(npcs), inserts)
