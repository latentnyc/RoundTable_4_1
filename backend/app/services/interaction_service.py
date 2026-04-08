import secrets

secure_random = secrets.SystemRandom()
from sqlalchemy.ext.asyncio import AsyncSession
from app.utils.entity_utils import EntityUtils
from app.services.state_service import StateService

class InteractionService:
    @staticmethod
    async def resolution_identify(campaign_id: str, actor_name: str, target_name: str, db: AsyncSession, target_id: str = None):
        """
        Mechanically resolves an identify/investigate check.
        Returns a dict with result and message.
        """
        game_state = await StateService.get_game_state(campaign_id, db)
        if not game_state:
            return {"success": False, "message": "No active game state found!"}

        # Resolve Actor
        # Usually a player, but theoretically could be NPC vs NPC
        actor_char = EntityUtils.find_char_by_name(game_state, actor_name)

        if not actor_char:
             return {"success": False, "message": f"Could not find actor '{actor_name}'."}

        target_char = EntityUtils.find_char_by_name(game_state, target_name, target_id)
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

        roll = secure_random.randint(1, 20)
        total = roll + int_mod

        is_success = total >= dc

        result_pkg = {
            "success": is_success,
            "roll_total": total,
            "roll_detail": f"{roll} (d20) + {int_mod} (INT)",
            "target_name": EntityUtils.get_display_name(target_char),
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
            result_pkg["message"] = f"You study {EntityUtils.get_display_name(target_char)} closely... It is {target_char.name}!"

        else:
            result_pkg["message"] = f"You glance at {EntityUtils.get_display_name(target_char)} but cannot discern anything new."

        return result_pkg
