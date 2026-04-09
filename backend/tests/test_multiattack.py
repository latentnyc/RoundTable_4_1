"""Tests for monster multiattack parsing and resolution."""
import pytest
from app.services.ai_turn_service import AITurnService
from app.models import NPC, Coordinates


class TestMultiattackParsing:
    """Test _get_multiattack_actions parses SRD multiattack data correctly."""

    def _make_npc_with_actions(self, actions):
        return NPC(
            id="test", name="TestMonster", role="Enemy", is_ai=True,
            hp_current=22, hp_max=22, ac=13,
            position=Coordinates(q=0, r=0, s=0),
            data={"actions": actions},
        )

    def test_no_actions_returns_empty(self):
        npc = self._make_npc_with_actions([])
        result = AITurnService._get_multiattack_actions(npc)
        assert result == []

    def test_no_multiattack_returns_empty(self):
        npc = self._make_npc_with_actions([
            {"name": "Bite", "attack_bonus": 4, "damage": [{"damage_dice": "1d6+2"}]}
        ])
        result = AITurnService._get_multiattack_actions(npc)
        assert result == []

    def test_actions_format_simple(self):
        """Thug-style: 2x Mace."""
        npc = self._make_npc_with_actions([
            {"name": "Multiattack", "multiattack_type": "actions", "damage": [],
             "actions": [{"action_name": "Mace", "count": "2", "type": "melee"}]},
            {"name": "Mace", "attack_bonus": 4, "damage": [{"damage_dice": "1d6+2"}]},
        ])
        result = AITurnService._get_multiattack_actions(npc)
        assert len(result) == 2
        assert result[0]["name"] == "Mace"
        assert result[1]["name"] == "Mace"

    def test_actions_format_mixed(self):
        """Brown Bear-style: 1x Bite + 1x Claws."""
        npc = self._make_npc_with_actions([
            {"name": "Multiattack", "multiattack_type": "actions", "damage": [],
             "actions": [
                 {"action_name": "Bite", "count": "1", "type": "melee"},
                 {"action_name": "Claws", "count": "1", "type": "melee"},
             ]},
            {"name": "Bite", "attack_bonus": 5, "damage": [{"damage_dice": "1d8+4"}]},
            {"name": "Claws", "attack_bonus": 5, "damage": [{"damage_dice": "2d6+4"}]},
        ])
        result = AITurnService._get_multiattack_actions(npc)
        assert len(result) == 2
        assert result[0]["name"] == "Bite"
        assert result[1]["name"] == "Claws"

    def test_action_options_format(self):
        """Lizardfolk-style: choose from option sets."""
        npc = self._make_npc_with_actions([
            {"name": "Multiattack", "multiattack_type": "action_options", "damage": [],
             "action_options": {
                 "choose": 1, "type": "action",
                 "from": {"option_set_type": "options_array", "options": [
                     {"option_type": "multiple", "items": [
                         {"option_type": "action", "action_name": "Bite", "count": 1, "type": "melee"},
                         {"option_type": "action", "action_name": "Heavy Club", "count": 1, "type": "melee"},
                     ]},
                 ]}
             }},
            {"name": "Bite", "attack_bonus": 4, "damage": [{"damage_dice": "1d6+2"}]},
            {"name": "Heavy Club", "attack_bonus": 4, "damage": [{"damage_dice": "1d6+2"}]},
        ])
        result = AITurnService._get_multiattack_actions(npc)
        assert len(result) == 2
        names = {r["name"] for r in result}
        assert "Bite" in names
        assert "Heavy Club" in names

    def test_missing_action_name_skipped(self):
        """If multiattack references an action that doesn't exist, skip it."""
        npc = self._make_npc_with_actions([
            {"name": "Multiattack", "multiattack_type": "actions", "damage": [],
             "actions": [
                 {"action_name": "Bite", "count": "1", "type": "melee"},
                 {"action_name": "Nonexistent", "count": "1", "type": "melee"},
             ]},
            {"name": "Bite", "attack_bonus": 4, "damage": [{"damage_dice": "1d6+2"}]},
        ])
        result = AITurnService._get_multiattack_actions(npc)
        assert len(result) == 1
        assert result[0]["name"] == "Bite"

    def test_player_no_multiattack(self, player_factory):
        """Player entities should never have multiattack."""
        p = player_factory()
        result = AITurnService._get_multiattack_actions(p)
        assert result == []
