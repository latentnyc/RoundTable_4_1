"""Square-grid (8-way Chebyshev) pathfinding tests for the shared PathfindingService."""
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.models import Coordinates
from app.services.pathfinding_service import PathfindingService


def test_reachable_cells_along_corridor():
    # Straight 4-cell corridor.
    walkable = [Coordinates(x=x, y=0) for x in range(0, 4)]
    reachable = PathfindingService.find_reachable_cells(
        (0, 0), max_move=6, walkable_cells=walkable, obstacle_cells=set()
    )
    assert (3, 0) in reachable
    assert len(reachable[(3, 0)]) == 3  # three steps down the corridor


def test_diagonal_reachable_within_budget():
    # 5x5 open area: a cell two diagonal steps away is reachable in 2 moves (Chebyshev).
    walkable = [Coordinates(x=x, y=y) for x in range(0, 5) for y in range(0, 5)]
    reachable = PathfindingService.find_reachable_cells(
        (0, 0), max_move=2, walkable_cells=walkable, obstacle_cells=set()
    )
    assert (2, 2) in reachable
    assert len(reachable[(2, 2)]) == 2  # two diagonal steps, not four


def test_find_best_cell_adjacent_to_target():
    # An actor at (3,0) wants a cell adjacent to a target at (0,0), down a corridor.
    walkable = [Coordinates(x=x, y=0) for x in range(0, 4)]
    best_cell, path = PathfindingService.find_best_cell_adjacent_to(
        Coordinates(x=3, y=0), Coordinates(x=0, y=0),
        max_move=6, walkable_cells=walkable, obstacle_cells=set(),
    )
    assert best_cell == (1, 0)  # only walkable cell adjacent to (0,0)
    assert path[-1] == (1, 0)


def test_find_best_cell_toward_limited_by_budget():
    walkable = [Coordinates(x=x, y=0) for x in range(0, 6)]
    best_cell, _ = PathfindingService.find_best_cell_toward(
        Coordinates(x=5, y=0), Coordinates(x=0, y=0),
        max_move=2, walkable_cells=walkable, obstacle_cells=set(),
    )
    assert best_cell == (3, 0)  # closest it can get in 2 moves
