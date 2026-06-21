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

    def test_distance_diagonal_is_chebyshev(self, coords):
        # 8-way Chebyshev: a pure diagonal of 3 costs 3 (not 6).
        a = coords(0, 0)
        b = coords(3, 3)
        assert a.distance_to(b) == 3

    def test_distance_mixed_is_chebyshev(self, coords):
        a = coords(0, 0)
        b = coords(3, 1)
        assert a.distance_to(b) == 3

    def test_line_to_same_point(self, coords):
        a = coords(0, 0)
        line = a.get_line_to(a)
        assert len(line) == 1
        assert line[0].x == 0 and line[0].y == 0

    def test_line_to_includes_endpoints(self, coords):
        a = coords(0, 0)
        b = coords(3, 0)
        line = a.get_line_to(b)
        assert line[0].x == a.x and line[0].y == a.y
        assert line[-1].x == b.x and line[-1].y == b.y

    def test_orthogonal_line_length(self, coords):
        # Axis-aligned lines are exactly distance + 1 cells, all on the same row.
        a = coords(0, 0)
        b = coords(4, 0)
        line = a.get_line_to(b)
        assert len(line) == a.distance_to(b) + 1
        assert all(c.y == 0 for c in line)

    def test_diagonal_line_is_supercover(self, coords):
        # A diagonal supercover includes both flanking cells at each corner crossing,
        # so it is fatter than distance + 1 and still contains both endpoints.
        a = coords(0, 0)
        b = coords(3, 3)
        line = a.get_line_to(b)
        cells = {(c.x, c.y) for c in line}
        assert (0, 0) in cells and (3, 3) in cells
        assert len(line) > a.distance_to(b) + 1
        # Both flank cells of the first corner crossing are present.
        assert (1, 0) in cells and (0, 1) in cells


class TestLineOfSight:
    def test_clear_diagonal_has_los(self, coords):
        from app.services.pathfinding_service import PathfindingService
        walkable = [coords(x, y) for x in range(0, 3) for y in range(0, 3)]
        assert PathfindingService.check_line_of_sight(coords(0, 0), coords(2, 2), walkable) is True

    def test_diagonal_wall_blocks_los(self, coords):
        from app.services.pathfinding_service import PathfindingService
        # Remove the two cells flanking the (0,0)->(1,1) corner: a diagonal wall.
        # True supercover routes through a flank cell, so LOS must be blocked.
        walkable = [coords(x, y) for x in range(0, 3) for y in range(0, 3)
                    if (x, y) not in {(1, 0), (0, 1)}]
        assert PathfindingService.check_line_of_sight(coords(0, 0), coords(2, 2), walkable) is False


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
            position={"x": 0, "y": 0},
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
            position={"x": 0, "y": 0},
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
            position={"x": 0, "y": 0},
            data={"hostile": True},
        )
        assert n.hostile is True
        assert n.friendly is False

    def test_npc_friendly_from_data_dict(self):
        """NPC with friendly=True in data dict should have model field set."""
        n = NPC(
            id="test", name="Shopkeeper", role="Merchant", is_ai=True,
            hp_current=10, hp_max=10,
            position={"x": 0, "y": 0},
            data={"friendly": True},
        )
        assert n.friendly is True
        assert n.hostile is False

    def test_npc_defaults_neutral(self):
        """NPC with no hostility flags should be neutral."""
        n = NPC(
            id="test", name="Villager", role="NPC", is_ai=True,
            hp_current=10, hp_max=10,
            position={"x": 0, "y": 0},
        )
        assert n.hostile is False
        assert n.friendly is False
        assert n.ally is False

    def test_explicit_field_overrides_data(self):
        """Explicit model field should take precedence over data dict."""
        n = NPC(
            id="test", name="Bandit", role="Enemy", is_ai=True,
            hp_current=10, hp_max=10,
            position={"x": 0, "y": 0},
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
            position={"x": 0, "y": 0},
        )
        assert e.hostile is True

    def test_npc_serialization_preserves_hostility(self):
        """Hostility should survive model_dump() -> NPC() round-trip."""
        n = NPC(
            id="test", name="Bandit", role="Enemy", is_ai=True,
            hp_current=10, hp_max=10,
            position={"x": 0, "y": 0},
            hostile=True, friendly=False, ally=False,
            data={"hostile": True},
        )
        data = n.model_dump()
        n2 = NPC(**data)
        assert n2.hostile is True
        assert n2.friendly is False


class TestLocation:
    def test_spawn_cells_added_to_walkable(self, coords):
        """party_locations positions should be auto-added to walkable_cells."""
        loc = Location(
            name="Test",
            description="Test",
            walkable_cells=[coords(0, 0)],
            party_locations=[{"position": {"x": 5, "y": 5}}],
        )
        walkable_set = {(h.x, h.y) for h in loc.walkable_cells}
        assert (5, 5) in walkable_set
