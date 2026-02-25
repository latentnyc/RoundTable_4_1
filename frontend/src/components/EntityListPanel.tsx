import { useEffect, useState, useMemo, useRef } from 'react';
import { createPortal } from 'react-dom';
import { useSocketStore, Enemy, NPC, Player } from '@/lib/socket';
import { campaignApi, CampaignParticipant } from '@/lib/api';
import { Users, Skull, User, ExternalLink, ScrollText, RefreshCw, Swords, Info } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAuthStore } from '@/store/authStore';

export default function EntityListPanel({ onCharacterClick }: { onCharacterClick?: (char: any) => void }) {
    const { gameState } = useSocketStore();
    const { user } = useAuthStore();
    const [participants, setParticipants] = useState<CampaignParticipant[]>([]);
    const [isLoading, setIsLoading] = useState(false);

    // Fetch Participants (DB Source)
    useEffect(() => {
        const fetchParticipants = async () => {
            if (gameState?.session_id) {
                try {
                    const parts = await campaignApi.getParticipants(gameState.session_id);
                    setParticipants(parts);
                } catch (e) {
                    console.error("Failed to fetch roster", e);
                }
            }
        };
        fetchParticipants();
    }, [gameState?.session_id]);

    // Combat Start Toast Logic - REMOVED per user request

    const handleRefresh = () => {
        if (gameState?.session_id && user?.uid) {
            setIsLoading(true);
            campaignApi.getParticipants(gameState.session_id).then(setParticipants).finally(() => setIsLoading(false));
        }
    };

    const openLogPopup = () => {
        if (!gameState?.session_id) return;
        const width = 800;
        const height = 600;
        const left = (window.screen.width - width) / 2;
        const top = (window.screen.height - height) / 2;
        window.open(`/logs?campaignId=${gameState.session_id}`, 'AI_Logs', `width=${width},height=${height},top=${top},left=${left},scrollbars=yes,resizable=yes`);
    };




    const party = gameState?.party || [];
    const enemies = gameState?.enemies || [];
    const npcs = gameState?.npcs || [];

    // Filter Roster: Participants NOT in the active party scene
    const activeIds = new Set(party.map(p => p.id));
    const rosterCharacters = participants.flatMap(p => p.characters).filter(c => !activeIds.has(c.id));

    // Combat Mode Logic
    const isCombat = gameState?.phase === 'combat';
    const turnOrder = gameState?.turn_order || [];
    const activeEntityId = gameState?.active_entity_id;

    // Ordered Combatants
    const combatants = useMemo(() => {
        if (!isCombat) return [];

        const allEntities = [...party, ...enemies, ...npcs];
        const entityMap = new Map(allEntities.map(e => [e.id, e]));

        // Filter out any IDs not found (in case turn_order has stale IDs)
        return turnOrder.map(id => {
            const ent = entityMap.get(id);
            if (!ent) return null;

            // Determine type for styling
            let type: 'party' | 'enemy' | 'npc' = 'npc';
            if (party.some(p => p.id === id)) type = 'party';
            else if (enemies.some(e => e.id === id)) type = 'enemy';

            return { entity: ent, type };
        }).filter((x): x is { entity: Player | Enemy | NPC, type: 'party' | 'enemy' | 'npc' } => x !== null);
    }, [isCombat, turnOrder, party, enemies, npcs]);

    if (!gameState) return (
        <div className="flex flex-col h-full bg-neutral-900/40 backdrop-blur-md rounded-xl border border-white/5 overflow-hidden items-center justify-center text-neutral-500 text-xs">
            Waiting for game state...
        </div>
    );

    const SectionHeader = ({ icon: Icon, title, count }: { icon: any, title: string, count: number }) => (
        <div className="flex items-center gap-2 px-3 py-2 bg-white/5 text-xs font-bold uppercase tracking-widest text-neutral-300 mt-2 first:mt-0 rounded-md mx-2">
            <Icon className="w-4 h-4" />
            <span>{title}</span>
            <span className="ml-auto bg-black/40 px-2 py-0.5 rounded text-neutral-400">{count}</span>
        </div>
    );

    const EntityRow = ({ entity, type, isActive }: { entity: Player | Enemy | NPC, type: 'party' | 'enemy' | 'npc', isActive?: boolean }) => {
        const [isHovered, setIsHovered] = useState(false);
        const [tooltipPos, setTooltipPos] = useState({ top: 0, right: 0, width: 0 });
        const rowRef = useRef<HTMLDivElement>(null);

        const hpCurrent = entity.hp_current ?? 0;
        const hpMax = entity.hp_max ?? 1;
        const hpPercent = Math.max(0, Math.min(100, (hpCurrent / hpMax) * 100));

        let hpColor = "bg-emerald-500";
        if (hpPercent < 30) hpColor = "bg-red-500";
        else if (hpPercent < 60) hpColor = "bg-yellow-500";

        const isDead = hpCurrent <= 0;
        const isInteractive = type === 'party' && onCharacterClick;

        const handleMouseEnter = () => {
            if (rowRef.current) {
                const rect = rowRef.current.getBoundingClientRect();
                setTooltipPos({
                    top: rect.top + (rect.height / 2),
                    right: window.innerWidth - rect.left + 10, // 10px padding from the row
                    width: rect.width
                });
            }
            setIsHovered(true);
        };

        return (
            <div
                ref={rowRef}
                className={cn(
                    "group px-3 py-2 mx-2 rounded-lg border border-transparent transition-all relative overflow-hidden",
                    isActive ? "bg-white/[0.08] border-white/20 shadow-lg shadow-black/20" : "hover:border-white/5 hover:bg-white/[0.02]",
                    isDead && "opacity-50 grayscale",
                    isInteractive && "cursor-pointer active:scale-[0.98]"
                )}
                onMouseEnter={handleMouseEnter}
                onMouseLeave={() => setIsHovered(false)}
                onClick={() => isInteractive && onCharacterClick(entity)}
            >
                {/* Active Indicator Strip */}
                {isActive && <div className="absolute left-0 top-0 bottom-0 w-1 bg-amber-500 rounded-l-lg overflow-hidden" />}

                <div className="flex items-center justify-between mb-1 pl-1 relative z-10">
                    <div className="flex items-center gap-2 min-w-0">
                        <div className={cn(
                            "w-2 h-2 rounded-full shrink-0",
                            entity.is_ai ? "bg-purple-500" : "bg-blue-500"
                        )} />
                        <span className={cn(
                            "text-sm font-semibold truncate transition-colors",
                            isActive ? "text-amber-200" : (entity.is_ai ? "text-purple-400 group-hover:text-purple-300" : "text-blue-400 group-hover:text-blue-300")
                        )}>
                            {entity.name}{entity.is_ai ? " - AI" : ""}
                        </span>
                    </div>
                    <div className="flex gap-2">
                        {isCombat && (
                            <span className={cn("text-[10px] font-bold font-mono", isActive ? "text-amber-400" : "text-neutral-400")}>
                                Init: {entity.initiative ?? '?'}
                            </span>
                        )}
                        <span className="text-[10px] font-mono text-neutral-400">AC {entity.ac}</span>
                    </div>
                </div>

                {/* HP Bar */}
                <div className="w-full h-1.5 bg-neutral-800 rounded-full overflow-hidden flex items-center ml-1 relative z-10 my-1.5">
                    <div
                        className={cn("h-full transition-all duration-500", hpColor, "shadow-[0_0_8px_rgba(0,0,0,0.5)]")}
                        style={{ width: `${hpPercent}%` }}
                    />
                </div>

                {/* Custom Graphical Tooltip via Portal */}
                {isHovered && createPortal(
                    <div
                        className="fixed w-48 bg-neutral-900 border border-neutral-700 shadow-xl shadow-black/50 rounded-xl p-3 z-50 animate-in fade-in zoom-in-95 pointer-events-none"
                        style={{ top: tooltipPos.top, right: tooltipPos.right, transform: 'translateY(-50%)' }}
                    >

                        {/* Header Area */}
                        <div className="flex items-start justify-between mb-2 pb-2 border-b border-white/10">
                            <div>
                                <h4 className="text-sm font-bold text-white leading-tight">{entity.name}</h4>
                                <div className="text-[10px] text-neutral-400 font-medium uppercase tracking-wider mt-0.5">
                                    {type === 'party' ? (entity as Player).race || 'Unknown' : type === 'enemy' ? (entity as Enemy).type || 'Monster' : (entity as NPC).role || 'NPC'}
                                </div>
                            </div>
                            {type === 'party' && <User className="w-4 h-4 text-purple-400 opacity-50" />}
                            {type === 'enemy' && <Skull className="w-4 h-4 text-red-500 opacity-50" />}
                            {type === 'npc' && <Users className="w-4 h-4 text-amber-500 opacity-50" />}
                        </div>

                        {/* Stats Grid */}
                        <div className="grid grid-cols-2 gap-2 mb-2">
                            <div className="bg-black/30 rounded p-1.5 flex flex-col items-center justify-center border border-white/5">
                                <span className="text-[9px] text-neutral-500 uppercase font-bold tracking-wider mb-0.5">HP</span>
                                <span className={cn("text-xs font-mono font-bold", isDead ? "text-red-500" : "text-emerald-400")}>
                                    {hpCurrent}/{hpMax}
                                </span>
                            </div>
                            <div className="bg-black/30 rounded p-1.5 flex flex-col items-center justify-center border border-white/5">
                                <span className="text-[9px] text-neutral-500 uppercase font-bold tracking-wider mb-0.5">AC</span>
                                <span className="text-xs font-mono font-bold text-blue-400">{entity.ac}</span>
                            </div>
                        </div>

                        {/* Extra Details */}
                        {type === 'party' && (
                            <div className="text-xs text-neutral-300 mt-2 flex justify-between items-center bg-white/5 px-2 py-1 rounded">
                                <span className="text-neutral-500 text-[10px] uppercase">Class</span>
                                <span className="font-medium text-purple-200">{(entity as Player).role || '?'}</span>
                            </div>
                        )}
                        {type === 'party' && (
                            <div className="text-xs text-neutral-300 mt-1 flex justify-between items-center bg-white/5 px-2 py-1 rounded">
                                <span className="text-neutral-500 text-[10px] uppercase">Level</span>
                                <span className="font-medium">{(entity as Player).level || '?'}</span>
                            </div>
                        )}

                        {/* Contextual Footer / Identified Stats */}
                        {type === 'enemy' && !(entity as Enemy).identified && (
                            <div className="mt-2 pt-2 border-t border-white/5 flex items-start gap-1.5">
                                <Info className="w-3 h-3 text-blue-400/70 shrink-0 mt-0.5" />
                                <span className="text-[9px] leading-tight text-neutral-500 font-medium italic">
                                    Use <span className="text-neutral-300">@identify {entity.name}</span> to learn more about this creature's stats and vulnerabilities.
                                </span>
                            </div>
                        )}
                        {type === 'enemy' && (entity as Enemy).identified && (
                            <div className="mt-2 pt-2 border-t border-white/5">
                                <div className="text-[10px] font-bold text-emerald-400 mb-1 uppercase tracking-wider flex items-center gap-1">
                                    <Info className="w-3 h-3" /> Identified
                                </div>
                                <div className="grid grid-cols-3 gap-1 text-[9px] text-neutral-300 mb-1">
                                    {Object.entries((entity as Enemy).data?.stats || {}).map(([stat, val]) => (
                                        <div key={stat} className="flex justify-between items-center bg-black/20 px-1 py-0.5 rounded border border-white/5">
                                            <span className="uppercase text-neutral-500 font-bold">{stat.substring(0, 3)}</span>
                                            <span className="font-mono font-bold text-neutral-200">{String(val)}</span>
                                        </div>
                                    ))}
                                </div>
                                {((entity as Enemy).data?.vulnerabilities?.length > 0) && (
                                    <div className="mt-1 text-[9px] leading-tight flex gap-1">
                                        <span className="text-red-400 uppercase font-bold shrink-0">Vuln:</span>
                                        <span className="text-neutral-300">{(entity as Enemy).data?.vulnerabilities.join(', ')}</span>
                                    </div>
                                )}
                                {((entity as Enemy).data?.resistances?.length > 0) && (
                                    <div className="mt-0.5 text-[9px] leading-tight flex gap-1">
                                        <span className="text-blue-400 uppercase font-bold shrink-0">Resist:</span>
                                        <span className="text-neutral-300">{(entity as Enemy).data?.resistances.join(', ')}</span>
                                    </div>
                                )}
                                {((entity as Enemy).data?.immunities?.length > 0) && (
                                    <div className="mt-0.5 text-[9px] leading-tight flex gap-1">
                                        <span className="text-yellow-400 uppercase font-bold shrink-0">Immune:</span>
                                        <span className="text-neutral-300">{(entity as Enemy).data?.immunities.join(', ')}</span>
                                    </div>
                                )}
                            </div>
                        )}

                        {isInteractive && (
                            <div className="mt-2 pt-2 border-t border-white/5 text-center">
                                <span className="text-[9px] text-purple-400/70 font-bold uppercase tracking-widest flex items-center justify-center gap-1">
                                    Click to View Sheet <ExternalLink className="w-2.5 h-2.5" />
                                </span>
                            </div>
                        )}
                    </div>,
                    document.body
                )}
                <div className="flex justify-between mt-1 pl-1">
                    <span className="text-[10px] text-neutral-500 uppercase tracking-widest font-semibold">
                        {type === 'enemy' ? (entity as Enemy).type : type === 'npc' ? (entity as NPC).role : (entity as Player).race}
                    </span>
                    <span className="text-[10px] font-mono font-bold text-neutral-400">
                        {hpCurrent}/{hpMax} HP
                    </span>
                </div>
            </div>
        );
    };

    const RosterRow = ({ char }: { char: { name: string, race: string, class_name: string, level: number } }) => (
        <div className="px-3 py-2 mx-2 rounded-lg border border-transparent hover:bg-white/[0.02] transition-colors opacity-70 hover:opacity-100">
            <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2 min-w-0">
                    <div className="w-1.5 h-1.5 rounded-full shrink-0 bg-neutral-600" />
                    <span className="text-xs font-medium text-neutral-400 truncate">
                        {char.name}
                    </span>
                </div>
                <span className="text-[9px] text-neutral-600 italic">Offline</span>
            </div>
            <div className="flex justify-between mt-1">
                <span className="text-[8px] text-neutral-600">{char.race} {char.class_name}</span>
                <span className="text-[8px] text-neutral-600">Lvl {char.level}</span>
            </div>
        </div>
    );

    return (
        <div className="flex flex-col h-full bg-neutral-900/40 backdrop-blur-md rounded-xl border border-white/5 overflow-hidden relative">

            {/* Combat Notification Overlay - REMOVED */}

            {/* Header */}
            <div className="w-full px-3 py-3 border-b border-white/10 flex items-center justify-between bg-white/[0.05]">
                <h3 className="text-xs font-bold text-neutral-300 uppercase tracking-widest flex items-center gap-2">
                    {isCombat ? <Swords className="w-4 h-4 text-red-400" /> : <Users className="w-4 h-4" />}
                    {isCombat ? "Combat Order" : "Scene Entities"}
                </h3>

                <div className="flex items-center gap-2">
                    <button
                        onClick={handleRefresh}
                        disabled={isLoading}
                        className={cn("p-1.5 rounded hover:bg-neutral-800 text-neutral-500 hover:text-white transition-colors", isLoading && "animate-spin")}
                        title="Refresh Roster"
                    >
                        <RefreshCw className="w-3 h-3" />
                    </button>
                    <button
                        onClick={openLogPopup}
                        className="flex items-center gap-1.5 px-2 py-1 rounded bg-neutral-800 hover:bg-neutral-700 border border-white/5 text-[9px] text-neutral-400 hover:text-white transition-all uppercase tracking-wide"
                        title="Open Logs in New Window"
                    >
                        <ScrollText className="w-3 h-3" />
                        <span>Logs</span>
                        <ExternalLink className="w-2.5 h-2.5 opacity-50" />
                    </button>
                </div>
            </div>

            {/* Scrollable List */}
            <div className="flex-1 overflow-y-auto py-2 space-y-4">

                {isCombat ? (
                    /* Combat View: Single Ordered List */
                    <div className="mt-1 space-y-1">
                        {combatants.map(({ entity, type }) => (
                            <EntityRow
                                key={entity.id}
                                entity={entity}
                                type={type}
                                isActive={entity.id === activeEntityId}
                            />
                        ))}
                    </div>
                ) : (
                    /* Exploration View: Grouped Sections */
                    <>
                        {/* Party Section */}
                        <div>
                            <SectionHeader icon={User} title="Active Party" count={party.length} />
                            <div className="mt-1 space-y-1">
                                {party.map(p => <EntityRow key={p.id} entity={p} type="party" />)}
                                {party.length === 0 && <div className="mx-4 text-[10px] text-neutral-600 italic">No party members in scene.</div>}
                            </div>
                        </div>

                        {/* Roster Section (DB Pull) */}
                        {(rosterCharacters.length > 0) && (
                            <div>
                                <SectionHeader icon={Users} title="Reserves / Offline" count={rosterCharacters.length} />
                                <div className="mt-1 space-y-1">
                                    {rosterCharacters.map(c => <RosterRow key={c.id} char={c} />)}
                                </div>
                            </div>
                        )}

                        {/* Enemies Section */}
                        {(enemies.length > 0) && (
                            <div>
                                <SectionHeader icon={Skull} title="Enemies" count={enemies.length} />
                                <div className="mt-1 space-y-1">
                                    {enemies.map(e => <EntityRow key={e.id} entity={e} type="enemy" />)}
                                </div>
                            </div>
                        )}

                        {/* NPCs Section */}
                        {(npcs.length > 0) && (
                            <div>
                                <SectionHeader icon={Users} title="NPCs" count={npcs.length} />
                                <div className="mt-1 space-y-1">
                                    {npcs.map(n => <EntityRow key={n.id} entity={n} type="npc" />)}
                                </div>
                            </div>
                        )}

                        {/* Empty State */}
                        {party.length === 0 && enemies.length === 0 && npcs.length === 0 && rosterCharacters.length === 0 && (
                            <div className="flex flex-col items-center justify-center p-8 text-neutral-700">
                                <span className="text-[10px] italic">The scene is empty.</span>
                            </div>
                        )}
                    </>
                )}
            </div>
        </div>
    );
}
