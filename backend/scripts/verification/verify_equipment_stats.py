import asyncio
from app.models import Player, Enemy
from game_engine.engine import GameEngine

def run_test():
    engine = GameEngine()

    alice_data = {
        "name": "Alice",
        "stats": {"strength": 16, "dexterity": 14}, # Str mod +3, Dex mod +2
        "sheet_data": {
            "equipment": [
                {
                    "name": "Longsword",
                    "type": "Weapon",
                    "data": {
                        "type": "Martial Melee",
                        "properties": [{"name": "Versatile"}],
                        "damage": { "damage_dice": "1d8" }
                    }
                },
                {
                    "name": "Chain Mail",
                    "type": "Armor",
                    "data": {
                        "type": "Heavy",
                        "armor_class": { "base": 16, "dex_bonus": False, "max_bonus": 0 }
                    }
                }
            ]
        },
        "hp_current": 20, "hp_max": 20
    }

    goblin_data = {
        "name": "Goblin Boss",
        "stats": {"strength": 8, "dexterity": 14},
        "data": {
            "equipment": [
                {
                    "name": "Scimitar",
                    "type": "Weapon",
                    "data": {
                        "type": "Martial Melee",
                        "properties": [{"name": "Finesse"}],
                        "damage": { "damage_dice": "1d6" }
                    }
                },
                {
                    "name": "Leather Armor",
                    "type": "Armor",
                    "data": {
                        "type": "Light",
                        "armor_class": { "base": 11, "dex_bonus": True, "max_bonus": None }
                    }
                }
            ]
        },
        "hp_current": 30, "hp_max": 30
    }

    print("\n--- Verifying Character Sheets ---")
    from game_engine.character_sheet import CharacterSheet
    alice = CharacterSheet(alice_data)
    goblin = CharacterSheet(goblin_data)

    print(f"Alice Weapon: {alice.get_weapon().get('name')} | AC: {alice.get_ac()}")
    print(f"Goblin Boss Weapon: {goblin.get_weapon().get('name')} | AC: {goblin.get_ac()}")

    assert alice.get_ac() == 16, f"Expected Alice AC 16, got {alice.get_ac()}"
    assert goblin.get_ac() == 13, f"Expected Goblin AC 13 (11+2 dex), got {goblin.get_ac()}"

    print("\n--- Simulating Combat ---")
    
    # Alice attacks Goblin
    res1 = engine.resolve_action(alice_data, "attack", target_data=goblin_data)
    print("Alice attacks:")
    print(res1['message'])
    print(f"Attack Mod Expected: +3 (str). Actual Mod used: {res1['attack_mod']}")
    # 1d8 damage
    
    # Goblin returns attack
    res2 = engine.resolve_action(goblin_data, "attack", target_data=alice_data)
    print("\nGoblin attacks:")
    print(res2['message'])
    print(f"Attack Mod Expected: +2 (dex finesse). Actual Mod used: {res2['attack_mod']}")
    # 1d6 damage
    
    print("\nVerification Succcessful!")

if __name__ == "__main__":
    run_test()
