import logging
from collections import deque
from typing import List, Tuple, Set, Dict, Optional
from app.models import Coordinates
from app.utils.grid_utils import get_neighbors, chebyshev_distance

logger = logging.getLogger(__name__)


class PathfindingService:
    """
    Square-grid (8-way Chebyshev) pathfinding. Single home for BFS / reachability /
    line-of-sight so the combat, follow, and interact paths share one implementation.
    Every step — orthogonal or diagonal — costs one cell (5 ft).
    """

    @staticmethod
    def check_line_of_sight(start_pos: Coordinates, target_pos: Coordinates, walkable_cells: List[Coordinates]) -> bool:
        """
        True if every cell on the supercover line between the two points is walkable.
        Because the line is a true supercover, a diagonal wall (both flanking cells
        blocked) correctly blocks LOS — no shooting/seeing through wall corners.
        """
        if not start_pos or not target_pos:
            return False
        walkable_set = {(h.x, h.y) for h in walkable_cells} if walkable_cells else set()
        for point in start_pos.get_line_to(target_pos):
            if (point.x, point.y) not in walkable_set:
                return False
        return True

    @staticmethod
    def find_reachable_cells(
        start_cell: Tuple[int, int],
        max_move: int,
        walkable_cells: List[Coordinates],
        obstacle_cells: Set[Tuple[int, int]],
    ) -> Dict[Tuple[int, int], List[Tuple[int, int]]]:
        """
        BFS over 8-connected neighbors. Uniform cost (1 per step incl. diagonals) is
        exactly Chebyshev movement. Returns {cell: path_to_cell} for every cell
        reachable within max_move steps (start cell included, with an empty path).
        """
        walkable = {(h.x, h.y) for h in walkable_cells} if walkable_cells else set()
        queue: deque = deque([(start_cell, [])])
        visited: Dict[Tuple[int, int], List[Tuple[int, int]]] = {start_cell: []}

        while queue:
            curr, path = queue.popleft()
            if len(path) >= max_move:
                continue
            for n in get_neighbors(curr):
                if n in walkable and n not in obstacle_cells:
                    if n not in visited or len(path) + 1 < len(visited[n]):
                        visited[n] = path + [n]
                        queue.append((n, path + [n]))

        return visited

    @staticmethod
    def find_best_cell_toward(
        start: Coordinates,
        target: Coordinates,
        max_move: int,
        walkable_cells: List[Coordinates],
        obstacle_cells: Set[Tuple[int, int]],
    ) -> Tuple[Optional[Tuple[int, int]], List[Tuple[int, int]]]:
        """
        Among cells reachable within max_move, pick the one that minimizes Chebyshev
        distance to target (ties broken by shortest path). Returns (best_cell, path),
        or (None, []) when no reachable cell gets strictly closer than staying put.
        """
        reachable = PathfindingService.find_reachable_cells(
            (start.x, start.y), max_move, walkable_cells, obstacle_cells
        )
        reachable.pop((start.x, start.y), None)
        if not reachable:
            return None, []

        start_dist = chebyshev_distance(start.x, start.y, target.x, target.y)
        best_cell, best_path = min(
            reachable.items(),
            key=lambda kv: (chebyshev_distance(kv[0][0], kv[0][1], target.x, target.y), len(kv[1])),
        )
        if chebyshev_distance(best_cell[0], best_cell[1], target.x, target.y) >= start_dist:
            return None, []
        return best_cell, best_path

    @staticmethod
    def find_best_cell_adjacent_to(
        start: Coordinates,
        target: Coordinates,
        max_move: int,
        walkable_cells: List[Coordinates],
        obstacle_cells: Set[Tuple[int, int]],
    ) -> Tuple[Optional[Tuple[int, int]], List[Tuple[int, int]]]:
        """
        Find the shortest path to any cell 8-adjacent to target (Chebyshev distance 1,
        excluding the target cell itself). Returns (cell, path) or (None, []).
        """
        reachable = PathfindingService.find_reachable_cells(
            (start.x, start.y), max_move, walkable_cells, obstacle_cells
        )
        adjacent = {
            cell: path
            for cell, path in reachable.items()
            if cell != (target.x, target.y)
            and chebyshev_distance(cell[0], cell[1], target.x, target.y) <= 1
        }
        if not adjacent:
            return None, []
        best_cell, best_path = min(adjacent.items(), key=lambda kv: len(kv[1]))
        return best_cell, best_path
