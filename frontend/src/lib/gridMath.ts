// Square-grid math (8-way Chebyshev movement).
export const CELL_SIZE = 40; // edge length in pixels

// SVG path for a square cell centered at 0,0
export const CELL_PATH = `M ${-CELL_SIZE / 2} ${-CELL_SIZE / 2} h ${CELL_SIZE} v ${CELL_SIZE} h ${-CELL_SIZE} Z`;

// Calculate pixel coordinates from grid coordinates (x, y).
// Returns {px, py} to keep pixel space distinct from the {x, y} grid coordinate fields.
export const cellToPixel = (x: number, y: number) => {
    return { px: x * CELL_SIZE, py: y * CELL_SIZE };
};

// Chebyshev distance: every step (orthogonal or diagonal) counts as one cell.
export const chebyshevDistance = (x1: number, y1: number, x2: number, y2: number) => {
    return Math.max(Math.abs(x1 - x2), Math.abs(y1 - y2));
};

// The 8 neighbors of a cell: 4 orthogonal + 4 diagonal.
export const getNeighbors = (x: number, y: number) => [
    { x: x + 1, y: y },
    { x: x - 1, y: y },
    { x: x, y: y + 1 },
    { x: x, y: y - 1 },
    { x: x + 1, y: y + 1 },
    { x: x + 1, y: y - 1 },
    { x: x - 1, y: y + 1 },
    { x: x - 1, y: y - 1 },
];
