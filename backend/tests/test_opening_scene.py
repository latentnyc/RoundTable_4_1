import sys
import os
import asyncio
import uuid
from unittest.mock import MagicMock, AsyncMock, patch

# Add backend to path
sys.path.append(os.getcwd())

from app.models import GameState, Location
from app.socket.handlers.game_state import handle_join_campaign
from db.session import AsyncSessionLocal
from sqlalchemy import text

# Mock Logic
async def run_test():
    campaign_id = f"test_camp_{uuid.uuid4()}"
    user_id = f"test_user_{uuid.uuid4()}"

    print(f"Setting up test campaign: {campaign_id}")

    # 1. Setup DB Data
    async with AsyncSessionLocal() as db:
        # Create Dummy Campaign
        await db.execute(
            text("INSERT INTO campaigns (id, name, gm_id, status, api_key, api_key_verified, model) VALUES (:id, 'Test Campaign', :gm_id, 'active', 'test_key', 1, 'gemini-2.0-flash')"),
            {"id": campaign_id, "gm_id": user_id}
        )

        # Create Dummy User Profile (Ref constraint)
        # Check if profile exists or insert (Usually profile is created on auth, we might need to fake it or use existing if known?
        # But we generated a random UUID. We need to insert a profile.)
        await db.execute(
            text("INSERT INTO profiles (id, username) VALUES (:id, 'TestUser')"),
            {"id": user_id}
        )

        # Create Campaign Participant
        await db.execute(
            text("INSERT INTO campaign_participants (id, campaign_id, user_id, role, status) VALUES (:id, :cid, :uid, 'gm', 'active')"),
            {"id": str(uuid.uuid4()), "cid": campaign_id, "uid": user_id}
        )

        # Create Initial Game State
        initial_state = GameState(
            session_id=campaign_id,
            location=Location(name="Test Dungeon", description="A dark and spooky place."),
            party=[]
        )
        await db.execute(
            text("INSERT INTO game_states (id, campaign_id, turn_index, phase, state_data) VALUES (:id, :campaign_id, 0, 'exploration', :data)"),
            {"id": str(uuid.uuid4()), "campaign_id": campaign_id, "data": initial_state.model_dump_json()}
        )
        await db.commit()

    print("DB Setup Complete.")

    # 2. Mock Dependencies
    mock_sio = AsyncMock()
    mock_sio.emit = AsyncMock()
    mock_sio.enter_room = AsyncMock()

    connected_users = {}
    sid = "test_sid"

    # Mock DM Graph
    mock_graph = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = "Welcome to the Test Dungeon! It is very dark."
    mock_graph.ainvoke.return_value = {"messages": [mock_response]}

    # Patch get_dm_graph to return our mock
    with patch("app.socket.handlers.game_state.get_dm_graph", return_value=(mock_graph, None)):

        # 3. Run Handler
        print("Running handle_join_campaign...")
        await handle_join_campaign(sid, {"user_id": user_id, "campaign_id": campaign_id}, mock_sio, connected_users)

    # 4. Verify
    print("Verifying results...")

    # Check typing indicator
    # mock_sio.emit.assert_any_call('typing_indicator', {'sender_id': 'dm', 'is_typing': True}, room=campaign_id)

    # Check Chat Message
    found_msg = False
    for call in mock_sio.emit.call_args_list:
        args, kwargs = call
        if args[0] == 'chat_message':
            data = args[1]
            if data.get('sender_id') == 'dm' and "Welcome to the Test Dungeon" in data.get('content'):
                found_msg = True
                print("SUCCESS: DM Opening Message Emitted!")
                break

    if not found_msg:
        print("FAILURE: DM Opening Message NOT found in emit calls.")
        print("Calls:", mock_sio.emit.call_args_list)

    # 5. Cleanup
    async with AsyncSessionLocal() as db:
        await db.execute(text("DELETE FROM chat_messages WHERE campaign_id = :id"), {"id": campaign_id})
        await db.execute(text("DELETE FROM game_states WHERE campaign_id = :id"), {"id": campaign_id})
        await db.execute(text("DELETE FROM campaign_participants WHERE campaign_id = :id"), {"id": campaign_id})
        await db.execute(text("DELETE FROM campaigns WHERE id = :id"), {"id": campaign_id})
        await db.execute(text("DELETE FROM profiles WHERE id = :id"), {"id": user_id})
        await db.commit()
    print("Cleanup Complete.")

if __name__ == "__main__":
    asyncio.run(run_test())
