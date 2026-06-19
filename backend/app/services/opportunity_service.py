import random
import logging
from typing import TYPE_CHECKING
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.state_service import StateService
from app.services.chat_service import ChatService

if TYPE_CHECKING:
    from app.models import GameState

logger = logging.getLogger(__name__)

class OpportunityService:
    @staticmethod
    async def handle_opportunity_attack(
        campaign_id: str,
        actor_name: str,
        action_name: str,
        db: AsyncSession,
        game_state: 'GameState'
    ):
        """
        Checks if there are living enemies within 10 hexes and with Line of Sight. 
        If so, a random valid enemy interrupts the action and attacks the actor.
        Returns (interrupted: bool, message: str, latest_game_state: GameState)
        """
        from app.services.game_service import GameService
        actor_char = GameService._find_char_by_name(game_state, actor_name)
        if not actor_char or not actor_char.position:
            return False, "", game_state

        living_enemies = [e for e in game_state.enemies if getattr(e, 'hp_current', 0) > 0]
        hostile_npcs = [n for n in game_state.npcs if n.hp_current > 0 and n.hostile]
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
