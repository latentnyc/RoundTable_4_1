import { useMemo } from 'react';
import { useSocketStore } from '@/lib/socket';
import { TransformWrapper, TransformComponent } from 'react-zoom-pan-pinch';
import { Expand, Minus, Plus } from 'lucide-react';
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
    dx?: number;
    dy?: number;
}

const Token = ({ entity, color, isSelected, dx = 0, dy = 0 }: TokenProps) => {
    const xBase = hexToPixel(entity.position.q, entity.position.r).x;
    const yBase = hexToPixel(entity.position.q, entity.position.r).y;
    const x = xBase + dx;

    // SVG viewBox centers (0,0) at the hex coordinate.
    // The Token text rendering behaves differently from regular shapes, pulling the perceived center down.
    // An offset of -2 provides visual alignment natively.
    const y = yBase + dy - 2;

    // Simple initials
    const initials = entity.name.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase();

    return (
        <g transform={`translate(${x}, ${y})`}>
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

    const party = gameState?.party || [];
    const enemies = gameState?.enemies || [];
    const npcs = gameState?.npcs || [];

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
                                    {roomRenderData.map((room) => (
                                        <g key={room.id} className="room-layer">
                                            {/* Draw Dynamic Bounding Box */}
                                            <rect
                                                x={room.rect.x}
                                                y={room.rect.y}
                                                width={room.rect.width}
                                                height={room.rect.height}
                                                fill="#171717"
                                                stroke="#404040"
                                                strokeWidth="4"
                                                rx="12"
                                                className="shadow-2xl"
                                            />

                                            {/* Draw Walkable Hexes */}
                                            {room.hexes.map((hex) => {
                                                const { x, y } = hexToPixel(hex.q, hex.r);
                                                return (
                                                    <path
                                                        key={`${hex.q},${hex.r}`}
                                                        d={HEX_PATH}
                                                        transform={`translate(${x}, ${y})`}
                                                        className="transition-colors hover:fill-white/10 opacity-20"
                                                    />
                                                );
                                            })}

                                            {/* Draw Party Spawn Hexes */}
                                            {room.partyLocations?.map((spawn) => {
                                                const { x, y } = hexToPixel(spawn.position.q, spawn.position.r);
                                                return (
                                                    <g key={`spawn-${spawn.position.q}-${spawn.position.r}`} transform={`translate(${x}, ${y})`}>
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
                                        <Token key={npc.id} entity={npc} color="#3b82f6" dx={entityOffsets[npc.id]?.dx} dy={entityOffsets[npc.id]?.dy} /> // blue-500
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
                                            />
                                        );
                                    })}

                                    {/* Party */}
                                    {party.map(player => (
                                        <Token
                                            key={player.id}
                                            entity={player}
                                            color="#a855f7" // purple-500
                                            isPlayer={true}
                                            isSelected={gameState.active_entity_id === player.id}
                                            dx={entityOffsets[player.id]?.dx}
                                            dy={entityOffsets[player.id]?.dy}
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
