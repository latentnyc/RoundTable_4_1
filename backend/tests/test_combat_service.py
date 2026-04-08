"""Tests for CombatService: initiative, turn advancement, death handling."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.combat_service import CombatService
from app.models import GameState, Coordinates


class TestNextTurn:
    """Tests for CombatService.next_turn (turn advancement logic)."""

    @pytest.mark.asyncio
    async def test_advances_to_next_entity(self, game_state_factory, player_factory, enemy_factory, coords):
        """Turn should advance from index 0 to index 1."""
        p = player_factory(name="Fighter", position=coords(0, 0))
        e = enemy_factory(name="Goblin", position=coords(2, 0))
        gs = game_state_factory(phase="combat", players=[p], enemies=[e])
        gs.turn_order = [p.id, e.id]
        gs.turn_index = 0
        gs.active_entity_id = p.id

        with patch("app.services.combat_service.StateService") as mock_ss:
            mock_ss.get_game_state = AsyncMock(return_value=gs)
            mock_ss.save_game_state = AsyncMock()

            active_id, new_gs = await CombatService.next_turn("test_camp", MagicMock(), gs, commit=False)

        assert active_id == e.id
        assert new_gs.turn_index == 1
        assert new_gs.has_moved_this_turn is False
        assert new_gs.has_acted_this_turn is False

    @pytest.mark.asyncio
    async def test_wraps_around_turn_order(self, game_state_factory, player_factory, enemy_factory, coords):
        """Turn should wrap from last entity back to first."""
        p = player_factory(name="Fighter", position=coords(0, 0))
        e = enemy_factory(name="Goblin", position=coords(2, 0))
        gs = game_state_factory(phase="combat", players=[p], enemies=[e])
        gs.turn_order = [p.id, e.id]
        gs.turn_index = 1  # Currently goblin's turn
        gs.active_entity_id = e.id

        active_id, new_gs = await CombatService.next_turn("test_camp", MagicMock(), gs, commit=False)

        assert active_id == p.id
        assert new_gs.turn_index == 0

    @pytest.mark.asyncio
    async def test_skips_dead_entities(self, game_state_factory, player_factory, enemy_factory, coords):
        """Dead entities (hp <= 0) should be skipped in turn order."""
        p = player_factory(name="Fighter", position=coords(0, 0))
        dead_e = enemy_factory(name="Dead Goblin", hp=0, position=coords(1, 0))
        alive_e = enemy_factory(name="Alive Goblin", hp=10, position=coords(2, 0))

        gs = game_state_factory(phase="combat", players=[p], enemies=[dead_e, alive_e])
        gs.turn_order = [p.id, dead_e.id, alive_e.id]
        gs.turn_index = 0
        gs.active_entity_id = p.id

        active_id, new_gs = await CombatService.next_turn("test_camp", MagicMock(), gs, commit=False)

        assert active_id == alive_e.id
        assert new_gs.turn_index == 2  # Skipped index 1 (dead goblin)

    @pytest.mark.asyncio
    async def test_all_dead_returns_none(self, game_state_factory, player_factory, enemy_factory, coords):
        """If all entities in turn order are dead, returns (None, None)."""
        p = player_factory(name="Fighter", hp=0, position=coords(0, 0))
        e = enemy_factory(name="Goblin", hp=0, position=coords(2, 0))

        gs = game_state_factory(phase="combat", players=[p], enemies=[e])
        gs.turn_order = [p.id, e.id]
        gs.turn_index = 0

        active_id, new_gs = await CombatService.next_turn("test_camp", MagicMock(), gs, commit=False)

        assert active_id is None
        assert new_gs is None

    @pytest.mark.asyncio
    async def test_empty_turn_order_returns_none(self, game_state_factory):
        """Empty turn order returns (None, None)."""
        gs = game_state_factory(phase="combat")
        gs.turn_order = []

        active_id, new_gs = await CombatService.next_turn("test_camp", MagicMock(), gs, commit=False)

        assert active_id is None
        assert new_gs is None


class TestHandleEntityDeath:
    """Tests for CombatService._handle_entity_death."""

    @pytest.mark.asyncio
    async def test_creates_vessel_on_death(self, game_state_factory, player_factory, enemy_factory, coords, mock_db):
        """Killing an enemy should create a corpse vessel."""
        p = player_factory(name="Fighter", position=coords(0, 0))
        e = enemy_factory(name="Goblin", type="Goblin", hp=0, position=coords(1, 0))

        gs = game_state_factory(phase="combat", players=[p], enemies=[e])
        gs.turn_order = [p.id, e.id]

        death_msg, updates = await CombatService._handle_entity_death(
            "test_camp", e, gs, is_npc=False, db=mock_db, commit=False
        )

        assert "Goblin has died" in death_msg
        assert len(gs.vessels) == 1
        assert "CORPSE" in gs.vessels[0].name.upper()
        assert e.id not in gs.turn_order

    @pytest.mark.asyncio
    async def test_combat_ends_when_all_enemies_dead(self, game_state_factory, player_factory, enemy_factory, coords, mock_db):
        """Combat should end in victory when last enemy dies."""
        p = player_factory(name="Fighter", position=coords(0, 0))
        e = enemy_factory(name="Goblin", hp=0, position=coords(1, 0))

        gs = game_state_factory(phase="combat", players=[p], enemies=[e])
        gs.turn_order = [p.id, e.id]

        death_msg, updates = await CombatService._handle_entity_death(
            "test_camp", e, gs, is_npc=False, db=mock_db, commit=False
        )

        assert updates.get('combat_end') == 'victory'
        assert gs.phase == 'exploration'
        assert "VICTORY" in death_msg

    @pytest.mark.asyncio
    async def test_defeat_when_all_party_dead(self, game_state_factory, player_factory, enemy_factory, coords, mock_db):
        """Game should end in defeat when last party member dies."""
        p = player_factory(name="Fighter", hp=0, position=coords(0, 0))
        e = enemy_factory(name="Goblin", hp=10, position=coords(1, 0))

        gs = game_state_factory(phase="combat", players=[p], enemies=[e])
        gs.turn_order = [p.id, e.id]

        # Simulate player death
        death_msg, updates = await CombatService._handle_entity_death(
            "test_camp", p, gs, is_npc=False, db=mock_db, commit=False
        )

        assert updates.get('combat_end') == 'defeat'
        assert "DEFEAT" in death_msg


class TestHostilityInCombat:
    """Tests for hostility changes during combat."""

    @pytest.mark.asyncio
    async def test_combat_ends_when_last_hostile_npc_dies(self, game_state_factory, player_factory, npc_factory, coords, mock_db):
        """Combat should end when the last hostile NPC dies (using model field)."""
        p = player_factory(name="Fighter", position=coords(0, 0))
        hostile_npc = npc_factory(name="Bandit", position=coords(1, 0), hostile=True)

        gs = game_state_factory(phase="combat", players=[p], enemies=[])
        gs.npcs = [hostile_npc]
        gs.turn_order = [p.id, hostile_npc.id]

        hostile_npc.hp_current = 0
        death_msg, updates = await CombatService._handle_entity_death(
            "test_camp", hostile_npc, gs, is_npc=True, db=mock_db, commit=False
        )

        assert updates.get('combat_end') == 'victory'
        assert gs.phase == 'exploration'

    @pytest.mark.asyncio
    async def test_combat_continues_with_remaining_hostile_npcs(self, game_state_factory, player_factory, npc_factory, coords, mock_db):
        """Combat should NOT end if other hostile NPCs are still alive."""
        p = player_factory(name="Fighter", position=coords(0, 0))
        npc1 = npc_factory(name="Bandit 1", position=coords(1, 0), hostile=True)
        npc2 = npc_factory(name="Bandit 2", position=coords(2, 0), hostile=True)

        gs = game_state_factory(phase="combat", players=[p], enemies=[])
        gs.npcs = [npc1, npc2]
        gs.turn_order = [p.id, npc1.id, npc2.id]

        npc1.hp_current = 0
        death_msg, updates = await CombatService._handle_entity_death(
            "test_camp", npc1, gs, is_npc=True, db=mock_db, commit=False
        )

        assert 'combat_end' not in updates
        assert gs.phase == 'combat'
