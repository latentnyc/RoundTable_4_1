import logging
from typing import List, Tuple, Set, Dict
from app.models import Coordinates

logger = logging.getLogger(__name__)

class PathfindingService:
    @staticmethod
    def check_line_of_sight(start_pos: Coordinates, target_pos: Coordinates, walkable_hexes: List[Coordinates]) -> bool:
        """
        Determines line of sight between two coordinates, checking that the path 
        only crosses walkable hexes.
        """
        if not start_pos or not target_pos:
            return False
            
        walkable_set = {(h.q, h.r, h.s) for h in walkable_hexes} if walkable_hexes else set()
        los_path = start_pos.get_line_to(target_pos)
        
        for point in los_path:
            if (point.q, point.r, point.s) not in walkable_set:
                return False
        return True

    @staticmethod
    def find_reachable_hexes(
        start_hex: Tuple[int, int, int], 
        max_move: int, 
        walkable_hexes: List[Coordinates], 
        obstacle_hexes: Set[Tuple[int, int, int]]
    ) -> Dict[Tuple[int, int, int], List[Tuple[int, int, int]]]:
        """
        Performs BFS to find reachable hexes within max_move based on walkable area and obstacles.
        Returns a dict mapping reachable hexes to the path taken to get there.
        """
        from app.utils.grid_utils import get_neighbors
        
        walkable = {(h.q, h.r, h.s) for h in walkable_hexes} if walkable_hexes else set()
        
        queue = [(start_hex, [])]
        visited = {start_hex: []}
        
        while queue:
            curr, path = queue.pop(0)
            
            if len(path) >= max_move:
                continue
                
            for n in get_neighbors(curr):
                if n in walkable and n not in obstacle_hexes:
                    if n not in visited or len(path) + 1 < len(visited[n]):
                        visited[n] = path + [n]
                        queue.append((n, path + [n]))
                        
        return visited
