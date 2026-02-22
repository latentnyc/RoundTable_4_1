
import asyncio
import json
import os
import sys

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from sqlalchemy import select, desc
from app.models import GameState
from app.services.game_service import GameService
from db.schema import game_states
from db.session import AsyncSessionLocal

async def inspect_game_state():
    async with AsyncSessionLocal() as db:
        # Get the latest game state
        query = (
            select(game_states.c.campaign_id, game_states.c.state_data)
            .order_by(desc(game_states.c.updated_at))
            .limit(1)
        )
        result = await db.execute(query)
        row = result.fetchone()

        if not row:
            print("No game state found.")
            return

        campaign_id, state_data_str = row
        print(f"Campaign ID: {campaign_id}")

        try:
            state_data = json.loads(state_data_str)
            game_state = GameState(**state_data)

            print("\n--- Party ---")
            for p in game_state.party:
                print(f"Name: '{p.name}', ID: {p.id}, UserID: {p.user_id}")

            print("\n--- Enemies ---")
            for e in game_state.enemies:
                print(f"Name: '{e.name}', ID: {e.id}")

            print("\n--- NPCs ---")
            for n in game_state.npcs:
                print(f"Name: '{n.name}', ID: {n.id}")
                print(f"Data: {n.data}")

            # Simulate lookup
            attacker_name = "Ilium"
            target_name = "goblin"

            print(f"\n--- Testing GameService._find_char_by_name ---")
            actor = GameService._find_char_by_name(game_state, attacker_name)
            print(f"Lookup '{attacker_name}': {actor.name if actor else 'None'} ({type(actor).__name__})")

            target = GameService._find_char_by_name(game_state, target_name)
            print(f"Lookup '{target_name}': {target.name if target else 'None'} ({type(target).__name__})")


        except Exception as e:
            print(f"Error parsing game state: {e}")

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(inspect_game_state())
