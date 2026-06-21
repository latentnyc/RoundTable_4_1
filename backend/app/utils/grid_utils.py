def chebyshev_distance(x1: int, y1: int, x2: int, y2: int) -> int:
    """
    Chebyshev (8-way) distance between two square cells. Every step — orthogonal
    or diagonal — counts as one cell (5 ft).
    """
    return max(abs(x1 - x2), abs(y1 - y2))

def get_neighbors(curr: tuple[int, int]) -> list[tuple[int, int]]:
    """
    Get the 8 surrounding neighbors of a square cell (x, y): 4 orthogonal + 4 diagonal.
    """
    x, y = curr
    return [
        (x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1),          # orthogonal
        (x + 1, y + 1), (x + 1, y - 1), (x - 1, y + 1), (x - 1, y - 1),  # diagonal
    ]
