"""Tests for Pydantic models: coordinates, entities, game state."""
import pytest
from app.models import Coordinates, Entity, Player, Enemy, NPC, GameState, Location, Vessel


class TestCoordinates:
    def test_distance_same_point(self, coords):
        a = coords(0, 0)
        assert a.distance_to(a) == 0

    def test_distance_adjacent(self, coords):
        a = coords(0, 0)
        b = coords(1, 0)
        assert a.distance_to(b) == 1

    def test_distance_symmetric(self, coords):
        a = coords(0, 0)
        b = coords(3, -2)
        assert a.distance_to(b) == b.distance_to(a)

    def test_distance_diagonal(self, coords):
        a = coords(0, 0)
        b = coords(2, -2)
        assert a.distance_to(b) == 2

    def test_line_to_same_point(self, coords):
        a = coords(0, 0)
        line = a.get_line_to(a)
        assert len(line) == 1
        assert line[0].q == 0 and line[0].r == 0

    def test_line_to_includes_endpoints(self, coords):
        a = coords(0, 0)
        b = coords(3, 0)
        line = a.get_line_to(b)
        assert line[0].q == a.q and line[0].r == a.r
        assert line[-1].q == b.q and line[-1].r == b.r

    def test_line_length_matches_distance(self, coords):
        a = coords(0, 0)
        b = coords(3, -1)
        line = a.get_line_to(b)
        assert len(line) == a.distance_to(b) + 1

    def test_s_invariant(self, coords):
        c = coords(3, -1)
        assert c.s == -3 - (-1)  # s = -q - r


class TestEntityValidation:
    def test_player_creation(self, player_factory):
        p = player_factory(name="Aria", role="Paladin", hp=30)
        assert p.name == "Aria"
        assert p.role == "Paladin"
        assert p.hp_current == 30
        assert p.hp_max == 30
        assert p.control_mode == "human"

    def test_enemy_creation(self, enemy_factory):
        e = enemy_factory(name="Goblin Boss", type="Goblin", hp=15)
        assert e.name == "Goblin Boss"
        assert e.type == "Goblin"
        assert e.hostile is True
        assert e.is_ai is True

    def test_npc_creation(self, npc_factory):
        n = npc_factory(name="Bartender", role="Innkeeper")
        assert n.name == "Bartender"
        assert n.hostile is False
        assert n.friendly is False

    def test_flatten_data_fields(self):
        """Entity model_validator should promote fields from 'data' dict."""
        e = Enemy(
            id="test",
            name="Orc",
            type="Orc",
            is_ai=True,
            hp_current=15,
            hp_max=15,
            position={"q": 0, "r": 0, "s": 0},
            data={"race": "Orc", "hostile": True},
        )
        assert e.race == "Orc"
        assert e.hostile is True

    def test_flatten_sheet_data_fields(self):
        """Player model_validator should promote fields from 'sheet_data' dict."""
        p = Player(
            id="test",
            name="Hero",
            role="Wizard",
            is_ai=False,
            hp_current=8,
            hp_max=8,
            position={"q": 0, "r": 0, "s": 0},
            sheet_data={"race": "Elf"},
        )
        assert p.race == "Elf"

    def test_entity_defaults(self, player_factory):
        p = player_factory()
        assert p.inventory == []
        assert p.conditions == []
        assert p.initiative == 0
        assert p.speed == 30


class TestGameState:
    def test_creation(self, game_state_factory):
        gs = game_state_factory()
        assert gs.phase == "exploration"
        assert len(gs.party) == 1
        assert len(gs.enemies) == 1
        assert gs.turn_index == 0

    def test_serialization_roundtrip(self, game_state_factory):
        gs = game_state_factory(num_players=2, num_enemies=3)
        data = gs.model_dump()
        gs2 = GameState(**data)
        assert len(gs2.party) == 2
        assert len(gs2.enemies) == 3
        assert gs2.session_id == gs.session_id

    def test_combat_state(self, game_state_factory, player_factory, enemy_factory):
        p = player_factory(name="Fighter")
        e = enemy_factory(name="Dragon")
        gs = game_state_factory(
            phase="combat",
            players=[p],
            enemies=[e],
        )
        gs.turn_order = [p.id, e.id]
        gs.active_entity_id = p.id
        assert gs.phase == "combat"
        assert len(gs.turn_order) == 2

    def test_vessel_in_state(self, game_state_factory, coords):
        gs = game_state_factory()
        v = Vessel(
            name="Corpse of Goblin",
            position=coords(1, 0),
            contents=["sword_01"],
            currency={"gp": 5, "sp": 0, "cp": 0, "pp": 0},
        )
        gs.vessels.append(v)
        assert len(gs.vessels) == 1
        assert gs.vessels[0].name == "Corpse of Goblin"


class TestHostility:
    """Tests for hostility field promotion and consistency."""

    def test_npc_hostile_from_data_dict(self):
        """NPC with hostile=True in data dict should have model field set."""
        n = NPC(
            id="test", name="Bandit", role="Enemy", is_ai=True,
            hp_current=10, hp_max=10,
            position={"q": 0, "r": 0, "s": 0},
            data={"hostile": True},
        )
        assert n.hostile is True
        assert n.friendly is False

    def test_npc_friendly_from_data_dict(self):
        """NPC with friendly=True in data dict should have model field set."""
        n = NPC(
            id="test", name="Shopkeeper", role="Merchant", is_ai=True,
            hp_current=10, hp_max=10,
            position={"q": 0, "r": 0, "s": 0},
            data={"friendly": True},
        )
        assert n.friendly is True
        assert n.hostile is False

    def test_npc_defaults_neutral(self):
        """NPC with no hostility flags should be neutral."""
        n = NPC(
            id="test", name="Villager", role="NPC", is_ai=True,
            hp_current=10, hp_max=10,
            position={"q": 0, "r": 0, "s": 0},
        )
        assert n.hostile is False
        assert n.friendly is False
        assert n.ally is False

    def test_explicit_field_overrides_data(self):
        """Explicit model field should take precedence over data dict."""
        n = NPC(
            id="test", name="Bandit", role="Enemy", is_ai=True,
            hp_current=10, hp_max=10,
            position={"q": 0, "r": 0, "s": 0},
            hostile=False,  # explicit
            data={"hostile": True},  # data dict says hostile
        )
        # Explicit field wins — flatten_data_fields only promotes if key not in values
        assert n.hostile is False

    def test_enemy_hostile_by_default(self):
        """Enemy model should default to hostile=True."""
        e = Enemy(
            id="test", name="Goblin", type="Goblin", is_ai=True,
            hp_current=7, hp_max=7,
            position={"q": 0, "r": 0, "s": 0},
        )
        assert e.hostile is True

    def test_npc_serialization_preserves_hostility(self):
        """Hostility should survive model_dump() -> NPC() round-trip."""
        n = NPC(
            id="test", name="Bandit", role="Enemy", is_ai=True,
            hp_current=10, hp_max=10,
            position={"q": 0, "r": 0, "s": 0},
            hostile=True, friendly=False, ally=False,
            data={"hostile": True},
        )
        data = n.model_dump()
        n2 = NPC(**data)
        assert n2.hostile is True
        assert n2.friendly is False


class TestLocation:
    def test_spawn_hexes_added_to_walkable(self, coords):
        """party_locations positions should be auto-added to walkable_hexes."""
        loc = Location(
            name="Test",
            description="Test",
            walkable_hexes=[coords(0, 0)],
            party_locations=[{"position": {"q": 5, "r": 5, "s": -10}}],
        )
        walkable_set = {(h.q, h.r, h.s) for h in loc.walkable_hexes}
        assert (5, 5, -10) in walkable_set
