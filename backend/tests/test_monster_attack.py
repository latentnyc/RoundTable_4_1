import sys
import os
import json
import asyncio

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from game_engine.character_sheet import CharacterSheet
from game_engine.engine import GameEngine

monster_data = {
    "name": "Grimtooth",
    "type": "Goblin Boss",
    "stats": {"strength": 10, "dexterity": 14, "constitution": 10, "intelligence": 10, "wisdom": 8, "charisma": 10},
    "data": {
        "armor_class": [{"type": "armor", "value": 17}],
        "actions": [
            {
                "name": "Scimitar",
                "desc": "Melee Weapon Attack: +4 to hit, reach 5 ft., one target. Hit: 5 (1d6 + 2) slashing damage.",
                "damage": [
                    {"damage_dice": "1d6+2"}
                ]
            }
        ]
    }
}

target_data = {
    "name": "Oliar",
    "stats": {"strength": 16, "dexterity": 14},
    "hp": {"current": 10, "max": 10},
    "ac": 16,
    "equipment": [
        {"type": "Armor", "data": {"type": "Heavy", "armor_class": {"base": 16, "dex_bonus": False}}}
    ]
}

engine = GameEngine()

def run_test():
    actor = CharacterSheet(monster_data)
    target = CharacterSheet(target_data)
    
    print("Monster Weapon:", actor.get_weapon())
    print("\nMonster AC:", actor.get_ac())
    print("\nTarget AC:", target.get_ac())
    
    res = engine.resolve_action(monster_data, "attack", target_data)
    print("\nAttack Result:")
    print(res.get('message'))

if __name__ == "__main__":
    run_test()
