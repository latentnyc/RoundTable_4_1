"""Tests for OpportunityService: opportunity attack logic outside and inside combat."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.opportunity_service import OpportunityService
from app.models import GameState, Coordinates


class TestOpportunityAttack:
    """Tests for OpportunityService.handle_opportunity_attack."""

    @pytest.mark.asyncio
    async def test_triggers_combat_when_in_range_and_los(self, game_state_factory, player_factory, enemy_factory, coords, mock_db):
        """Opportunity attack triggers if hostile is within 10 hexes with Line of Sight."""
        p = player_factory(name="Fighter", position=coords(0, 0))
        e = enemy_factory(name="Goblin", position=coords(2, 0))

        # Include walkable hexes covering the path
        walkable = [coords(0, 0), coords(1, 0), coords(2, 0)]
        gs = game_state_factory(phase="exploration", players=[p], enemies=[e])
        gs.location.walkable_hexes = walkable

        with patch("app.services.opportunity_service.StateService") as mock_ss, \
             patch("app.services.opportunity_service.ChatService") as mock_chat:
            mock_ss.get_game_state = AsyncMock(return_value=gs)
            mock_ss.save_game_state = AsyncMock()
            mock_chat.save_message = AsyncMock()

            interrupted, msg, latest_state = await OpportunityService.handle_opportunity_attack(
                "test_camp", "Fighter", "move", mock_db, gs
            )

        assert interrupted is True
        assert "catches Fighter attempting to move" in msg
        assert gs.phase == "combat"
        assert len(gs.turn_order) == 2
        assert p.id in gs.turn_order
        assert e.id in gs.turn_order
        assert gs.active_entity_id is not None
        mock_ss.save_game_state.assert_called_once_with("test_camp", gs, mock_db)
        mock_chat.save_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_does_not_trigger_when_out_of_range(self, game_state_factory, player_factory, enemy_factory, coords, mock_db):
        """Opportunity attack does not trigger if hostile is > 10 hexes away."""
        p = player_factory(name="Fighter", position=coords(0, 0))
        e = enemy_factory(name="Goblin", position=coords(11, 0))

        # Include walkable hexes covering the long path
        walkable = [coords(q, 0) for q in range(12)]
        gs = game_state_factory(phase="exploration", players=[p], enemies=[e])
        gs.location.walkable_hexes = walkable

        interrupted, msg, latest_state = await OpportunityService.handle_opportunity_attack(
            "test_camp", "Fighter", "move", mock_db, gs
        )

        assert interrupted is False
        assert msg == ""
        assert gs.phase == "exploration"

    @pytest.mark.asyncio
    async def test_does_not_trigger_when_no_los(self, game_state_factory, player_factory, enemy_factory, coords, mock_db):
        """Opportunity attack does not trigger if Line of Sight is blocked (middle hex not walkable)."""
        p = player_factory(name="Fighter", position=coords(0, 0))
        e = enemy_factory(name="Goblin", position=coords(2, 0))

        # Missing coords(1, 0) in walkable makes it non-walkable (blocked LOS)
        walkable = [coords(0, 0), coords(2, 0)]
        gs = game_state_factory(phase="exploration", players=[p], enemies=[e])
        gs.location.walkable_hexes = walkable

        interrupted, msg, latest_state = await OpportunityService.handle_opportunity_attack(
            "test_camp", "Fighter", "move", mock_db, gs
        )

        assert interrupted is False
        assert msg == ""
        assert gs.phase == "exploration"

    @pytest.mark.asyncio
    async def test_triggers_inside_combat_without_phase_transition(self, game_state_factory, player_factory, enemy_factory, coords, mock_db):
        """Opportunity attack triggers if already in combat but doesn't re-initialize turn order."""
        p = player_factory(name="Fighter", position=coords(0, 0))
        e = enemy_factory(name="Goblin", position=coords(2, 0))

        walkable = [coords(0, 0), coords(1, 0), coords(2, 0)]
        gs = game_state_factory(phase="combat", players=[p], enemies=[e])
        gs.location.walkable_hexes = walkable
        gs.turn_order = [p.id, e.id]
        gs.turn_index = 0
        gs.active_entity_id = p.id

        with patch("app.services.opportunity_service.StateService") as mock_ss, \
             patch("app.services.opportunity_service.ChatService") as mock_chat:
            mock_ss.get_game_state = AsyncMock(return_value=gs)
            mock_ss.save_game_state = AsyncMock()
            mock_chat.save_message = AsyncMock()

            interrupted, msg, latest_state = await OpportunityService.handle_opportunity_attack(
                "test_camp", "Fighter", "move", mock_db, gs
            )

        assert interrupted is True
        assert "catches Fighter attempting to move" in msg
        assert gs.phase == "combat"
        assert gs.turn_order == [p.id, e.id]
        assert gs.turn_index == 0
        assert gs.active_entity_id == p.id
        # StateService.save_game_state should NOT be called because it was already in combat
        mock_ss.save_game_state.assert_not_called()
        mock_chat.save_message.assert_called_once()
