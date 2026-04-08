def hex_distance(q1: int, r1: int, s1: int, q2: int, r2: int, s2: int) -> int:
    """
    Calculate the cube distance between two hexes.
    """
    return max(abs(q1 - q2), abs(r1 - r2), abs(s1 - s2))

def get_neighbors(curr: tuple[int, int, int]) -> list[tuple[int, int, int]]:
    """
    Get the 6 surrounding neighbors of a hex coordinate tuple (q,r,s).
    """
    return [
        (curr[0]+1, curr[1], curr[2]-1),
        (curr[0]+1, curr[1]-1, curr[2]),
        (curr[0], curr[1]-1, curr[2]+1),
        (curr[0]-1, curr[1], curr[2]+1),
        (curr[0]-1, curr[1]+1, curr[2]),
        (curr[0], curr[1]+1, curr[2]-1)
    ]
