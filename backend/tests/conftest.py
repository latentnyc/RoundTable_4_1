"""Shared test fixtures for RoundTable backend tests."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock
from app.models import (
    GameState, Player, Enemy, NPC, Location, Coordinates, Vessel
)


@pytest.fixture
def coords():
    """Factory for creating Coordinates."""
    def _make(q=0, r=0):
        return Coordinates(q=q, r=r, s=-q - r)
    return _make


@pytest.fixture
def player_factory(coords):
    """Factory for creating Player entities."""
    def _make(
        name="TestPlayer",
        role="Fighter",
        hp=20,
        position=None,
        is_ai=False,
        control_mode="human",
        **kwargs
    ):
        pos = position or coords(0, 0)
        return Player(
            id=str(uuid4()),
            name=name,
            role=role,
            is_ai=is_ai,
            hp_current=hp,
            hp_max=hp,
            ac=15,
            position=pos,
            control_mode=control_mode,
            **kwargs,
        )
    return _make


@pytest.fixture
def enemy_factory(coords):
    """Factory for creating Enemy entities."""
    def _make(
        name="TestEnemy",
        type="Goblin",
        hp=10,
        position=None,
        is_ai=True,
        hostile=True,
        **kwargs
    ):
        pos = position or coords(2, 0)
        return Enemy(
            id=str(uuid4()),
            name=name,
            type=type,
            is_ai=is_ai,
            hp_current=hp,
            hp_max=hp,
            ac=12,
            position=pos,
            hostile=hostile,
            **kwargs,
        )
    return _make


@pytest.fixture
def npc_factory(coords):
    """Factory for creating NPC entities."""
    def _make(
        name="TestNPC",
        role="Shopkeeper",
        hp=10,
        position=None,
        is_ai=True,
        **kwargs
    ):
        pos = position or coords(1, 1)
        return NPC(
            id=str(uuid4()),
            name=name,
            role=role,
            is_ai=is_ai,
            hp_current=hp,
            hp_max=hp,
            ac=10,
            position=pos,
            **kwargs,
        )
    return _make


@pytest.fixture
def location_factory(coords):
    """Factory for creating Locations."""
    def _make(name="Test Arena", hexes=None):
        walkable = hexes or [
            coords(q, r) for q in range(-3, 4) for r in range(-3, 4)
            if abs(-q - r) <= 3
        ]
        return Location(
            name=name,
            description=f"A {name.lower()} for testing.",
            walkable_hexes=walkable,
        )
    return _make


@pytest.fixture
def game_state_factory(player_factory, enemy_factory, location_factory):
    """Factory for creating a valid GameState."""
    def _make(
        num_players=1,
        num_enemies=1,
        phase="exploration",
        location=None,
        players=None,
        enemies=None,
    ):
        party = players if players is not None else [player_factory() for _ in range(num_players)]
        foes = enemies if enemies is not None else [enemy_factory() for _ in range(num_enemies)]
        loc = location or location_factory()

        return GameState(
            session_id=str(uuid4()),
            turn_index=0,
            phase=phase,
            location=loc,
            party=party,
            enemies=foes,
        )
    return _make


@pytest.fixture
def mock_sio():
    """Mock Socket.IO server."""
    sio = AsyncMock()
    sio.emit = AsyncMock()
    sio.enter_room = AsyncMock()
    sio.leave_room = AsyncMock()
    return sio


@pytest.fixture
def mock_db():
    """Mock async database session."""
    db = AsyncMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    db.close = AsyncMock()
    db.scalars = AsyncMock()
    return db
