import pytest
from app.models import GameState, Location, Coordinates, Player
from app.services.movement_service import MovementService

from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_process_ai_following():
    # Setup mock game state
    
    # 5x5 grid roughly
    walkable_hexes = []
    for q in range(-6, 7):
        for r in range(-6, 7):
            walkable_hexes.append(Coordinates(q=q, r=r, s=-q-r))
            
    leader = Player(
        id="player_1",
        name="Leader",
        is_ai=False,
        control_mode="human",
        hp_current=10,
        hp_max=10,
        speed=30,
        position=Coordinates(q=0, r=0, s=0),
        role="Fighter",
        race="Human"
    )
    
    follower = Player(
        id="ai_1",
        name="Follower",
        is_ai=True,
        control_mode="ai",
        hp_current=10,
        hp_max=10,
        speed=30,
        position=Coordinates(q=0, r=-5, s=5), # 5 hexes away (max diff)
        role="Wizard",
        race="Elf"
    )
    
    game_state = GameState(
        session_id="test_campaign",
        phase="exploration",
        location=Location(
            name="Test Room",
            description="",
            walkable_hexes=walkable_hexes
        ),
        party=[leader, follower],
        enemies=[],
        npcs=[]
    )
    
    # Mocks

    sio = AsyncMock()
    
    with patch('app.services.state_service.StateService.save_game_state', new_callable=AsyncMock) as mock_save:
        await MovementService.process_ai_following("test_campaign", "player_1", AsyncMock(), sio, game_state)
        
        # Helper for checking hex distance
        def hex_distance(q1, r1, s1, q2, r2, s2):
            return max(abs(q1 - q2), abs(r1 - r2), abs(s1 - s2))
            
        dist = hex_distance(follower.position.q, follower.position.r, follower.position.s, leader.position.q, leader.position.r, leader.position.s)
        
        print(f"Follower new position: {follower.position}")
        print(f"Leader position: {leader.position}")
        print(f"Distance: {dist}")
        
        assert dist <= 3
        assert mock_save.call_count == 1
        assert sio.emit.call_count == 2 # Expecting game_state_update and entity_path_animation
        
        # Check that game_state_update was emitted
        emits = sio.emit.call_args_list
        game_state_emits = [c for c in emits if c.args[0] == 'game_state_update']
        assert len(game_state_emits) == 1
        assert game_state_emits[0].kwargs.get('room') == "test_campaign"


