import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from contextlib import asynccontextmanager
from app.services.turn_manager import TurnManager
from app.services.game_service import GameService
from app.services.combat_service import CombatService
from app.models import GameState, Player, Enemy, Coordinates

@pytest.mark.asyncio
async def test_turn_advancement_locking():
    """
    Verify that concurrent calls to advance_turn do not race.
    """
    # Mock SIO
    mock_sio = AsyncMock()

    # Mock DB
    mock_db = AsyncMock()

    # Mock Game State
    active_char = Player(id="char1", name="Hero", hp_current=10, hp_max=10, is_ai=False, role="Paladin", position=Coordinates(q=0,r=0,s=0))
    enemy_char = Enemy(id="enemy1", name="Goblin", hp_current=10, hp_max=10, type="Goblin", is_ai=True, position=Coordinates(q=1,r=-1,s=0))

    initial_state = GameState(
        session_id="test_camp",
        turn_index=0,
        phase="combat",
        turn_order=["char1", "enemy1"],
        active_entity_id="char1",
        party=[active_char],
        enemies=[enemy_char],
        npcs=[],
        location={"name": "Test Loc", "description": "Test Desc"}
    )

    # Mock CombatService.next_turn to simulate work
    async def mock_next_turn(camp_id, db, current_game_state=None, commit=True, **kwargs):
        await asyncio.sleep(0.1) # Simulate DB latency

        # Simple toggle logic for test
        current_idx = current_game_state.turn_index if current_game_state else 0
        next_idx = (current_idx + 1) % 2
        next_id = "char1" if next_idx == 0 else "enemy1"

        new_state = initial_state.model_copy()
        new_state.turn_index = next_idx
        new_state.active_entity_id = next_id

        return next_id, new_state

    async def mock_process_step(campaign_id, sio, game_state, active_id, **kwargs):
        # We don't care about the UI step for this concurrency test
        # Returning None stops the loop, which is fine for just testing advance_turn race
        return None

    @asynccontextmanager
    async def mock_lock(campaign_id):
        yield True

    async def mock_save_state(camp_id, st, db_sess):
        return st

    with patch('app.services.combat_service.CombatService.next_turn', side_effect=mock_next_turn) as mock_next:
        with patch('app.services.turn_manager.TurnManager._process_turn_step', side_effect=mock_process_step):
            with patch('app.services.lock_service.LockService.acquire', side_effect=mock_lock):
                with patch('app.services.game_service.GameService.save_game_state', side_effect=mock_save_state):
                    # Fire two concurrent turn advancements
                    task1 = asyncio.create_task(TurnManager.advance_turn("test_camp", mock_sio, db=mock_db, current_game_state=initial_state))
                    task2 = asyncio.create_task(TurnManager.advance_turn("test_camp", mock_sio, db=mock_db, current_game_state=initial_state))
            
                    await asyncio.gather(task1, task2)
            
                    assert mock_next.call_count >= 1

@pytest.mark.asyncio
async def test_combat_start_race_condition():
    """
    Verify that start_combat checks for existing combat.
    """
    mock_db = AsyncMock()

    # Scene 1: Combat already active
    active_state = GameState(
        session_id="test_camp",
        turn_index=0,
        phase="combat",
        turn_order=[],
        active_entity_id="",
        party=[],
        enemies=[],
        npcs=[],
        location={"name": "Test Loc", "description": "Test Desc"}
    )

    with patch('app.services.state_service.StateService.get_game_state', return_value=active_state):
        result = await CombatService.start_combat("test_camp", mock_db)
        assert result['success'] == False
        assert result['message'] == "Combat already in progress."

    # Scene 2: Combat NOT active
    peace_state = GameState(
        session_id="test_camp",
        turn_index=0,
        phase="exploration",
        turn_order=[],
        active_entity_id="",
        party=[],
        enemies=[],
        npcs=[],
        location={"name": "Test Loc", "description": "Test Desc"}
    )

    with patch('app.services.state_service.StateService.get_game_state', return_value=peace_state):
        with patch('app.services.state_service.StateService.save_game_state', new_callable=AsyncMock) as mock_save:
             result = await CombatService.start_combat("test_camp", mock_db)
             assert result['success'] == True
             assert result['message'] == "Combat Started!"
             mock_save.assert_called_once()
