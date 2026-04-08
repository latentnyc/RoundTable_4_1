import pytest
import asyncio
from unittest.mock import AsyncMock, patch

pytestmark = pytest.mark.integration  # These tests reference refactored internals and need a live DB

from app.services.turn_manager import TurnManager
from app.models import GameState, Player, Enemy, Coordinates

@pytest.fixture
def base_game_state():
    active_char = Player(id="char1", name="Hero", hp_current=10, hp_max=10, is_ai=False, role="Paladin", position=Coordinates(q=0,r=0,s=0))
    enemy_char = Enemy(id="enemy1", name="Goblin", hp_current=10, hp_max=10, type="Goblin", is_ai=True, position=Coordinates(q=1,r=-1,s=0))

    return GameState(
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

def test_is_character_ai(base_game_state):
    # Test Human Player
    assert TurnManager._is_character_ai(base_game_state, "char1") is False
    
    # Test AI Enemy
    assert TurnManager._is_character_ai(base_game_state, "enemy1") is True
    
    # Test invalid id
    assert TurnManager._is_character_ai(base_game_state, "nonexistent") is False

@pytest.mark.asyncio
async def test_process_turn_human(base_game_state):
    mock_sio = AsyncMock()
    mock_db = AsyncMock()
    
    with patch('app.services.turn_manager.TurnManager._process_turn_step', new_callable=AsyncMock) as mock_process_step:
        mock_process_step.return_value = (base_game_state.party[0], False)
        await TurnManager.process_turn("test_camp", "char1", base_game_state, mock_sio, 0, mock_db)
        
        # Expect _process_turn_step to be called for the human player
        mock_process_step.assert_called_once_with("test_camp", mock_sio, base_game_state, "char1", db=mock_db)

@pytest.mark.asyncio
async def test_process_turn_ai(base_game_state):
    mock_sio = AsyncMock()
    mock_db = AsyncMock()
    
    with patch('app.services.turn_manager.TurnManager._execute_ai_turn_sequence', new_callable=AsyncMock) as mock_exec_ai:
        # Pass an AI character ID
        await TurnManager.process_turn("test_camp", "enemy1", base_game_state, mock_sio, 0, mock_db)
        
        # Expect _execute_ai_turn_sequence to be called for the AI
        mock_exec_ai.assert_called_once_with("test_camp", "enemy1", mock_sio)

@pytest.mark.asyncio
@patch('app.services.lock_service.LockService.acquire')
async def test_advance_game_state(mock_lock, base_game_state):
    from contextlib import asynccontextmanager
    @asynccontextmanager
    async def mock_lock_cm(campaign_id):
        yield True
    mock_lock.side_effect = mock_lock_cm

    mock_db = AsyncMock()
    
    with patch('app.services.combat_service.CombatService.next_turn', new_callable=AsyncMock) as mock_next_turn:
        mock_next_turn.return_value = ("enemy1", base_game_state)
        
        result_id, result_state = await TurnManager._advance_game_state("test_camp", mock_db, base_game_state)
        
        mock_next_turn.assert_called_once_with("test_camp", mock_db, current_game_state=base_game_state, commit=False)
        assert result_id == "enemy1"
        assert result_state == base_game_state
