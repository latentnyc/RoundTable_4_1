"""Phase 0 regression tests: weapon attacks include the proficiency bonus (RAW), damage does
not, and CharacterSheet.get_mod resolves both full and abbreviated ability keys."""
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from game_engine.engine import GameEngine
from game_engine.character_sheet import CharacterSheet


def _attack(level: int):
    engine = GameEngine()
    actor = {"name": "Hero", "level": level, "stats": {"strength": 16, "dexterity": 10}, "equipment": []}
    target = {"name": "Dummy", "stats": {"dexterity": 10}, "hp": {"current": 10, "max": 10}, "ac": 5}
    return engine.resolve_action(actor, "attack", target, {"weapon_name": "Sword", "weapon_damage_dice": "1d6"})


def test_weapon_attack_includes_proficiency_at_level_1():
    # STR 16 -> +3 ability, level 1 -> +2 proficiency => +5 to hit.
    assert _attack(1)["attack_mod"] == 5


def test_weapon_attack_proficiency_scales_with_level():
    # level 5 -> +3 proficiency, +3 STR => +6 to hit.
    assert _attack(5)["attack_mod"] == 6


def test_get_mod_resolves_abbreviated_keys():
    cs = CharacterSheet({"name": "X", "stats": {"str": 16, "dex": 14}})
    assert cs.get_mod("strength") == 3
    assert cs.get_mod("dexterity") == 2


def test_get_mod_resolves_full_keys():
    cs = CharacterSheet({"name": "Y", "stats": {"strength": 20}})
    assert cs.get_mod("strength") == 5


def test_get_mod_unknown_stat_defaults_to_zero():
    cs = CharacterSheet({"name": "Z", "stats": {}})
    assert cs.get_mod("strength") == 0
