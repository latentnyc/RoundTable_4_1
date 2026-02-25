import { useMemo, useState, useEffect } from 'react';
import { useSocketStore } from '@/lib/socket';
import { useSocketContext } from '@/lib/SocketProvider';
import { TransformWrapper, TransformComponent } from 'react-zoom-pan-pinch';
import { Expand, Minus, Plus, ShoppingBag } from 'lucide-react';
import { Player, Enemy, NPC } from '@/lib/socket';

// Hexagon Math (Flat-topped hexes)
const HEX_SIZE = 30; // Radius
const HEX_HEIGHT = Math.sqrt(3) * HEX_SIZE;

// Calculate pixel coordinates from axial coordinates (q, r)
const hexToPixel = (q: number, r: number) => {
    const x = HEX_SIZE * (3 / 2 * q);
    const y = HEX_SIZE * (Math.sqrt(3) / 2 * q + Math.sqrt(3) * r);
    return { x, y };
};

// SVG path for a flat-topped hexagon centered at 0,0
const HEX_PATH = `
  M ${HEX_SIZE} 0
  L ${HEX_SIZE / 2} ${HEX_HEIGHT / 2}
  L ${-HEX_SIZE / 2} ${HEX_HEIGHT / 2}
  L ${-HEX_SIZE} 0
  L ${-HEX_SIZE / 2} ${-HEX_HEIGHT / 2}
  L ${HEX_SIZE / 2} ${-HEX_HEIGHT / 2}
  Z
`;

interface TokenProps {
    entity: Player | Enemy | NPC;
    color: string;
    isPlayer?: boolean;
    isSelected?: boolean;
    onClick?: () => void;
    dx?: number;
    dy?: number;
    animatingPath?: { q: number, r: number, s: number }[];
    onAnimationComplete?: () => void;
}

const Token = ({ entity, color, isSelected, onClick, dx = 0, dy = 0, animatingPath, onAnimationComplete }: TokenProps) => {
    const [visualPos, setVisualPos] = useState(entity.position);

    useEffect(() => {
        if (!animatingPath || animatingPath.length === 0) {
            setVisualPos(entity.position);
        }
    }, [entity.position.q, entity.position.r, entity.position.s, animatingPath]);

    useEffect(() => {
        if (animatingPath && animatingPath.length > 0) {
            let currentStep = 0;
            const totalSteps = animatingPath.length;

            const interval = setInterval(() => {
                if (currentStep < totalSteps) {
                    setVisualPos(animatingPath[currentStep]);
                    currentStep++;
                } else {
                    clearInterval(interval);
                    onAnimationComplete?.();
                    setVisualPos(entity.position);
                }
            }, 300);

            return () => clearInterval(interval);
        }
    }, [animatingPath]);

    const xBase = hexToPixel(visualPos.q, visualPos.r).x;
    const yBase = hexToPixel(visualPos.q, visualPos.r).y;
    const x = xBase + dx;

    // SVG viewBox centers (0,0) at the hex coordinate.
    // The Token text rendering behaves differently from regular shapes, pulling the perceived center down.
    // An offset of -2 provides visual alignment natively.
    const y = yBase + dy - 2;

    // Simple initials
    const initials = entity.name.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase();

    return (
        <g
            transform={`translate(${x}, ${y})`}
            onClick={(e) => {
                if (onClick) {
                    e.stopPropagation();
                    onClick();
                }
            }}
            className={`transition-transform duration-300 ease-linear ${onClick ? "cursor-pointer" : ""}`}
        >
            {/* Selection Ring */}
            {isSelected && (
                <circle cx="0" cy="0" r={HEX_SIZE * 0.9} fill="none" stroke="white" strokeWidth="2" strokeDasharray="4 2" className="animate-spin-slow" />
            )}

            {/* Token Base */}
            <circle
                cx="0" cy="0"
                r={HEX_SIZE * 0.7}
                fill={color}
                className="stroke-neutral-900 drop-shadow-md"
                strokeWidth="3"
            />

            {/* Inner Ring */}
            <circle
                cx="0" cy="0"
                r={HEX_SIZE * 0.6}
                fill="none"
                stroke="white"
                strokeOpacity="0.2"
                strokeWidth="1"
            />

            {/* Label */}
            <text
                x="0"
                y="0"
                textAnchor="middle"
                dy=".35em"
                fill="white"
                className="text-[10px] font-bold pointer-events-none select-none"
                style={{ textShadow: "0px 1px 2px rgba(0,0,0,0.8)" }}
            >
                {initials}
            </text>

            {/* HP Bar (Simplified) */}
            {entity.hp_max && (
                <g transform={`translate(0, ${HEX_SIZE * 0.8})`}>
                    <rect x="-10" y="0" width="20" height="4" fill="black" rx="2" />
                    <rect x="-10" y="0" width={20 * (Math.max(0, entity.hp_current || 0) / entity.hp_max)} height="4" fill="#22c55e" rx="2" />
                </g>
            )}
        </g>
    );
};

export default function BattlemapPanel() {
    const gameState = useSocketStore(state => state.gameState);
    const { socket } = useSocketContext();

    // We need the socket instance to emit the move event. 
    // Since we don't store the raw socket in the store, we might need a helper from our API or just window.socket for now, 
    // OR more cleanly, useSocket() if we have a context. Looking at the codebase, there's usually a global socket or a provider.
    // Wait, let's check lib/socket.ts or other components how they emit.
    // They usually import `socket` from `@/lib/socket-client` or similar, or have an API adapter.
    // Let me check api-adapters.ts first to see if I need to import something.
    // Actually, I can just use a generic window event for now and hook it up in GameInterface, OR check how other components do it.

    const party = gameState?.party || [];
    const enemies = gameState?.enemies || [];
    const npcs = gameState?.npcs || [];

    const [selectedTokenId, setSelectedTokenId] = useState<string | null>(null);
    const [plottedPath, setPlottedPath] = useState<{ q: number, r: number, s: number }[]>([]);
    const [animatingPaths, setAnimatingPaths] = useState<Record<string, { q: number, r: number, s: number }[]>>({});

    // Listen for path animations from backend (ensuring synced movement for all players/AI)
    useEffect(() => {
        if (!socket) return;

        const handlePathAnimation = (data: { entity_id: string, path: { q: number, r: number, s: number }[] }) => {
            setAnimatingPaths(prev => ({ ...prev, [data.entity_id]: data.path }));
        };

        socket.on('entity_path_animation', handlePathAnimation);
        return () => {
            socket.off('entity_path_animation', handlePathAnimation);
        };
    }, [socket]);

    // Calculate hex distance (cube distance)
    const getHexDistance = (q1: number, r1: number, s1: number, q2: number, r2: number, s2: number) => {
        return Math.max(Math.abs(q1 - q2), Math.abs(r1 - r2), Math.abs(s1 - s2));
    };

    const handleHexHover = (hex: { q: number, r: number, s: number }) => {
        if (!selectedTokenId) return;
        const token = [...party, ...enemies, ...npcs].find(e => e.id === selectedTokenId);
        if (!token) return;

        const pathIdx = plottedPath.findIndex(p => p.q === hex.q && p.r === hex.r);

        if (pathIdx !== -1) {
            setPlottedPath(prev => prev.slice(0, pathIdx + 1));
            return;
        }

        if (hex.q === token.position.q && hex.r === token.position.r) {
            setPlottedPath([]);
            return;
        }

        const tip = plottedPath.length > 0 ? plottedPath[plottedPath.length - 1] : token.position;
        const dist = getHexDistance(tip.q, tip.r, tip.s, hex.q, hex.r, hex.s);

        if (dist === 1) {
            const maxHexDistance = Math.floor((token.speed || 30) / 5);
            if (plottedPath.length < maxHexDistance) {
                const isEnemyOrNPC = [...enemies, ...npcs].some(e => e.position && e.position.q === hex.q && e.position.r === hex.r && (e.hp_current === undefined || e.hp_current > 0));
                if (!isEnemyOrNPC) {
                    setPlottedPath(prev => [...prev, hex]);
                }
            }
        }
    };

    const handleHexClick = (hex: { q: number, r: number, s: number }, isReachable: boolean) => {
        if (!selectedTokenId || !socket || !isReachable) return;

        const pathTarget = plottedPath.length > 0 ? plottedPath[plottedPath.length - 1] : null;
        const matchesPathTarget = pathTarget && pathTarget.q === hex.q && pathTarget.r === hex.r;

        let finalPath = [];
        if (matchesPathTarget) {
            finalPath = [...plottedPath];
        } else {
            finalPath = [hex];
        }

        const emitId = selectedTokenId;
        setSelectedTokenId(null);
        setPlottedPath([]);

        socket.emit('move_entity', {
            entity_id: emitId,
            q: hex.q,
            r: hex.r,
            s: hex.s,
            path: finalPath
        });
    };

    const polylinePoints = useMemo(() => {
        if (!selectedTokenId || plottedPath.length === 0) return "";
        const token = [...party, ...enemies, ...npcs].find(e => e.id === selectedTokenId);
        if (!token) return "";

        const pts = [token.position, ...plottedPath].map(h => {
            const px = hexToPixel(h.q, h.r);
            return `${px.x},${px.y}`;
        });
        return pts.join(" ");
    }, [plottedPath, selectedTokenId, party, enemies, npcs]);

    // Helper for finding neighbors inline
    const getHexNeighbors = (q: number, r: number, s: number) => [
        { q: q + 1, r: r, s: s - 1 },
        { q: q + 1, r: r - 1, s: s },
        { q: q, r: r - 1, s: s + 1 },
        { q: q - 1, r: r, s: s + 1 },
        { q: q - 1, r: r + 1, s: s },
        { q: q, r: r + 1, s: s - 1 },
    ];

    // Derived state for reachable hexes (Shrinks as path is plotted)
    const reachableHexes = useMemo(() => {
        if (!selectedTokenId || !gameState?.location?.walkable_hexes) return new Set<string>();

        const token = [...party, ...enemies, ...npcs].find(e => e.id === selectedTokenId);
        if (!token || token.speed === undefined || !token.position) return new Set<string>();

        const isPartyMember = party.some(p => p.id === selectedTokenId);
        if (!isPartyMember) return new Set<string>();

        const maxMoves = Math.floor(token.speed / 5);
        const remainingMoves = maxMoves - plottedPath.length;

        const reachable = new Set<string>();

        // Add the path itself and origin so they stay highlighted (to allow clicking backwards)
        reachable.add(`${token.position.q},${token.position.r}`);
        plottedPath.forEach(p => reachable.add(`${p.q},${p.r}`));

        if (remainingMoves <= 0) return reachable;

        // Only enemies and NPCs block movement paths (allies can be moved through, but not ended on)
        const obstacleHexes = new Set(
            [...enemies.filter(e => e.hp_current > 0), ...npcs]
                .map(e => `${e.position.q},${e.position.r}`)
        );

        const alliedHexes = new Set(
            party.map(p => `${p.position.q},${p.position.r}`)
        );

        // Set of hexes we have already stepped on in this path
        const pathSet = new Set(plottedPath.map(p => `${p.q},${p.r}`));
        pathSet.add(`${token.position.q},${token.position.r}`);

        const walkableSet = new Set(gameState.location.walkable_hexes.map(h => `${h.q},${h.r}`));
        const startPos = plottedPath.length > 0 ? plottedPath[plottedPath.length - 1] : token.position;

        // BFS to find all hexes reachable within remainingMoves
        const visited = new Set<string>();
        const queue: { q: number, r: number, s: number, dist: number }[] = [{ ...startPos, dist: 0 }];
        visited.add(`${startPos.q},${startPos.r}`);

        while (queue.length > 0) {
            const current = queue.shift()!;

            // Reached max distance for this tip
            if (current.dist >= remainingMoves) continue;

            const neighbors = getHexNeighbors(current.q, current.r, current.s);
            for (const n of neighbors) {
                const key = `${n.q},${n.r}`;
                if (walkableSet.has(key) && !visited.has(key) && !pathSet.has(key) && !obstacleHexes.has(key)) {
                    visited.add(key);
                    reachable.add(key);
                    queue.push({ ...n, dist: current.dist + 1 });
                }
            }
        }

        // Cannot end your turn on an ally's hex
        for (const alliedHex of alliedHexes) {
            reachable.delete(alliedHex);
        }

        return reachable;
    }, [selectedTokenId, gameState?.location?.walkable_hexes, party, enemies, npcs, gameState?.phase, plottedPath]);

    // Calculate rendering offsets for tokens that share the same hex
    const allEntities = useMemo(() => {
        return [...npcs, ...enemies.filter(e => e.hp_current > 0), ...party];
    }, [npcs, enemies, party]);

    const entityOffsets = useMemo(() => {
        const counts: Record<string, number> = {};
        allEntities.forEach(e => {
            if (!e.position) return;
            const key = `${e.position.q},${e.position.r}`;
            counts[key] = (counts[key] || 0) + 1;
        });

        const currentCounts: Record<string, number> = {};
        const offsets: Record<string, { dx: number, dy: number }> = {};

        allEntities.forEach(e => {
            if (!e.position) {
                offsets[e.id] = { dx: 0, dy: 0 };
                return;
            }
            const key = `${e.position.q},${e.position.r}`;
            const total = counts[key];
            if (total > 1) {
                currentCounts[key] = (currentCounts[key] || 0) + 1;
                const index = currentCounts[key] - 1;
                if (total === 2) {
                    const sign = index === 0 ? -1 : 1;
                    offsets[e.id] = { dx: sign * 8, dy: 0 };
                } else if (total === 3) {
                    // Triangle formation
                    const angle = (index / total) * Math.PI * 2 - Math.PI / 2;
                    const radius = 8;
                    offsets[e.id] = { dx: Math.cos(angle) * radius, dy: Math.sin(angle) * radius };
                } else {
                    // Circle formation around center
                    if (index === 0) {
                        offsets[e.id] = { dx: 0, dy: 0 }; // Center one
                    } else {
                        const angle = ((index - 1) / (total - 1)) * Math.PI * 2;
                        const radius = 10;
                        offsets[e.id] = { dx: Math.cos(angle) * radius, dy: Math.sin(angle) * radius };
                    }
                }
            } else {
                offsets[e.id] = { dx: 0, dy: 0 };
            }
        });
        return offsets;
    }, [allEntities]);



    // Room bounding boxes based on explicit hex grids
    const roomRenderData = useMemo(() => {
        if (!gameState?.location) return [];
        const locs = [gameState.location, ...(gameState.discovered_locations || [])];

        return locs.map(loc => {
            if (!loc.walkable_hexes || loc.walkable_hexes.length === 0) return null;

            let minX = Infinity;
            let maxX = -Infinity;
            let minY = Infinity;
            let maxY = -Infinity;

            const interactables = loc.interactables || [];
            const doorPositions = new Set(
                interactables.filter(i => i.type === 'door' && i.position)
                    .map(d => `${d.position!.q},${d.position!.r}`)
            );

            // Only use non-door hexes to calculate the tight bounding box
            const floorHexes = loc.walkable_hexes.filter(h => !doorPositions.has(`${h.q},${h.r}`));
            const hexesToBound = floorHexes.length > 0 ? floorHexes : loc.walkable_hexes;

            hexesToBound.forEach(h => {
                const px = hexToPixel(h.q, h.r);
                minX = Math.min(minX, px.x);
                maxX = Math.max(maxX, px.x);
                minY = Math.min(minY, px.y);
                maxY = Math.max(maxY, px.y);
            });

            // Include party locations in bounds if they extend past the defined walkable area
            const partyLocs = loc.party_locations || [];
            partyLocs.forEach(spawn => {
                if (spawn.position) {
                    const px = hexToPixel(spawn.position.q, spawn.position.r);
                    minX = Math.min(minX, px.x);
                    maxX = Math.max(maxX, px.x);
                    minY = Math.min(minY, px.y);
                    maxY = Math.max(maxY, px.y);
                }
            });

            // The padding should reach exactly to the center of adjacent door hexes.
            // Horizontal doors (West/East) are 1.5 * HEX_SIZE away from the edge floor hex.
            // Vertical doors (North/South) are sqrt(3) * HEX_SIZE away from the outer floor hex.
            const padX = HEX_SIZE * 1.5;
            const padY = Math.sqrt(3) * HEX_SIZE;

            return {
                id: loc.source_id || loc.id,
                rect: {
                    x: minX - padX,
                    y: minY - padY,
                    width: (maxX - minX) + padX * 2,
                    height: (maxY - minY) + padY * 2,
                },
                hexes: loc.walkable_hexes,
                interactables: interactables,
                partyLocations: loc.party_locations || []
            };
        }).filter(Boolean) as {
            id: string;
            rect: { x: number; y: number; width: number; height: number };
            hexes: { q: number; r: number; s: number }[];
            interactables: any[];
            partyLocations: { party_id: string, position: { q: number, r: number, s: number } }[];
        }[];
    }, [gameState?.location, gameState?.discovered_locations]);

    const allDoors = useMemo(() => {
        const doors = roomRenderData.flatMap(r => r.interactables).filter(i => i.type === 'door' && i.position);
        // Deduplicate in case rooms share the exact same door interactable object in their schema arrays
        const dm = new Map(doors.map(d => [d.id || `${d.position.q},${d.position.r}`, d]));
        return Array.from(dm.values());
    }, [roomRenderData]);

    if (!gameState) {
        return (
            <div className="w-full h-full flex items-center justify-center bg-neutral-900/50 border border-neutral-800 rounded-xl relative overflow-hidden">
                <div className="absolute inset-0 bg-[url('/grid.svg')] opacity-5" />
                <span className="text-neutral-500 font-medium">Waiting for map data...</span>
            </div>
        );
    }

    const V_SIZE = 3000;
    const viewBoxX = -V_SIZE / 2;
    const viewBoxY = -V_SIZE / 2;

    // Calculate the offset needed to center the wrapper around our initial target
    // The TransformWrapper's initialPositionX/Y expect a translation value.
    // If the view starts centered at 0,0, to look at (centerX, centerY), we must translate the view by (-centerX, -centerY).
    // Because we use centerOnInit, it centers the entire SVG content, so we just need to ensure the SVG is big enough.

    // The TransformWrapper wants pixel offsets from the top left of the viewbox.
    // If the center is 'centerX', its offset from the left edge of the viewBox is:
    // offsetX = centerX - viewBoxX
    // We want that offset to be in the middle of our screen, but initialPosition centers it automatically if we give it the coordinate we want to focus on.
    // Wait, initialPositionX/Y is the translate value applied to the wrapper.
    // Let's rely on centerOnInit for now and remove the manual offset since we have a proper viewBox.

    return (
        <div className="w-full h-full bg-neutral-950 rounded-xl relative overflow-hidden group">

            {/* Header Overlay */}
            <div className="absolute top-0 left-0 right-0 p-3 flex justify-between items-start z-10 pointer-events-none">
                <div className="bg-black/60 backdrop-blur-sm px-3 py-1.5 rounded-lg border border-white/10 pointer-events-auto">
                    <h3 className="font-bold text-sm text-neutral-200">{gameState.location?.name || "Unknown Location"}</h3>
                </div>
            </div>

            <TransformWrapper
                initialScale={1}
                minScale={0.2}
                maxScale={4}
                centerOnInit={true}
                smooth={true}
                limitToBounds={false}
                wheel={{ step: 0.1 }}
            >
                {({ zoomIn, zoomOut, centerView }) => (
                    <>
                        {/* Controls Overlay */}
                        <div className="absolute bottom-4 right-4 flex flex-col gap-2 z-10 opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-auto">
                            <button onClick={() => centerView()} className="p-2 bg-neutral-800/80 hover:bg-neutral-700 text-white rounded-lg backdrop-blur-sm border border-white/10 shadow-lg transition-colors" title="Center on Party">
                                <Expand className="w-4 h-4" />
                            </button>
                            <button onClick={() => zoomIn()} className="p-2 bg-neutral-800/80 hover:bg-neutral-700 text-white rounded-lg backdrop-blur-sm border border-white/10 shadow-lg transition-colors">
                                <Plus className="w-4 h-4" />
                            </button>
                            <button onClick={() => zoomOut()} className="p-2 bg-neutral-800/80 hover:bg-neutral-700 text-white rounded-lg backdrop-blur-sm border border-white/10 shadow-lg transition-colors">
                                <Minus className="w-4 h-4" />
                            </button>
                        </div>

                        <TransformComponent
                            wrapperStyle={{ width: '100%', height: '100%' }}
                            contentStyle={{ width: `${V_SIZE}px`, height: `${V_SIZE}px`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                        >
                            <svg
                                viewBox={`${viewBoxX} ${viewBoxY} ${V_SIZE} ${V_SIZE}`}
                                width="100%"
                                height="100%"
                                style={{ overflow: 'visible' }}
                            >
                                {/* Grid Layer - Fog of War Rooms */}
                                <g className="hex-rooms" stroke="white" strokeWidth="1" fill="none">
                                    {/* Base Room Silhouette (Merged Overlaps) */}
                                    <g className="room-base-layer">
                                        <g className="room-borders" style={{ filter: "drop-shadow(0px 20px 25px rgba(0,0,0,0.5))" }}>
                                            {roomRenderData.map((room) => (
                                                <rect
                                                    key={`border-${room.id}`}
                                                    x={room.rect.x}
                                                    y={room.rect.y}
                                                    width={room.rect.width}
                                                    height={room.rect.height}
                                                    fill="#404040"
                                                    stroke="#404040"
                                                    strokeWidth="8"
                                                    strokeLinejoin="round"
                                                    rx="12"
                                                />
                                            ))}
                                        </g>
                                        <g className="room-fills" stroke="none">
                                            {roomRenderData.map((room) => (
                                                <rect
                                                    key={`fill-${room.id}`}
                                                    x={room.rect.x}
                                                    y={room.rect.y}
                                                    width={room.rect.width}
                                                    height={room.rect.height}
                                                    fill="#171717"
                                                    stroke="none"
                                                    rx="12"
                                                />
                                            ))}
                                        </g>
                                    </g>

                                    {roomRenderData.map((room) => (
                                        <g key={`content-${room.id}`} className="room-content-layer">
                                            {/* Draw Walkable Hexes */}
                                            {room.hexes.map((hex) => {
                                                const { x, y } = hexToPixel(hex.q, hex.r);
                                                const hexKey = `${hex.q},${hex.r}`;
                                                const isReachable = reachableHexes.has(hexKey);
                                                const isInPath = plottedPath.some(p => p.q === hex.q && p.r === hex.r);
                                                const hasVessel = gameState.vessels?.some(v => v.position?.q === hex.q && v.position?.r === hex.r);
                                                const hasCorpse = enemies.some(e => e.position && e.position.q === hex.q && e.position.r === hex.r && e.hp_current !== undefined && e.hp_current <= 0);

                                                return (
                                                    <g key={hexKey} transform={`translate(${x}, ${y})`}>
                                                        <path
                                                            d={HEX_PATH}
                                                            className={`transition-colors duration-200 ${isReachable ? 'fill-green-500/20 stroke-green-500/50 cursor-pointer' : 'opacity-20 hover:fill-white/10'} ${isInPath && isReachable ? '!fill-yellow-500/30' : ''}`}
                                                            onMouseEnter={() => handleHexHover(hex)}
                                                            onClick={() => handleHexClick(hex, isReachable)}
                                                        />
                                                        {(hasVessel || hasCorpse) && (
                                                            <g transform="translate(0, 8)" className="pointer-events-none opacity-80">
                                                                <ShoppingBag color="#facc15" size={14} x={-7} y={0} strokeWidth={2.5} />
                                                            </g>
                                                        )}
                                                    </g>
                                                );
                                            })}

                                            {/* Plotted Path Overlay */}
                                            {plottedPath.length > 0 && (
                                                <polyline
                                                    points={polylinePoints}
                                                    fill="none"
                                                    stroke="#eab308"
                                                    strokeWidth="4"
                                                    strokeLinecap="round"
                                                    strokeLinejoin="round"
                                                    strokeDasharray="8 6"
                                                    className="pointer-events-none opacity-80"
                                                    style={{ filter: "drop-shadow(0px 2px 4px rgba(0,0,0,0.5))" }}
                                                />
                                            )}

                                            {/* Draw Party Spawn Hexes */}
                                            {room.partyLocations?.map((spawn) => {
                                                const { x, y } = hexToPixel(spawn.position.q, spawn.position.r);
                                                return (
                                                    <g key={`spawn-${spawn.position.q}-${spawn.position.r}`} transform={`translate(${x}, ${y})`} className="pointer-events-none">
                                                        <path d={HEX_PATH} fill="rgba(234, 179, 8, 0.2)" />
                                                        <text
                                                            x="0"
                                                            y="0"
                                                            textAnchor="middle"
                                                            dy=".35em"
                                                            fill="#eab308"
                                                            className="text-[10px] font-bold opacity-80"
                                                        >
                                                            SPAWN
                                                        </text>
                                                    </g>
                                                );
                                            })}
                                        </g>
                                    ))}
                                </g>

                                {/* Interactables Layer (Doors) */}
                                <g className="interactables pointer-events-none">
                                    {allDoors.map(door => {
                                        const pos = hexToPixel(door.position!.q, door.position!.r);
                                        const isOpen = door.state === 'open';
                                        return (
                                            <g key={door.id} transform={`translate(${pos.x}, ${pos.y})`}>
                                                {/* Ground highlight for door hex */}
                                                <path d={HEX_PATH} fill={isOpen ? "rgba(34, 197, 94, 0.2)" : "rgba(239, 68, 68, 0.2)"} />
                                                <text
                                                    x="0"
                                                    y="0"
                                                    textAnchor="middle"
                                                    dy=".35em"
                                                    fill="white"
                                                    className="text-[12px] font-bold opacity-80"
                                                >
                                                    {isOpen ? "OPEN" : "DOOR"}
                                                </text>
                                            </g>
                                        );
                                    })}
                                </g>

                                {/* Tokens Layer */}
                                <g className="tokens">
                                    {/* NPCs */}
                                    {npcs.map(npc => (
                                        <Token
                                            key={npc.id}
                                            entity={npc}
                                            color="#f59e0b" // amber-500
                                            dx={entityOffsets[npc.id]?.dx}
                                            dy={entityOffsets[npc.id]?.dy}
                                            animatingPath={animatingPaths[npc.id]}
                                            onAnimationComplete={() => setAnimatingPaths(p => { const next = { ...p }; delete next[npc.id]; return next; })}
                                        />
                                    ))}

                                    {/* Enemies */}
                                    {enemies.map(enemy => {
                                        if (enemy.hp_current <= 0) return null;
                                        return (
                                            <Token
                                                key={enemy.id}
                                                entity={enemy}
                                                color="#ef4444" // red-500
                                                dx={entityOffsets[enemy.id]?.dx}
                                                dy={entityOffsets[enemy.id]?.dy}
                                                animatingPath={animatingPaths[enemy.id]}
                                                onAnimationComplete={() => setAnimatingPaths(p => { const next = { ...p }; delete next[enemy.id]; return next; })}
                                            />
                                        );
                                    })}

                                    {/* Party */}
                                    {party.map(player => (
                                        <Token
                                            key={player.id}
                                            entity={player}
                                            color={player.is_ai ? "#a855f7" : "#3b82f6"} // purple-500 for AI, blue-500 for human
                                            isPlayer={true}
                                            isSelected={gameState.active_entity_id === player.id || selectedTokenId === player.id}
                                            onClick={() => {
                                                if (gameState.phase !== 'combat' || gameState.active_entity_id === player.id) {
                                                    setSelectedTokenId(prev => {
                                                        const next = prev === player.id ? null : player.id;
                                                        if (next !== prev) setPlottedPath([]);
                                                        return next;
                                                    });
                                                }
                                            }}
                                            dx={entityOffsets[player.id]?.dx}
                                            dy={entityOffsets[player.id]?.dy}
                                            animatingPath={animatingPaths[player.id]}
                                            onAnimationComplete={() => setAnimatingPaths(p => { const next = { ...p }; delete next[player.id]; return next; })}
                                        />
                                    ))}
                                </g>
                            </svg>
                        </TransformComponent>
                    </>
                )}
            </TransformWrapper>
        </div>
    );
}
