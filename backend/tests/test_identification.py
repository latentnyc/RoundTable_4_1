
import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure backend is in path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.game_service import GameService
from app.models import GameState, NPC, Player, Location

async def test_identification():
    print("Testing Identification Logic...")

    # Mock DB Session
    mock_db = AsyncMock()

    # Mock Game State
    # Note: Pydantic models require all fields or defaults.
    mock_npc = NPC(
        id="npc1",
        name="Silas",
        role="Hunter",
        data={"race": "Human", "description": "A mysterious figure."},
        is_ai=True,
        hp_current=20,
        hp_max=20,
        position={"x": 0, "y": 0, "z": 0, "q": 0, "r": 0, "s": 0},
        identified=False
    )

    mock_player = Player(
        id="p1",
        name="Cedia",
        role="Bard",
        hp_current=10,
        hp_max=10,
        sheet_data={"stats": {"intelligence": 16}},
        is_ai=False,
        position={"x": 5, "y": 5, "z": 0, "q": 0, "r": 0, "s": 0}
    )

    mock_location = Location(
        id="loc1",
        source_id="room1",
        name="Torchlit Room",
        description="A small room."
    )

    mock_game_state = GameState(
        id="campaign1",
        session_id="session1",
        party=[mock_player],
        npcs=[mock_npc],
        enemies=[],
        location=mock_location,
        phase="exploration"
    )

    # Mock get_game_state to return our mock state
    with patch('app.services.game_service.GameService.get_game_state', new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_game_state

        # Mock update_npc_field
        with patch('app.services.game_service.GameService.update_npc_field', new_callable=AsyncMock) as mock_update:

            # Test 1: Identify "Man" (Search for Silas)
            print("\nTest 1: Identify 'Silas' (Success Case)")
            result = await GameService.resolution_identify("campaign1", "Cedia", "Silas", mock_db)
            print(f"Result: {result}")

            if result['success'] and result['target_name'] == "Silas":
                print("PASS: Identification successful.")
            else:
                print("FAIL: Identification failed.")

            # Test 2: Already Identified
            print("\nTest 2: Already Identified")
            mock_npc.identified = True
            result = await GameService.resolution_identify("campaign1", "Cedia", "Silas", mock_db)
            print(f"Result: {result}")

            if result['success'] and result.get('reason') == 'already_known':
                print("PASS: Correctly handled already identified NPC.")
            else:
                print("FAIL: Did not detect already identified status.")

if __name__ == "__main__":
    asyncio.run(test_identification())
