
import asyncio
import json
from uuid import uuid4
from app.models import GameState, Player, Enemy, Location, Coordinates
from app.services.game_service import GameService
from app.services.combat_service import CombatService
from unittest.mock import MagicMock, AsyncMock

async def test_combat_loop_loot():
    print("--- Starting Combat Loot Verification ---")

    # 1. Setup Mock DB Session
    mock_db = MagicMock()
    mock_db.execute = MagicMock()
    mock_db.commit = MagicMock()

    # 2. Setup GameState
    loc = Location(name="Test Loc", description="Test Desc")
    p1 = Player(
        id="player_1",
        name="Hero",
        role="Fighter",
        hp_current=10,
        hp_max=10,
        is_ai=False,
        position=Coordinates(q=0,r=0,s=0)
    )
    e1 = Enemy(
        id="goblin_1",
        name="Goblin",
        type="Goblin",
        hp_current=5,
        hp_max=5,
        is_ai=True,
        position=Coordinates(q=1,r=-1,s=0),
        inventory=["rusty-sword"],
        data={"loot": {"guaranteed": ["gold-tooth"]}} # Mock loot data
    )

    gs = GameState(
        session_id="test_session",
        location=loc,
        party=[p1],
        enemies=[e1],
        vessels=[],
        turn_order=[p1.id, e1.id], # Combat active
        phase="combat"
    )

    print(f"Initial State: Enemies={len(gs.enemies)}, Vessels={len(gs.vessels)}")

    # 3. Execute Attack (Kill Shot)
    # Mocking get_game_state to return our local gs via async wrapper
    async def mock_get_game_state(*args, **kwargs):
        return gs
    GameService.get_game_state = mock_get_game_state

    # Mocking save to do nothing but satisfy await
    GameService.save_game_state = MagicMock()
    async def noop(*args, **kwargs): pass
    GameService.save_game_state.side_effect = noop
    GameService.update_char_hp = MagicMock()
    GameService.update_char_hp.side_effect = noop
    GameService.update_npc_hostility = MagicMock()
    GameService.update_npc_hostility.side_effect = noop

    print("Executing fatal attack on Goblin...")
    # Force damage to kill (5 damage to 5 HP goblin)
    # We can't easily mock the ENGINE execution inside resolution_attack without more mocking.
    # So we will rely on CombatService.resolution_attack calling the engine.
    # Wait, resolution_attack calls `loop.run_in_executor(None, engine.resolve_action...)`.
    # We need to mock that or the engine itself.

    # Let's mock `GameEngine.resolve_action` return value directly if we can,
    # OR we can just mock `_run_engine_resolution` helper in GameService!
    # Let's mock `_run_engine_resolution` helper in GameService!
    def mock_run_resolution(*args, **kwargs):
        return {
            "success": True,
            "target_hp_remaining": 0, # FATAL
            "message": "Hit for 5 damage!",
            "damage_total": 5,
            "is_hit": True
        }
    GameService._run_engine_resolution = mock_run_resolution

    result = await CombatService.resolution_attack("camp_id", "Hero", "Hero", "Goblin", mock_db, current_state=gs, commit=False)

    # 4. Assertions
    print("\n--- Results ---")
    print(f"Attack Result Success: {result.get('success')}")
    if 'death_msg' in result:
        print(f"Death Msg: {result['death_msg']}")

    # Verify Vessel Created
    if gs.vessels:
        v = gs.vessels[0]
        print(f"Vessel Created: Name='{v.name}'")
        print(f"Description: {v.description}")
        print(f"Contents: {v.contents}")
        print(f"Currency: {v.currency}")

        # Checks
        if v.name == "CORPSE OF GOBLIN":
            print("✅ Vessel Name Correct (Capitalized)")
        else:
            print(f"❌ Vessel Name Incorrect: {v.name}")

        if "rusty-sword" in v.contents and "gold-tooth" in v.contents:
             print("✅ Inventory & Guaranteed Loot Transferred")
        else:
             print("❌ Missing items in vessel")

        if v.currency['sp'] > 0 or v.currency['cp'] > 0:
            print(f"✅ Currency Generated: {v.currency['sp']}sp, {v.currency['cp']}cp")
        else:
            print("❌ No currency generated")

    else:
        print("❌ No Vessel Created!")

    # Verify Enemies Removed (from active list logic in service)
    # Service modifies gs.enemies directly
    print(f"Remaining Enemies: {len(gs.enemies)}")
    if len(gs.enemies) == 0:
        print("✅ Enemy removed from active list")
    else:
        print("❌ Enemy still in list")

    # Verify Combat End
    if result.get('combat_end') == 'victory':
        print("✅ Combat Victory Detected")
    else:
         print(f"❌ Combat End Status: {result.get('combat_end')}")

    # 5. Test Open Command
    # print("\n--- Testing Open Command ---")
    # open_res = await GameService.open_vessel("camp_id", "Hero", "Corpse of Goblin", mock_db)
    # print(f"Open Result: {open_res.get('message')}")

    # if "rusty sword" in open_res.get('message', '').lower():
    #     print("✅ Open Command lists contents")
    # else:
    #     print(f"❌ Open Command missing content listing: {open_res.get('message')}")

if __name__ == "__main__":
    asyncio.run(test_combat_loop_loot())
