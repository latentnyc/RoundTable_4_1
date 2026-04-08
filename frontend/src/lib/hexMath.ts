// Hexagon Math (Flat-topped hexes)
export const HEX_SIZE = 30; // Radius
export const HEX_HEIGHT = Math.sqrt(3) * HEX_SIZE;

// SVG path for a flat-topped hexagon centered at 0,0
export const HEX_PATH = `
  M ${HEX_SIZE} 0
  L ${HEX_SIZE / 2} ${HEX_HEIGHT / 2}
  L ${-HEX_SIZE / 2} ${HEX_HEIGHT / 2}
  L ${-HEX_SIZE} 0
  L ${-HEX_SIZE / 2} ${-HEX_HEIGHT / 2}
  L ${HEX_SIZE / 2} ${-HEX_HEIGHT / 2}
  Z
`;

// Calculate pixel coordinates from axial coordinates (q, r)
export const hexToPixel = (q: number, r: number) => {
    const x = HEX_SIZE * (3 / 2) * q;
    const y = HEX_SIZE * Math.sqrt(3) * (r + q / 2);
    return { x, y };
};

// Calculate hex distance (cube distance)
export const getHexDistance = (q1: number, r1: number, s1: number, q2: number, r2: number, s2: number) => {
    return Math.max(Math.abs(q1 - q2), Math.abs(r1 - r2), Math.abs(s1 - s2));
};

// Helper for finding neighbors inline
export const getHexNeighbors = (q: number, r: number, s: number) => [
    { q: q + 1, r: r, s: s - 1 },
    { q: q + 1, r: r - 1, s: s },
    { q: q, r: r - 1, s: s + 1 },
    { q: q - 1, r: r, s: s + 1 },
    { q: q - 1, r: r + 1, s: s },
    { q: q, r: r + 1, s: s - 1 }
];
