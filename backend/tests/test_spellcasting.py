import asyncio
from unittest.mock import MagicMock, AsyncMock
from app.services.game_service import GameService
from app.services.combat_service import CombatService
from game_engine.engine import GameEngine

async def run_tests():
    print("--- Testing Spellcasting ---")

    # 1. Mock DB and GameState
    mock_db = AsyncMock()

    class MockPartyMember:
        def __init__(self, name, id):
            self.id = id
            self.name = name
            self.role = "Wizard"
            self.hp_current = 10
            self.hp_max = 10
            self.position = [0,0]
            self.inventory = []
            self.data = {
                "stats": {"intelligence": 16, "dexterity": 14}, # +3 Int, +2 Dex
                "level": 1
            }
            # Add known spells
            self.sheet_data = {
                "stats": self.data["stats"],
                "spells": [
                    {
                        "name": "Firebolt",
                        "index": "firebolt",
                        "data": {
                            "name": "Firebolt",
                            "level": 0,
                            "attack_type": "ranged",
                            "damage": {
                                "damage_type": {"name": "Fire"},
                                "damage_at_character_level": {"1": "1d10", "5": "2d10"}
                            }
                        }
                    },
                    {
                        "name": "Fireball",
                        "index": "fireball",
                        "data": {
                            "name": "Fireball",
                            "level": 3,
                            "save": {"dc_type": {"index": "dexterity"}},
                            "damage": {
                                "damage_type": {"name": "Fire"},
                                "damage_at_slot_level": {"3": "8d6"}
                            }
                        }
                    },
                    {
                        "name": "Cure Wounds",
                        "data": {
                            "name": "Cure Wounds",
                            "level": 1,
                            "heal_at_slot_level": {"1": "1d8"}
                        }
                    }
                ]
            }

        def model_dump(self):
             return self.dict()

        def dict(self):
             return {
                 "id": self.id,
                 "name": self.name,
                 "role": self.role,
                 "hp": {"current": self.hp_current, "max": self.hp_max},
                 "data": self.data,
                 "equipment": [],
                 "spells": self.sheet_data["spells"]
             }

    class MockEnemy:
         def __init__(self, name, id):
            self.id = id
            self.name = name
            self.type = "Goblin"
            self.hp_current = 20
            self.hp_max = 20
            self.position = [0,1]
            self.inventory = []
            self.data = {"armor_class": 12, "stats": {"dexterity": 14}} # +2 Dex Save, AC 12
         def dict(self):
             return {
                 "id": self.id,
                 "name": self.name,
                 "hp": {"current": self.hp_current, "max": self.hp_max},
                 "data": self.data
             }

    class MockGameState:
        def __init__(self):
            self.id = "test_camp"
            self.phase = "combat"
            self.party = [MockPartyMember("Gandalf", "p1")]
            self.enemies = [MockEnemy("Goblin", "e1")]
            self.npcs = []
            self.vessels = []
            self.turn_order = ["p1", "e1"]

    game_state = MockGameState()

    # Mock get_game_state
    async def mock_get_gs(*args): return game_state
    GameService.get_game_state = mock_get_gs
    GameService.update_char_hp = AsyncMock()
    GameService.save_game_state = AsyncMock()

    # 2. Test Attack Spell
    print("\n[TEST] Casting Firebolt (Attack Roll)")
    res_attack = await CombatService.resolution_cast("test_camp", "p1", "Gandalf", "Firebolt", "Goblin", mock_db)
    print(res_attack["message"])
    print(f"Success? {res_attack.get('success')}")

    # 3. Test Save Spell
    print("\n[TEST] Casting Fireball (Saving Throw)")
    res_save = await CombatService.resolution_cast("test_camp", "p1", "Gandalf", "Fireball", "Goblin", mock_db)
    print(res_save["message"])

    # 4. Test Healing Spell
    print("\n[TEST] Casting Cure Wounds (Healing)")
    # Damage party member first
    game_state.party[0].hp_current = 5
    res_heal = await CombatService.resolution_cast("test_camp", "p1", "Gandalf", "Cure Wounds", "Gandalf", mock_db)
    print(res_heal["message"])

if __name__ == "__main__":
    asyncio.run(run_tests())
