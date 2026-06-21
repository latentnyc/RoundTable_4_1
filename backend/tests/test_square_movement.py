import asyncio
import pytest
from app.models import GameState, Location, Coordinates, Player
from app.services.game_service import GameService

from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_process_ai_following():
    # Open 13x13 square arena.
    walkable_cells = [
        Coordinates(x=x, y=y)
        for x in range(-6, 7)
        for y in range(-6, 7)
    ]

    leader = Player(
        id="player_1", name="Leader", is_ai=False, control_mode="human",
        hp_current=10, hp_max=10, speed=30,
        position=Coordinates(x=0, y=0), role="Fighter", race="Human",
    )

    follower = Player(
        id="ai_1", name="Follower", is_ai=True, control_mode="ai",
        hp_current=10, hp_max=10, speed=30,
        position=Coordinates(x=5, y=0),  # 5 cells away (Chebyshev)
        role="Wizard", race="Elf",
    )

    game_state = GameState(
        session_id="test_campaign",
        phase="exploration",
        location=Location(name="Test Room", description="", walkable_cells=walkable_cells),
        party=[leader, follower],
        enemies=[],
        npcs=[],
    )

    sio = AsyncMock()

    with patch('app.services.state_service.StateService.save_game_state', new_callable=AsyncMock) as mock_save:
        await GameService.process_ai_following("test_campaign", "player_1", AsyncMock(), sio, game_state)
        # Let the scheduled entity_path_animation create_task run.
        await asyncio.sleep(0.05)

        dist = follower.position.distance_to(leader.position)
        assert dist <= 3
        assert mock_save.call_count == 1
        assert sio.emit.call_count == 2  # game_state_update and entity_path_animation

        emits = sio.emit.call_args_list
        game_state_emits = [c for c in emits if c.args[0] == 'game_state_update']
        assert len(game_state_emits) == 1
        assert game_state_emits[0].kwargs.get('room') == "test_campaign"
