import { Character, Item } from '@/lib/api';
import { Shield, Sword, Brain, Heart, Zap, Eye, User, X, Backpack, Activity, Scroll, Component } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useSocketContext } from '@/lib/SocketProvider';

interface FullCharacterSheetProps {
    character: Character;
    onClose?: () => void;
}

export default function FullCharacterSheet({ character, onClose }: FullCharacterSheetProps) {
    const { socket } = useSocketContext();
    const sheet = character.sheet_data || {};
    const stats = sheet.stats || {};
    const equipment = (sheet.equipment || []) as Item[];
    const inventory = (sheet.inventory || []) as (string | Item)[];
    const spells = (sheet.spells || []) as Item[];
    const feats = (sheet.feats || []) as Item[];

    const handleEquipToggle = (itemId: string, isEquip: boolean) => {
        if (!socket) return;
        socket.emit('equip_item', {
            actor_id: character.id,
            item_id: itemId,
            is_equip: isEquip
        });
    };

    const handleDragStart = (e: React.DragEvent, itemId: string) => {
        e.dataTransfer.setData('itemId', itemId);
        e.dataTransfer.effectAllowed = 'move';
    };

    const handleDropOnSlot = (e: React.DragEvent, targetSlot?: string) => {
        e.preventDefault();
        const itemId = e.dataTransfer.getData('itemId');
        if (!itemId) return;

        // Emitting the equip_item. The backend logic enforces limits.
        if (!socket) return;
        socket.emit('equip_item', {
            actor_id: character.id,
            item_id: itemId,
            is_equip: true,
            target_slot: targetSlot // Send intended slot just in case
        });
    };

    const handleDropOnBackpack = (e: React.DragEvent) => {
        e.preventDefault();
        const itemId = e.dataTransfer.getData('itemId');
        if (!itemId) return;

        // Unequip it
        handleEquipToggle(itemId, false);
    };

    const allowDrop = (e: React.DragEvent) => {
        e.preventDefault();
    };

    // Vitals with fallbacks
    const hpMax = sheet.hpMax ?? (10 + Math.floor(((stats.Constitution || 10) - 10) / 2));
    const hpCurrent = sheet.hpCurrent ?? hpMax;

    // Calculate AC based on equipment
    let baseAc = 10;
    const dexMod = Math.floor(((stats.Dexterity || 10) - 10) / 2);
    let shieldBonus = 0;
    let equippedArmor = null;
    let equippedShield = null;

    for (const item of equipment) {
        if (item.type === "Armor") {
            if (item.data?.type === "Shield") {
                equippedShield = item;
            } else {
                equippedArmor = item;
            }
        }
    }

    if (equippedArmor) {
        const acInfo = equippedArmor.data?.armor_class || {};
        baseAc = acInfo.base || 10;
        if (acInfo.dex_bonus) {
            if (acInfo.max_bonus !== null && acInfo.max_bonus !== undefined && dexMod > acInfo.max_bonus) {
                baseAc += acInfo.max_bonus;
            } else {
                baseAc += dexMod;
            }
        }
    } else {
        baseAc += dexMod;
    }

    if (equippedShield) {
        const acInfo = equippedShield.data?.armor_class || {};
        shieldBonus = acInfo.base || 2;
    }

    const ac = sheet.ac ? Math.max(sheet.ac, baseAc + shieldBonus) : baseAc + shieldBonus;

    const initiative = sheet.initiative ?? Math.floor(((stats.Dexterity || 10) - 10) / 2);
    const speed = sheet.speed || 30;

    return (
        <div className="w-full h-full bg-neutral-900 border border-neutral-800 rounded-xl overflow-hidden flex flex-col relative shadow-2xl">
            {/* Close Button */}
            {onClose && (
                <button
                    onClick={onClose}
                    className="absolute top-4 right-4 p-2 bg-neutral-950/50 hover:bg-neutral-800 rounded-full text-neutral-400 hover:text-white transition-colors z-10"
                    title="Close Character Sheet"
                >
                    <X className="w-5 h-5" />
                </button>
            )}

            {/* Header Banner */}
            <div className="h-48 bg-gradient-to-r from-neutral-900 via-purple-900/20 to-neutral-900 relative flex-shrink-0">
                <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,_var(--tw-gradient-stops))] from-purple-500/10 via-transparent to-transparent opacity-50" />

                <div className="absolute -bottom-12 left-8 flex items-end gap-6">
                    <div className="w-32 h-32 rounded-full bg-neutral-900 border-4 border-neutral-800 flex items-center justify-center shadow-xl overflow-hidden">
                        <div className="w-full h-full bg-gradient-to-br from-purple-900 to-indigo-900 flex items-center justify-center border border-purple-500/50">
                            <User className="w-16 h-16 text-purple-200" />
                        </div>
                    </div>
                    <div className="mb-4">
                        <h1 className="text-3xl font-bold text-white shadow-black drop-shadow-md">{character.name}</h1>
                        <p className="text-purple-400 font-medium text-lg drop-shadow-md flex items-center gap-2">
                            {character.race} {character.role}
                            <span className="w-1.5 h-1.5 rounded-full bg-neutral-600 space-x-2" />
                            Level {character.level}
                        </p>
                    </div>
                </div>
            </div>

            {/* Content Area */}
            <div className="flex-1 overflow-y-auto p-6 pt-16 grid grid-cols-1 lg:grid-cols-12 gap-6 custom-scrollbar">

                {/* Left Column: Stats & Vitals (3 cols) */}
                <div className="lg:col-span-3 space-y-6">
                    {/* Vitals */}
                    <div className="bg-neutral-950/50 p-4 rounded-xl border border-neutral-800 space-y-4">
                        <div className="grid grid-cols-2 gap-3">
                            <div className="bg-neutral-900 p-2 rounded text-center border border-neutral-800">
                                <span className="text-[10px] text-neutral-500 uppercase font-bold">AC</span>
                                <div className="text-2xl font-bold text-blue-400">{ac}</div>
                            </div>
                            <div className="bg-neutral-900 p-2 rounded text-center border border-neutral-800">
                                <span className="text-[10px] text-neutral-500 uppercase font-bold">Init</span>
                                <div className="text-2xl font-bold text-neutral-300">{initiative >= 0 ? `+${initiative}` : initiative}</div>
                            </div>
                        </div>
                        <div className="bg-neutral-900 p-3 rounded text-center border border-neutral-800 relative overflow-hidden">
                            <div className="relative z-10 flex justify-between items-center px-2">
                                <span className="text-xs text-neutral-500 uppercase font-bold">Hit Points</span>
                                <div className="text-xl font-bold text-green-400">
                                    {hpCurrent} <span className="text-sm text-neutral-600 font-normal">/ {hpMax}</span>
                                </div>
                            </div>
                            <div
                                className="absolute bottom-0 left-0 h-1 bg-green-500/30 transition-all duration-500"
                                style={{ width: `${Math.min(100, (hpCurrent / hpMax) * 100)}%` }}
                            />
                        </div>
                        <div className="flex justify-between items-center px-1">
                            <span className="text-xs text-neutral-500 font-bold uppercase">Speed</span>
                            <span className="text-sm font-bold text-neutral-300">{speed} ft.</span>
                        </div>
                    </div>

                    {/* Ability Scores */}
                    <div className="bg-neutral-950/50 p-4 rounded-xl border border-neutral-800">
                        <h3 className="text-xs font-bold text-neutral-500 uppercase tracking-wider mb-3 pb-1 border-b border-neutral-800">Abilities</h3>
                        <div className="space-y-2">
                            <StatRow label="Strength" value={stats.Strength || 10} icon={<Sword className="w-3.5 h-3.5" />} />
                            <StatRow label="Dexterity" value={stats.Dexterity || 10} icon={<Zap className="w-3.5 h-3.5" />} />
                            <StatRow label="Constitution" value={stats.Constitution || 10} icon={<Heart className="w-3.5 h-3.5" />} />
                            <StatRow label="Intelligence" value={stats.Intelligence || 10} icon={<Brain className="w-3.5 h-3.5" />} />
                            <StatRow label="Wisdom" value={stats.Wisdom || 10} icon={<Eye className="w-3.5 h-3.5" />} />
                            <StatRow label="Charisma" value={stats.Charisma || 10} icon={<Shield className="w-3.5 h-3.5" />} />
                        </div>
                    </div>
                </div>

                {/* Center Column: Roleplay & Feats (5 cols) */}
                <div className="lg:col-span-5 space-y-6">
                    <div className="bg-neutral-950/50 p-6 rounded-xl border border-neutral-800">
                        <h3 className="text-xs font-bold text-neutral-500 uppercase tracking-wider mb-3 pb-1 border-b border-neutral-800">Backstory & Traits</h3>
                        {character.backstory ? (
                            <p className="text-sm text-neutral-300 leading-relaxed italic whitespace-pre-line">
                                "{character.backstory}"
                            </p>
                        ) : (
                            <p className="text-sm text-neutral-600 italic">No backstory provided.</p>
                        )}

                        {sheet.features && (
                            <div className="mt-4 pt-4 border-t border-neutral-800/50">
                                <h4 className="text-[10px] font-bold text-neutral-500 uppercase mb-2">Notes</h4>
                                <p className="text-sm text-neutral-400 whitespace-pre-line font-mono">{sheet.features}</p>
                            </div>
                        )}
                    </div>

                    {/* Feats List */}
                    <div className="bg-neutral-950/50 p-6 rounded-xl border border-neutral-800">
                        <h3 className="text-xs font-bold text-neutral-500 uppercase tracking-wider mb-3 pb-1 border-b border-neutral-800 flex items-center gap-2">
                            <Activity className="w-4 h-4" /> Feats & Features
                        </h3>
                        {feats.length === 0 ? (
                            <p className="text-sm text-neutral-600 italic">No feats recorded.</p>
                        ) : (
                            <div className="space-y-3">
                                {feats.map((feat, idx) => (
                                    <div key={idx} className="bg-neutral-900 border border-neutral-800 rounded p-2.5">
                                        <div className="font-bold text-sm text-purple-300 mb-1">{feat.name}</div>
                                        {feat.data?.desc && (
                                            <div className="text-xs text-neutral-400 leading-relaxed">
                                                {Array.isArray(feat.data.desc) ? feat.data.desc.join(' ') : feat.data.desc}
                                            </div>
                                        )}
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </div>

                {/* Right Column: Inventory & Spells (4 cols) */}
                <div className="lg:col-span-4 space-y-6">
                    {/* Equipment & Backpack Container */}
                    <div className="flex flex-col gap-4">
                        {/* Equipment - Paper Doll */}
                        <div className="bg-neutral-950/50 p-4 rounded-xl border border-neutral-800 flex flex-col">
                            <h3 className="text-xs font-bold text-neutral-500 uppercase tracking-wider mb-3 pb-1 border-b border-neutral-800 flex items-center justify-between flex-shrink-0">
                                <span className="flex items-center gap-2"><Component className="w-4 h-4" /> Equipped</span>
                                <span className="bg-neutral-900 px-2 py-0.5 rounded-full text-neutral-600">{equipment.length}</span>
                            </h3>

                            <div className="grid grid-cols-2 gap-3 mt-2">
                                {/* Slots helper */}
                                {(() => {
                                    // Map to Slots (temporary naive mapping until slotted backend)
                                    const slots = [
                                        { id: 'armor', label: 'Armor', accept: 'Armor', icon: <Shield className="w-4 h-4" /> },
                                        { id: 'main_hand', label: 'Main Hand', accept: 'Weapon', icon: <Sword className="w-4 h-4" /> },
                                        { id: 'off_hand', label: 'Off Hand', accept: 'Shield', icon: <Shield className="w-4 h-4" /> },
                                        { id: 'accessory', label: 'Accessory', accept: 'Item', icon: <Component className="w-4 h-4" /> }
                                    ];

                                    // Pre-populate slotted items from equipment
                                    const slotted: Record<string, Item> = {};
                                    for (const e of equipment) {
                                        if (e.data?.type === 'Shield') slotted['off_hand'] = e;
                                        else if (e.type === 'Armor') slotted['armor'] = e;
                                        else if (e.type === 'Weapon') {
                                            if (!slotted['main_hand']) slotted['main_hand'] = e;
                                            else if (!slotted['off_hand']) slotted['off_hand'] = e; // Dual Wielding!
                                            else if (!slotted['accessory']) slotted['accessory'] = e;
                                        }
                                        else if (!slotted['accessory']) slotted['accessory'] = e;
                                    }

                                    return slots.map(slot => {
                                        const item = slotted[slot.id];
                                        return (
                                            <div
                                                key={slot.id}
                                                className={cn(
                                                    "border-2 border-dashed rounded-lg p-3 min-h-[70px] flex flex-col items-center justify-center relative group transition-colors",
                                                    item ? "border-purple-600/50 bg-neutral-900" : "border-neutral-800 bg-neutral-950/30",
                                                )}
                                                onDragOver={allowDrop}
                                                onDrop={(e) => handleDropOnSlot(e, slot.id)}
                                            >
                                                {!item ? (
                                                    <div className="flex flex-col items-center justify-center text-neutral-600">
                                                        {slot.icon}
                                                        <span className="text-[10px] mt-1 font-medium">{slot.label}</span>
                                                    </div>
                                                ) : (
                                                    <div
                                                        className="w-full h-full flex flex-col cursor-grab active:cursor-grabbing"
                                                        draggable
                                                        onDragStart={(e) => handleDragStart(e, item.id)}
                                                    >
                                                        <div className="font-bold text-xs text-neutral-300 group-hover:text-white transition-colors truncate w-full text-center" title={item.name}>{item.name}</div>
                                                        <div className="flex justify-center gap-1 mt-1">
                                                            {item.data?.armor_class && (
                                                                <span className="text-[9px] font-mono text-blue-400 bg-blue-950/30 px-1.5 py-0.5 rounded">
                                                                    AC {item.data.armor_class.base}
                                                                </span>
                                                            )}
                                                            {item.data?.damage && (
                                                                <span className="text-[9px] font-mono text-red-400 bg-red-950/30 px-1.5 py-0.5 rounded">
                                                                    {item.data.damage.damage_dice}
                                                                </span>
                                                            )}
                                                        </div>
                                                        <button
                                                            onClick={() => handleEquipToggle(item.id, false)}
                                                            className="absolute -top-1.5 -right-1.5 bg-neutral-800 hover:bg-neutral-700 text-neutral-400 p-0.5 rounded-full transition-colors opacity-0 group-hover:opacity-100 shadow-md border border-neutral-700"
                                                            title="Unequip"
                                                        >
                                                            <X className="w-3 h-3" />
                                                        </button>
                                                    </div>
                                                )}
                                            </div>
                                        );
                                    });
                                })()}
                            </div>
                        </div>

                        {/* Backpack */}
                        <div
                            className="bg-neutral-950/50 p-4 rounded-xl border border-neutral-800 flex flex-col max-h-[300px]"
                            onDragOver={allowDrop}
                            onDrop={handleDropOnBackpack}
                        >
                            <h3 className="text-xs font-bold text-neutral-500 uppercase tracking-wider mb-3 pb-1 border-b border-neutral-800 flex items-center justify-between flex-shrink-0">
                                <span className="flex items-center gap-2"><Backpack className="w-4 h-4" /> Backpack</span>
                                <span className="bg-neutral-900 px-2 py-0.5 rounded-full text-neutral-600">{inventory.length}</span>
                            </h3>
                            <div className="flex-1 overflow-y-auto custom-scrollbar space-y-2 pr-1">
                                {inventory.length === 0 ? (
                                    <p className="text-sm text-neutral-600 italic text-center py-4">Backpack is empty.</p>
                                ) : (
                                    (() => {
                                        const groupedInventory = inventory.reduce((acc, item) => {
                                            const isString = typeof item === 'string';
                                            const itemId = isString ? item : (item as Item).id;
                                            if (acc[itemId]) {
                                                acc[itemId].count += 1;
                                            } else {
                                                acc[itemId] = { item, count: 1 };
                                            }
                                            return acc;
                                        }, {} as Record<string, { item: string | Item, count: number }>);

                                        return Object.values(groupedInventory).map(({ item, count }, idx) => {
                                            const isString = typeof item === 'string';
                                            const itemId = isString ? item : (item as Item).id;
                                            const itemName = isString
                                                ? item.replace(/^(wpn-|arm-|itm-|eqp-|item_)/i, '').replace(/[-_]/g, ' ')
                                                : (item as Item).name;

                                            return (
                                                <div
                                                    key={idx}
                                                    className="bg-neutral-900 border border-neutral-800 rounded p-2 flex justify-between items-center group cursor-grab active:cursor-grabbing hover:border-purple-600/50 transition-colors"
                                                    draggable
                                                    onDragStart={(e) => handleDragStart(e, itemId)}
                                                >
                                                    <span className="text-sm text-neutral-300 font-medium capitalize group-hover:text-white transition-colors flex items-center gap-2">
                                                        {itemName}
                                                        {count > 1 && (
                                                            <span className="text-[10px] bg-neutral-800 text-neutral-400 px-1.5 py-0.5 rounded-full font-mono">x{count}</span>
                                                        )}
                                                    </span>
                                                    <button
                                                        onClick={() => handleEquipToggle(itemId, true)}
                                                        className="text-[10px] bg-purple-900/40 hover:bg-purple-800/60 text-purple-300 px-2 py-1 rounded transition-colors opacity-0 md:group-hover:opacity-100"
                                                    >
                                                        Equip
                                                    </button>
                                                </div>
                                            );
                                        });
                                    })()
                                )}
                            </div>
                        </div>
                    </div>

                    {/* Spells */}
                    <div className="bg-neutral-950/50 p-4 rounded-xl border border-neutral-800 max-h-[400px] flex flex-col">
                        <h3 className="text-xs font-bold text-neutral-500 uppercase tracking-wider mb-3 pb-1 border-b border-neutral-800 flex items-center gap-2 flex-shrink-0">
                            <Scroll className="w-4 h-4" /> Spells
                        </h3>
                        <div className="flex-1 overflow-y-auto custom-scrollbar space-y-2 pr-1">
                            {spells.length === 0 ? (
                                <p className="text-sm text-neutral-600 italic text-center py-4">No known spells.</p>
                            ) : (
                                spells.map((spell, idx) => (
                                    <div key={idx} className="bg-neutral-900 border border-neutral-800 rounded p-2 group">
                                        <div className="flex justify-between items-center mb-1">
                                            <span className="font-bold text-sm text-indigo-300 group-hover:text-indigo-200 transition-colors">{spell.name}</span>
                                            <span className="text-[10px] bg-neutral-800 px-1.5 rounded text-neutral-400">
                                                {spell.data?.level > 0 ? `Lvl ${spell.data.level}` : 'Cantrip'}
                                            </span>
                                        </div>
                                        {spell.data?.desc && (
                                            <p className="text-[10px] text-neutral-500 line-clamp-2 hover:line-clamp-none cursor-help transition-all">
                                                {Array.isArray(spell.data.desc) ? spell.data.desc[0] : spell.data.desc}
                                            </p>
                                        )}
                                    </div>
                                ))
                            )}
                        </div>
                    </div>
                </div>

            </div>
        </div>
    );
}

function StatRow({ label, value, icon }: { label: string; value: number; icon: React.ReactNode }) {
    const mod = Math.floor((value - 10) / 2);
    const sign = mod >= 0 ? '+' : '';

    return (
        <div className="flex items-center justify-between p-2 hover:bg-neutral-900 rounded transition-colors group">
            <div className="flex items-center gap-3">
                <div className="p-1.5 bg-neutral-900 rounded text-neutral-500 group-hover:text-purple-400 transition-colors">
                    {icon}
                </div>
                <span className="text-xs font-bold text-neutral-400 uppercase">{label.substring(0, 3)}</span>
            </div>
            <div className="flex items-baseline gap-2">
                <span className="text-sm font-bold text-white">{value}</span>
                <span className={cn("text-xs font-mono px-1.5 py-0.5 rounded w-8 text-center", mod >= 0 ? "bg-neutral-800 text-green-400" : "bg-red-950/30 text-red-400")}>
                    {sign}{mod}
                </span>
            </div>
        </div>
    );
}
