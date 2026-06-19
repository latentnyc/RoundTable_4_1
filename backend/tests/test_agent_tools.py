"""Tests for database-aware agent tools (Attack, Check, Move, EndTurn)."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.models import GameState, Coordinates, Location
from game_engine.tools import AttackTool, CheckTool, MoveTool, EndTurnTool


class TestAgentTools:
    @pytest.mark.asyncio
    async def test_attack_tool_execution(self, game_state_factory, player_factory, enemy_factory, coords, mock_db):
        """AttackTool executes a real combat resolution using the database session."""
        p = player_factory(
            name="Fighter",
            hp=20,
            position=coords(0, 0),
            sheet_data={
                "stats": {"strength": 16, "dexterity": 12},
                "equipment": [
                    {
                        "name": "Longsword",
                        "type": "Weapon",
                        "data": {
                            "type": "Melee Weapon",
                            "damage": {"damage_dice": "1d8"}
                        }
                    }
                ]
            }
        )
        e = enemy_factory(name="Goblin", hp=10, position=coords(1, 0))
        gs = game_state_factory(phase="combat", players=[p], enemies=[e])
        tool = AttackTool()

        with patch("app.services.combat_service.StateService") as mock_ss:
            mock_ss.get_game_state = AsyncMock(return_value=gs)
            mock_ss.save_game_state = AsyncMock()

            result = await tool.execute_with_db(
                db=mock_db,
                campaign_id="test_camp",
                attacker_name="Fighter",
                target_name="Goblin"
            )

        assert "Fighter attacks Goblin" in result
        mock_ss.save_game_state.assert_called_once_with("test_camp", gs, mock_db)

    @pytest.mark.asyncio
    async def test_check_tool_execution(self, game_state_factory, player_factory, coords, mock_db):
        """CheckTool executes a real ability check using the character's database statistics."""
        p = player_factory(
            name="Fighter",
            position=coords(0, 0),
            sheet_data={
                "stats": {"strength": 16, "dexterity": 10}
            }
        )
        gs = game_state_factory(players=[p])
        tool = CheckTool()

        with patch("app.services.state_service.StateService.get_game_state", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = gs

            result = await tool.execute_with_db(
                db=mock_db,
                campaign_id="test_camp",
                character_name="Fighter",
                stat="strength",
                dc=12
            )

        assert "Fighter strength check:" in result
        # Check that we applied the correct modifier (+3 for Str 16)
        assert "+ 3" in result

    @pytest.mark.asyncio
    async def test_move_tool_execution(self, game_state_factory, player_factory, coords, mock_db):
        """MoveTool attempts a movement transition calling resolution_move."""
        p = player_factory(name="Fighter", position=coords(0, 0))
        gs = game_state_factory(players=[p])
        
        # Configure connections
        gs.location.id = "loc_start"
        tool = MoveTool()

        with patch("app.services.game_service.GameService.resolution_move", new_callable=AsyncMock) as mock_move:
            mock_move.return_value = {"success": True, "message": "Moved to Barleyrest."}

            result = await tool.execute_with_db(
                db=mock_db,
                campaign_id="test_camp",
                actor_name="Fighter",
                direction="north"
            )

        assert result == "Moved to Barleyrest."
        mock_move.assert_called_once_with(
            campaign_id="test_camp",
            actor_name="Fighter",
            direction="north",
            db=mock_db
        )

    @pytest.mark.asyncio
    async def test_end_turn_tool_execution(self, game_state_factory, player_factory, coords, mock_db):
        """EndTurnTool advances to the next turn using next_turn resolution."""
        p1 = player_factory(name="Fighter", position=coords(0, 0))
        p2 = player_factory(name="Wizard", position=coords(1, 0))
        gs = game_state_factory(phase="combat", players=[p1, p2])
        tool = EndTurnTool()

        with patch("app.services.combat_service.CombatService.next_turn", new_callable=AsyncMock) as mock_next:
            mock_next.return_value = ("Wizard", gs)

            result = await tool.execute_with_db(
                db=mock_db,
                campaign_id="test_camp",
                reason="Done"
            )

        assert "[SYSTEM_COMMAND:END_TURN]" in result
        assert "It is now Wizard's turn." in result
        mock_next.assert_called_once_with("test_camp", mock_db, commit=True)
