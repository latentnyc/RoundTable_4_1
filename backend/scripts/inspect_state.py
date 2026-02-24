
import asyncio
import json
import os
import sys

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from sqlalchemy import select, desc
from app.models import GameState
from app.services.game_service import GameService
from app.services.state_service import StateService
from db.schema import game_states
from db.session import AsyncSessionLocal

async def inspect_game_state():
    async with AsyncSessionLocal() as db:
        # Get the latest game state
        query = (
            select(game_states.c.campaign_id)
            .order_by(desc(game_states.c.updated_at))
            .limit(1)
        )
        result = await db.execute(query)
        row = result.fetchone()

        if not row:
            print("No game state found.")
            return

        campaign_id = row[0]
        print(f"Campaign ID: {campaign_id}")

        try:
            game_state = await StateService.get_game_state(campaign_id, db)

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

        except Exception as e:
            print(f"Fatal Error: {e}")
            import sys; sys.exit(1)

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(inspect_game_state())
