"""Tests for spell service: Tier A whitelist, SRD normalization, engine compatibility."""
import pytest
from app.services.spell_service import (
    normalize_spell_for_engine, is_tier_a, TIER_A_SPELLS, _extract_damage_dice
)
from game_engine.engine import GameEngine
from game_engine.character_sheet import CharacterSheet


class TestTierAWhitelist:
    def test_fire_bolt_is_tier_a(self):
        assert is_tier_a("fire-bolt")

    def test_magic_missile_is_tier_a(self):
        assert is_tier_a("magic-missile")

    def test_cure_wounds_is_tier_a(self):
        assert is_tier_a("cure-wounds")

    def test_fireball_not_tier_a(self):
        assert not is_tier_a("fireball")

    def test_hold_person_not_tier_a(self):
        assert not is_tier_a("hold-person")

    def test_tier_a_count(self):
        assert len(TIER_A_SPELLS) == 16


class TestNormalizeSpell:
    def test_fire_bolt_normalization(self):
        srd_spell = {
            "index": "fire-bolt",
            "name": "Fire Bolt",
            "level": 0,
            "attack_type": "ranged",
            "range": "120 feet",
            "damage": {
                "damage_type": {"name": "Fire"},
                "damage_at_character_level": {"1": "1d10", "5": "2d10", "11": "3d10", "17": "4d10"}
            },
            "school": {"name": "Evocation"},
            "casting_time": "1 action",
        }
        result = normalize_spell_for_engine(srd_spell)

        assert result["name"] == "Fire Bolt"
        assert result["data"]["attack_type"] == "ranged"
        assert result["data"]["range"] == "120 feet"
        assert result["data"]["damage"]["damage_dice"] == "1d10"
        assert result["data"]["damage"]["damage_type"]["name"] == "Fire"

    def test_sacred_flame_normalization(self):
        srd_spell = {
            "index": "sacred-flame",
            "name": "Sacred Flame",
            "level": 0,
            "range": "60 feet",
            "dc": {"dc_type": {"index": "dexterity", "name": "DEX"}},
            "damage": {
                "damage_type": {"name": "Radiant"},
                "damage_at_character_level": {"1": "1d8", "5": "2d8"}
            },
        }
        result = normalize_spell_for_engine(srd_spell)

        assert result["data"]["save"]["dc_type"]["index"] == "dexterity"
        assert result["data"]["damage"]["damage_dice"] == "1d8"
        assert "attack_type" not in result["data"]

    def test_magic_missile_special_case(self):
        srd_spell = {
            "index": "magic-missile",
            "name": "Magic Missile",
            "level": 1,
            "range": "120 feet",
            "damage": {
                "damage_type": {"name": "Force"},
                "damage_at_slot_level": {"1": "3d4+3", "2": "4d4+4"}
            },
        }
        result = normalize_spell_for_engine(srd_spell)

        # Magic Missile is special-cased to 3d4+3 auto-hit
        assert result["data"]["damage"]["damage_dice"] == "3d4+3"
        assert result["data"]["damage"]["damage_type"]["name"] == "Force"
        # Should NOT have attack_type or save — triggers auto-hit branch
        assert "attack_type" not in result["data"]
        assert "save" not in result["data"]

    def test_cure_wounds_normalization(self):
        srd_spell = {
            "index": "cure-wounds",
            "name": "Cure Wounds",
            "level": 1,
            "range": "Touch",
            "heal_at_slot_level": {"1": "1d8", "2": "2d8", "3": "3d8"},
        }
        result = normalize_spell_for_engine(srd_spell)

        assert result["data"]["heal_at_slot_level"]["1"] == "1d8"
        assert result["data"]["range"] == "Touch"

    def test_blight_save_damage(self):
        srd_spell = {
            "index": "blight",
            "name": "Blight",
            "level": 4,
            "range": "30 feet",
            "dc": {"dc_type": {"index": "constitution", "name": "CON"}},
            "damage": {
                "damage_type": {"name": "Necrotic"},
                "damage_at_slot_level": {"4": "8d8", "5": "9d8"}
            },
        }
        result = normalize_spell_for_engine(srd_spell)

        assert result["data"]["save"]["dc_type"]["index"] == "constitution"
        assert result["data"]["damage"]["damage_dice"] == "8d8"


class TestEngineWithNormalizedSpells:
    """Test that normalized spells actually resolve correctly in the GameEngine."""

    def _make_actor(self, role="Wizard"):
        return {
            "name": "TestCaster",
            "role": role,
            "stats": {"str": 8, "dex": 14, "con": 13, "int": 16, "wis": 12, "cha": 10},
            "hp_current": 20, "hp_max": 20,
            "level": 1,
            "equipment": [],
        }

    def _make_target(self):
        return {
            "name": "TestTarget",
            "stats": {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10},
            "hp_current": 20, "hp_max": 20,
            "ac": 12,
            "equipment": [],
        }

    def test_fire_bolt_resolves_with_attack_roll(self):
        spell = normalize_spell_for_engine({
            "index": "fire-bolt", "name": "Fire Bolt", "level": 0,
            "attack_type": "ranged", "range": "120 feet",
            "damage": {"damage_type": {"name": "Fire"}, "damage_at_character_level": {"1": "1d10"}},
        })
        engine = GameEngine()
        result = engine.resolve_action(self._make_actor(), "cast", self._make_target(), {"spell_data": spell})

        assert result["success"] is True
        assert "Spell Attack Roll" in result["message"]
        # Should have rolled to hit, not auto-hit
        assert "Auto-Hit" not in result["message"]

    def test_sacred_flame_resolves_with_save(self):
        spell = normalize_spell_for_engine({
            "index": "sacred-flame", "name": "Sacred Flame", "level": 0,
            "range": "60 feet",
            "dc": {"dc_type": {"index": "dexterity", "name": "DEX"}},
            "damage": {"damage_type": {"name": "Radiant"}, "damage_at_character_level": {"1": "1d8"}},
        })
        engine = GameEngine()
        result = engine.resolve_action(
            self._make_actor("Cleric"), "cast", self._make_target(), {"spell_data": spell}
        )

        assert result["success"] is True
        assert "Saving Throw" in result["message"]

    def test_magic_missile_resolves_as_auto_hit(self):
        spell = normalize_spell_for_engine({
            "index": "magic-missile", "name": "Magic Missile", "level": 1,
            "range": "120 feet",
            "damage": {"damage_type": {"name": "Force"}, "damage_at_slot_level": {"1": "3d4+3"}},
        })
        engine = GameEngine()
        result = engine.resolve_action(self._make_actor(), "cast", self._make_target(), {"spell_data": spell})

        assert result["success"] is True
        assert "Auto-Hit" in result["message"]
        assert result["damage_total"] > 0

    def test_cure_wounds_heals_target(self):
        spell = normalize_spell_for_engine({
            "index": "cure-wounds", "name": "Cure Wounds", "level": 1,
            "range": "Touch",
            "heal_at_slot_level": {"1": "1d8", "2": "2d8"},
        })
        target = self._make_target()
        target["hp_current"] = 5  # injured

        engine = GameEngine()
        result = engine.resolve_action(
            self._make_actor("Cleric"), "cast", target, {"spell_data": spell}
        )

        assert result["success"] is True
        assert "Healing" in result["message"] or "HP" in result["message"]
        assert result.get("target_hp_remaining", 5) > 5  # should have healed


class TestDamageExtraction:
    def test_cantrip_damage_at_char_level(self):
        dice = _extract_damage_dice(
            {"damage_at_character_level": {"1": "1d10", "5": "2d10"}},
            0, "fire-bolt"
        )
        assert dice == "1d10"

    def test_leveled_spell_damage_at_slot(self):
        dice = _extract_damage_dice(
            {"damage_at_slot_level": {"4": "8d8", "5": "9d8"}},
            4, "blight"
        )
        assert dice == "8d8"

    def test_fallback_to_damage_dice(self):
        dice = _extract_damage_dice(
            {"damage_dice": "2d6"},
            1, "test"
        )
        assert dice == "2d6"
