import asyncio
import functools
import random
import logging
from typing import TYPE_CHECKING
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.state_service import StateService
from game_engine.engine import GameEngine

if TYPE_CHECKING:
    from app.models import GameState

logger = logging.getLogger(__name__)

class CombatService:
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
        game_state = await StateService.get_game_state(campaign_id, db)
        if not game_state:
            return {"success": False, "message": "No active game state found!"}

        # Race Condition Fix: Double Check Phase
        if game_state.phase == 'combat':
            return {"success": False, "message": "Combat already in progress.", "game_state": game_state}

        # Helper to get Dex Mod
        def get_dex_mod(entity):
            dex = getattr(entity.stats, 'dexterity', 10) if hasattr(entity, 'stats') else 10
            return (dex - 10) // 2

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

        await StateService.save_game_state(campaign_id, game_state, db)

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
        from app.services.game_service import GameService
        from app.services.loot_service import LootService

        game_state = current_game_state
        if not game_state:
            game_state = await StateService.get_game_state(campaign_id, db)

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
        game_state.has_moved_this_turn = False
        game_state.has_acted_this_turn = False

        if commit:
            await StateService.save_game_state(campaign_id, game_state, db)

        return game_state.active_entity_id, game_state

    @staticmethod
    async def resolution_attack(campaign_id: str, attacker_id: str, attacker_name: str, target_name: str, db: AsyncSession, current_state=None, commit: bool = True, target_id: str = None):
        """
        Mechanically resolves an attack.
        Returns a dict with results and the updated game state elements.
        """
        from app.services.game_service import GameService
        from app.services.loot_service import LootService
        game_state = current_state
        if not game_state:
            game_state = await StateService.get_game_state(campaign_id, db)
        if not game_state:
            return {"success": False, "message": "No active game state found!"}


        actor_char = GameService._find_char_by_name(game_state, attacker_id)
        # Fallback if attacker ID is not found (e.g. system test or mismatched ID), try name
        if not actor_char:
             actor_char = GameService._find_char_by_name(game_state, attacker_name)

        target_char = GameService._find_char_by_name(game_state, target_name, target_id)

        if not actor_char or not target_char:
            print(f"DEBUG: attacker_id={attacker_id}, actor_char={actor_char}, target_name={target_name}, target_char={target_char}")
            for n in game_state.enemies: print(f"DEBUG: ENEMY: {n.name}")
            return {"success": False, "message": f"Could not find actor '{attacker_name}' or target '{target_name}'."}

        # Engine Resolution
        engine = GameEngine()
        actor_data = actor_char.model_dump() if hasattr(actor_char, 'model_dump') else actor_char.dict()
        target_data = target_char.model_dump() if hasattr(target_char, 'model_dump') else target_char.dict()

        # Inject Equipped Weapon Stats if applicable
        weapons = []
        if hasattr(actor_char, 'sheet_data') and 'equipment' in actor_char.sheet_data:
            weapons = [item for item in actor_char.sheet_data['equipment'] if isinstance(item, dict) and item.get('type') == 'Weapon']

        # If no weapons, fallback to Unarmed
        if not weapons:
            weapons = [None]

        action_results = []
        loop = asyncio.get_running_loop()

        for idx, weapon_data in enumerate(weapons):
            params = {}
            if weapon_data and 'data' in weapon_data:
                if 'damage_dice' in weapon_data['data'].get('damage', {}):
                    params['weapon_damage_dice'] = weapon_data['data']['damage']['damage_dice']
                    params['weapon_name'] = weapon_data.get('name', 'Weapon')

                properties = weapon_data['data'].get('properties', [])
                for prop in properties:
                    if isinstance(prop, dict) and 'finesse' in (prop.get('name') or '').lower():
                        params['is_finesse'] = True
                        break

                w_type = (weapon_data['data'].get('type') or '').lower()
                is_w_ranged = 'ranged' in w_type
                for prop in properties:
                    if isinstance(prop, dict) and 'thrown' in (prop.get('name') or '').lower():
                        is_w_ranged = True
                
                if is_w_ranged:
                    params['is_ranged'] = True

                # Second weapon is offhand
                if idx > 0:
                    params['is_offhand'] = True

            # Range Limit Check
            dist = actor_char.position.distance_to(target_char.position)
            is_ranged_attack = params.get('is_ranged', False)
            
            max_hex_range = 1
            if is_ranged_attack and weapon_data and 'data' in weapon_data:
                range_data = weapon_data['data'].get('range', {})
                if isinstance(range_data, dict):
                    normal_range_ft = range_data.get('normal', 120)
                    if isinstance(normal_range_ft, (int, float)):
                        max_hex_range = max(1, int(normal_range_ft) // 5)
                else:
                    max_hex_range = 24 # Fallback 120ft

            if dist > max_hex_range:
                action_results.append({
                    "success": False,
                    "message": f"**{actor_char.name}** tries to attack **{target_char.name}**, but is too far away. (Range: {max_hex_range} hexes)!"
                })
                continue

            # Run synchronous engine logic for this attack
            res = await loop.run_in_executor(
                None,
                functools.partial(
                    GameService._run_engine_resolution,
                    engine,
                    actor_data,
                    "attack",
                    target_data,
                    params
                )
            )
            res['weapon_name'] = params.get('weapon_name')
            res['is_ranged'] = params.get('is_ranged', False)
            res['is_finesse'] = params.get('is_finesse', False)
            action_results.append(res)

            # Stop if target is dead before subsequent attacks
            if res.get("success") and res.get("target_hp_remaining", getattr(target_char, 'hp_current', 0)) <= 0:
                break

        # Aggregate results
        if not action_results:
             return {"success": False, "message": "Attack failed to resolve."}

        # Take the LAST result for state updates (HP, death, etc)
        action_result = action_results[-1]

        # Combine messages
        combined_message = "\n".join([r.get("message", "") for r in action_results if r.get("success")])
        action_result["message"] = combined_message
        if action_result.get("success"):
            new_hp = action_result.get("target_hp_remaining")
            target_char.hp_current = new_hp

            # Hostility
            is_npc = any(n.id == getattr(target_char, 'id', None) for n in game_state.npcs)
            if is_npc:
                # Check current hostility
                if 'hostile' not in getattr(target_char, 'data', {}) or not target_char.data['hostile']:
                    target_char.data['hostile'] = True # Update local state object too

            # Barks & Death Logic
            bark_msg = None
            death_msg = None

            if new_hp > 0:
                # Aggro Bark
                bark = GameService.get_bark(target_char, 'aggro')
                if bark:
                    bark_msg = f'{GameService.get_display_name(target_char)} shouts: "{bark}"'
            else:
                # Death Bark
                bark = GameService.get_bark(target_char, 'death')
                if bark:
                    bark_msg = f'{GameService.get_display_name(target_char)} gasps: "{bark}"'

                # HANDLE DEATH
                death_msg, action_result_updates = await CombatService._handle_entity_death(campaign_id, target_char, game_state, is_npc, db, commit)
                action_result.update(action_result_updates)

            # Save State
            if commit:
                await StateService.save_game_state(campaign_id, game_state, db)

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
    async def resolution_cast(campaign_id: str, actor_id: str, actor_name: str, spell_name: str, target_name: str, db: AsyncSession, commit=True, target_id: str = None):
        """
        Resolves casting a spell in or out of combat.
        """
        from app.services.game_service import GameService
        from app.services.loot_service import LootService

        game_state = await StateService.get_game_state(campaign_id, db)
        if not game_state:
            return {"success": False, "message": "No active game state found!"}

        # Find Actor
        actor_char = None
        for p in game_state.party:
            if getattr(p, 'id', None) == actor_id:
                actor_char = p
                break

        if not actor_char and getattr(game_state, 'phase', '') == 'combat':
            # Could be NPC/Enemy casting (AI Turn)
            for c in (game_state.enemies + game_state.npcs):
                if getattr(c, 'id', None) == actor_id:
                    actor_char = c
                    break

        if not actor_char:
            return {"success": False, "message": "You are not in the current active state."}

        # Validate Spell is known
        # In a real 5E game, we might check slots. For now, just check it's in the spellbook
        spells = []
        if hasattr(actor_char, 'sheet_data') and 'spells' in actor_char.sheet_data:
            spells = actor_char.sheet_data['spells']

        matched_spell = None
        for spl in spells:
            spl_name = spl.get('name', '').lower() if isinstance(spl, dict) else spl.lower()
            if spell_name.lower() in spl_name:
                matched_spell = spl
                break

        if not matched_spell:
            return {"success": False, "message": f"{actor_char.name} does not know the spell '{spell_name}'."}

        # Resolve Target (Optional for some spells, but required for most combat ones)
        target_char = None
        if target_name or target_id:
            target_char = GameService._find_char_by_name(game_state, target_name or "", target_id)
            if not target_char:
                return {"success": False, "message": f"Could not find target '{target_name}'."}

            # Distance Verification for Spell Targeting
            dist = actor_char.position.distance_to(target_char.position)
            spell_range_str = matched_spell.get('data', {}).get('range', 'Touch').lower()
            max_hexes = 1 # Default touch/melee
            
            import re
            if 'feet' in spell_range_str or 'ft' in spell_range_str:
                nums = re.findall(r'\d+', spell_range_str)
                if nums:
                    max_hexes = max(1, int(nums[0]) // 5)
            elif 'mile' in spell_range_str:
                max_hexes = 100 # Effectively limitless on a standard battlemap
            elif 'self' in spell_range_str:
                max_hexes = 0

            # Allow casting on self if distance is 0, otherwise check bounds
            if dist > max_hexes:
                return {"success": False, "message": f"**{actor_char.name}** tries to cast **{spell_name}** at **{target_char.name}**, but they are out of range ({max_hexes} hexes max)!"}

        # Engine Resolution
        engine = GameEngine()
        actor_data = actor_char.model_dump() if hasattr(actor_char, 'model_dump') else actor_char.dict()
        target_data = target_char.model_dump() if target_char and hasattr(target_char, 'model_dump') else target_char.dict() if target_char else None

        params = {
            "spell_data": matched_spell
        }

        loop = asyncio.get_running_loop()
        action_result = await loop.run_in_executor(
            None,
            functools.partial(
                GameService._run_engine_resolution,
                engine,
                actor_data,
                "cast",
                target_data,
                params
            )
        )

        if not action_result.get("success"):
            return action_result

        # Apply state changes (HP drops, death)
        death_msg = None
        if target_char and "target_hp_remaining" in action_result:
            new_hp = action_result["target_hp_remaining"]
            target_char.hp_current = new_hp

            # Hostility Aggro if target is NPC and the spell dealt damage or hostile effect
            # We assume for now targeting them with a spell = hostile
            is_npc = any(n.id == getattr(target_char, 'id', None) for n in game_state.npcs)
            if is_npc:
                if 'hostile' not in getattr(target_char, 'data', {}) or not target_char.data['hostile']:
                    target_char.data['hostile'] = True

            # Death Processing (identical to attack)
            if new_hp <= 0:
                death_msg, action_result_updates = await CombatService._handle_entity_death(campaign_id, target_char, game_state, is_npc, db, commit)
                action_result.update(action_result_updates)

        if commit:
            await StateService.save_game_state(campaign_id, game_state, db)

        action_result['game_state'] = game_state
        if death_msg:
            action_result['death_msg'] = death_msg
            # prepend to description generated by engine
            action_result['message'] = action_result.get('message', '') + "\n\n" + death_msg

        return action_result

    @staticmethod
    async def _handle_opportunity_attack(campaign_id: str, actor_name: str, action_name: str, db: AsyncSession, game_state: 'GameState'):
        """
        Checks if there are living enemies within 10 hexes and with Line of Sight. 
        If so, a random valid enemy interrupts the action and attacks the actor.
        Returns (interrupted: bool, message: str)
        """
        from app.services.chat_service import ChatService
        from app.services.game_service import GameService

        actor_char = GameService._find_char_by_name(game_state, actor_name)
        if not actor_char or not actor_char.position:
            return False, "", game_state

        living_enemies = [e for e in game_state.enemies if getattr(e, 'hp_current', 0) > 0]
        hostile_npcs = [n for n in game_state.npcs if getattr(n, 'hp_current', 0) > 0 and (getattr(n, 'hostile', False) or getattr(n, 'data', {}).get('hostile') == True)]
        all_hostiles = living_enemies + hostile_npcs

        if not all_hostiles:
            return False, "", game_state

        # Filter by distance (<= 10) and Line of Sight
        walkable_set = {(h.q, h.r, h.s) for h in getattr(game_state.location, 'walkable_hexes', [])}
        valid_interrupters = []
        for hostile in all_hostiles:
            if not hostile.position:
                continue
            
            dist = hostile.position.distance_to(actor_char.position)
            if dist > 10:
                continue
                
            # Line of Sight check
            los_path = hostile.position.get_line_to(actor_char.position)
            has_los = True
            for point in los_path:
                if (point.q, point.r, point.s) not in walkable_set:
                    has_los = False
                    break
            
            if has_los:
                valid_interrupters.append(hostile)

        if not valid_interrupters:
            return False, "", game_state

        attacker = random.choice(valid_interrupters)

        if getattr(game_state, 'phase', '') != 'combat':
            game_state.phase = 'combat'
            if not getattr(game_state, 'turn_order', []):
                turn_order = [p.id for p in game_state.party if getattr(p, 'hp_current', 0) > 0] + [e.id for e in all_hostiles]
                random.shuffle(turn_order)
                game_state.turn_order = turn_order
                game_state.turn_index = 0
                game_state.active_entity_id = turn_order[0]

            await StateService.save_game_state(campaign_id, game_state, db)

        interruption_msg = f"**{attacker.name}** catches {actor_name} attempting to {action_name}!\n\n**COMBAT HAS BEGUN!** Roll for Initiative!"
        await ChatService.save_message(campaign_id, 'system', 'System', interruption_msg, db=db)

        # We do NOT grant a free telekinetic melee attack from across the map.
        # Just kickstart the combat loop naturally.

        latest_state = await StateService.get_game_state(campaign_id, db)
        return True, interruption_msg, latest_state

    @staticmethod
    async def _handle_entity_death(campaign_id: str, target_char, game_state: 'GameState', is_npc: bool, db: AsyncSession, commit: bool = True):
        from app.models import Vessel, Coordinates
        from app.services.loot_service import LootService

        target_id_str = target_char.id
        if isinstance(target_id_str, dict):
            target_id_str = target_id_str.get('id')

        action_result_updates = {}

        char_type = getattr(target_char, 'type', getattr(target_char, 'race', ''))
        if not char_type and hasattr(target_char, 'data') and isinstance(target_char.data, dict):
            char_type = target_char.data.get('race', '')
        if isinstance(char_type, dict):
            char_type = target_char.data.get('race', '')
        char_type = char_type.upper()
        v_name = f"CORPSE OF {target_char.name.upper()}"
        if char_type:
            v_name += f" ({char_type})"
        v_desc = f"The lifeless body of {target_char.name}."

        v_contents = list(target_char.inventory) if getattr(target_char, 'inventory', None) else []
        v_contents.extend(LootService.generate_loot(target_char))

        sp = random.randint(1, 10)
        cp = random.randint(1, 10)
        v_currency = {"pp": 0, "gp": 0, "sp": sp, "cp": cp}

        vessel = Vessel(
            name=v_name,
            description=v_desc,
            position=Coordinates(q=target_char.position.q, r=target_char.position.r, s=target_char.position.s) if target_char.position else None,
            contents=v_contents,
            currency=v_currency
        )

        if getattr(game_state, 'vessels', None) is None:
            game_state.vessels = []
        game_state.vessels.append(vessel)
        action_result_updates['vessel_created'] = vessel
        death_msg = f"💀 {target_char.name} has died! A {v_name} falls to the ground."

        if is_npc:
            game_state.npcs = [n for n in game_state.npcs if getattr(n, 'id', None) != target_id_str]
        else:
            game_state.enemies = [e for e in game_state.enemies if getattr(e, 'id', None) != target_id_str]

        if target_id_str in getattr(game_state, 'turn_order', []):
            game_state.turn_order.remove(target_id_str)

        # Combat End Check
        hostile_npcs = [n for n in game_state.npcs if getattr(n, 'hp_current', 0) > 0 and getattr(n, 'data', {}).get('hostile') == True]
        if not game_state.enemies and not hostile_npcs:
            game_state.phase = 'exploration'
            game_state.turn_order = []
            game_state.active_entity_id = None
            death_msg += "\n\n**COMBAT ENDED! VICTORY!**"

            revived = []
            for p in game_state.party:
                if getattr(p, 'hp_current', 0) <= 0:
                    p.hp_current = 1
                    revived.append(p.name)

            if revived:
                death_msg += f"\n*({', '.join(revived)} narrowly survived and regained 1 HP.)*"

            action_result_updates['combat_end'] = 'victory'

        # Defeat Check
        live_party = [p for p in game_state.party if getattr(p, 'hp_current', 0) > 0]
        if not live_party:
            game_state.phase = 'exploration'
            death_msg += "\n\n**DEFEAT! The party has fallen. Game Over.**"
            action_result_updates['combat_end'] = 'defeat'

        return death_msg, action_result_updates
