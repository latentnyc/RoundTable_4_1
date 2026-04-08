import os
import sys
import pytest
import asyncio
from unittest.mock import AsyncMock

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.models import GameState, Player, Enemy, Coordinates, Location
from app.services.ai_turn_service import AITurnService

@pytest.mark.asyncio
async def test_ai_pathfinding():
    print("\nSetting up mini-board for pathfinding...")
    
    p1 = Player(
        id="player1", name="Alice", user_id="u1", hp_current=20, hp_max=20, ac=12,
        position=Coordinates(q=0, r=0, s=0), role="Fighter", is_ai=False
    )
    
    goblin = Enemy(
        id="enemy1", name="Goblin", hp_current=15, hp_max=15, ac=10,
        position=Coordinates(q=3, r=0, s=-3), is_ai=True, type="Monster",
        data={"actions": [{"name": "Bite", "desc": "Melee Weapon Attack"}]}
    )
    
    walkable = [
        Coordinates(q=0, r=0, s=0),
        Coordinates(q=1, r=0, s=-1),
        Coordinates(q=2, r=0, s=-2),
        Coordinates(q=3, r=0, s=-3)
    ]
    
    gs = GameState(
        session_id="test_session",
        location=Location(name="Cave", description="A cave", walkable_hexes=walkable),
        party=[p1],
        enemies=[goblin],
        active_entity_id="enemy1"
    )
    
    mock_sio = AsyncMock()
    mock_db = AsyncMock()
    
    print(f"Goblin starting at: {goblin.position.q}, {goblin.position.r}")
    print(f"Alice at: {p1.position.q}, {p1.position.r}")
    
    from app.services.combat_service import CombatService
    CombatService.resolution_attack = AsyncMock(return_value={"success": True, "game_state": gs, "is_hit": True, "total_damage": 5})
    
    try:
        result_gs = await AITurnService.execute_ai_turn("test_session", goblin, gs, mock_sio, mock_db, commit=False)
        print(f"Goblin ended at: {goblin.position.q}, {goblin.position.r}")
        if goblin.position.q == 1 and goblin.position.r == 0:
            print("SUCCESS! Goblin moved adjacent to Alice.")
        else:
            print("FAILED! Goblin did not move to (1, 0, -1).")
    except Exception as e:
        import traceback
        print("EXCEPTION RAISED:")
        print(traceback.format_exc())
