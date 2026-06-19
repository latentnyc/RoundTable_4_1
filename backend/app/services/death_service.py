import random
import logging
from typing import TYPE_CHECKING
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Vessel, Coordinates
from app.services.loot_service import LootService

if TYPE_CHECKING:
    from app.models import GameState

logger = logging.getLogger(__name__)

class DeathService:
    @staticmethod
    async def handle_entity_death(
        campaign_id: str,
        target_char,
        game_state: 'GameState',
        is_npc: bool,
        db: AsyncSession,
        commit: bool = True
    ):
        """
        Handles target entity death:
        1. Breaks concentration.
        2. Generates corpse Vessel with random currency and character inventory/loot.
        3. Removes entity from game_state party/enemies/npcs lists.
        4. Removes from combat turn order.
        5. Checks for combat victory/defeat condition changes.
        """
        target_id_str = target_char.id
        if isinstance(target_id_str, dict):
            target_id_str = target_id_str.get('id')

        # Break concentration on death
        if getattr(target_char, 'concentrating_on', None):
            from app.services.condition_service import break_concentration
            break_concentration(target_char, game_state)

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
        hostile_npcs = [n for n in game_state.npcs if n.hp_current > 0 and n.hostile]
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
