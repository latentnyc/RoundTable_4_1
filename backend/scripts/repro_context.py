import asyncio
from typing import List
from app.services.context_builder import format_player_state
from app.models import Player

# Mock Player
class MockPlayer:
    def __init__(self, name, sheet_data):
        self.name = name
        self.race = "Human"
        self.role = "Fighter"
        self.level = 1
        self.hp_current = 10
        self.hp_max = 10
        self.ac = 15
        self.sheet_data = sheet_data
        self.status_effects = []

async def test_format():
    # Simulate DB data structure
    sheet_data = {
        "stats": {"str": 16, "dex": 14},
        "equipment": [
            {"name": "Longsword", "type": "Weapon"},
            {"name": "Shield", "type": "Armor"},
            {"name": "Potion of Healing", "type": "Item"}
        ],
        # "weapons": [], # Missing in this case
        # "inventory": [] # Missing in this case
    }

    p = MockPlayer("Hero", sheet_data)

    formatted = await format_player_state([p])
    print(formatted)

if __name__ == "__main__":
    asyncio.run(test_format())
