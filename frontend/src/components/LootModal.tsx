import { useState } from 'react';
import { useSocketContext } from '@/lib/SocketProvider';
import { useCharacterStore } from '@/store/characterStore';
import { X, PackageOpen, Coins, Check } from 'lucide-react';

export interface EnrichedItem {
    id: string;
    name: string;
    description?: string;
    type?: string;
}

// Using a local interface since Vessel isn't in api.ts yet
export interface VesselData {
    id: string;
    name: string;
    description: string;
    contents: string[];
    enriched_contents?: EnrichedItem[];
    currency: { pp: number; gp: number; sp: number; cp: number };
}

interface LootModalProps {
    vessel: VesselData;
    onClose: () => void;
    campaignId: string;
}

export default function LootModal({ vessel, onClose, campaignId }: LootModalProps) {
    const { socket } = useSocketContext();
    const { activeCharacterId } = useCharacterStore();
    const [taking, setTaking] = useState(false);

    // Filter out items already taken (conceptually, backend handles it, but we can do it optimistically)
    const [items, setItems] = useState<string[]>(vessel.contents || []);
    const [currency, setCurrency] = useState(vessel.currency || { pp: 0, gp: 0, sp: 0, cp: 0 });

    const formatCurrency = (c: typeof currency) => {
        const parts = [];
        if (c.pp > 0) parts.push(`${c.pp} pp`);
        if (c.gp > 0) parts.push(`${c.gp} gp`);
        if (c.sp > 0) parts.push(`${c.sp} sp`);
        if (c.cp > 0) parts.push(`${c.cp} cp`);
        return parts.join(', ') || 'None';
    };

    const handleTakeItem = (itemId: string) => {
        if (!socket || !activeCharacterId) return;
        setTaking(true);
        socket.emit('take_items', {
            campaign_id: campaignId,
            actor_id: activeCharacterId,
            vessel_id: vessel.id,
            item_ids: [itemId],
            take_currency: false
        });

        // Optimistic UI update
        setItems(prev => prev.filter(i => i !== itemId));
        setTaking(false);
    };

    const handleTakeCurrency = () => {
        if (!socket || !activeCharacterId) return;
        setTaking(true);
        socket.emit('take_items', {
            campaign_id: campaignId,
            actor_id: activeCharacterId,
            vessel_id: vessel.id,
            item_ids: [],
            take_currency: true
        });
        setCurrency({ pp: 0, gp: 0, sp: 0, cp: 0 });
        setTaking(false);
    };

    const handleTakeAll = () => {
        if (!socket || !activeCharacterId) return;
        setTaking(true);
        socket.emit('take_items', {
            campaign_id: campaignId,
            actor_id: activeCharacterId,
            vessel_id: vessel.id,
            item_ids: items,
            take_currency: true
        });
        setItems([]);
        setCurrency({ pp: 0, gp: 0, sp: 0, cp: 0 });
        setTaking(false);
        // Automatically close after taking all
        setTimeout(() => onClose(), 500);
    };

    const hasCurrency = currency.pp > 0 || currency.gp > 0 || currency.sp > 0 || currency.cp > 0;
    const isEmpty = items.length === 0 && !hasCurrency;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
            <div className="bg-neutral-900 border border-neutral-800 rounded-xl w-full max-w-md shadow-2xl overflow-hidden flex flex-col max-h-[80vh]">
                {/* Header */}
                <div className="flex items-center justify-between p-4 border-b border-neutral-800 bg-neutral-950/50">
                    <div className="flex items-center gap-3">
                        <div className="p-2 bg-purple-900/30 text-purple-400 rounded-lg">
                            <PackageOpen className="w-5 h-5" />
                        </div>
                        <div>
                            <h2 className="font-bold text-white">{vessel.name}</h2>
                            <p className="text-xs text-neutral-400">{vessel.description}</p>
                        </div>
                    </div>
                    <button onClick={onClose} className="p-2 text-neutral-500 hover:text-white transition-colors bg-neutral-900 rounded-md">
                        <X className="w-4 h-4" />
                    </button>
                </div>

                {/* Content Area */}
                <div className="flex-1 overflow-y-auto p-4 space-y-4">
                    {isEmpty ? (
                        <div className="flex flex-col items-center justify-center py-8 text-neutral-500 space-y-2">
                            <Check className="w-8 h-8 text-green-500/50" />
                            <p className="text-sm">This vessel is now empty.</p>
                        </div>
                    ) : (
                        <>
                            {/* Wealth Section */}
                            {hasCurrency && (
                                <div className="space-y-2">
                                    <h3 className="text-xs font-bold text-neutral-500 uppercase tracking-wider flex items-center gap-2">
                                        <Coins className="w-3.5 h-3.5" /> Wealth
                                    </h3>
                                    <div className="flex items-center justify-between bg-neutral-950 border border-neutral-800 rounded-lg p-3">
                                        <span className="text-sm font-medium text-amber-400 font-mono">
                                            {formatCurrency(currency)}
                                        </span>
                                        <button
                                            disabled={taking}
                                            onClick={handleTakeCurrency}
                                            className="text-xs bg-neutral-800 hover:bg-neutral-700 text-white px-3 py-1.5 rounded transition-colors disabled:opacity-50"
                                        >
                                            Take
                                        </button>
                                    </div>
                                </div>
                            )}

                            {/* Items Section */}
                            {items.length > 0 && (
                                <div className="space-y-2">
                                    <h3 className="text-xs font-bold text-neutral-500 uppercase tracking-wider">Items</h3>
                                    <div className="space-y-2">
                                        {items.map((item, idx) => {
                                            const enriched = vessel.enriched_contents?.find(e => e.id === item);
                                            const displayName = enriched ? enriched.name : item.replace(/-/g, ' ').replace(/_/g, ' ');

                                            return (
                                                <div key={idx} className="flex items-center justify-between bg-neutral-950 border border-neutral-800 rounded-lg p-2 pl-3">
                                                    <div className="flex flex-col pr-4">
                                                        <span className="text-sm text-neutral-300 font-medium capitalize">
                                                            {displayName}
                                                        </span>
                                                        {enriched && enriched.description && (
                                                            <span className="text-xs text-neutral-500 line-clamp-1 truncate" title={enriched.description}>
                                                                {enriched.description}
                                                            </span>
                                                        )}
                                                    </div>
                                                    <button
                                                        disabled={taking}
                                                        onClick={() => handleTakeItem(item)}
                                                        className="text-xs bg-purple-900/40 hover:bg-purple-800/60 text-purple-300 px-3 py-1.5 rounded transition-colors disabled:opacity-50 flex-shrink-0"
                                                    >
                                                        Take
                                                    </button>
                                                </div>
                                            );
                                        })}
                                    </div>
                                </div>
                            )}
                        </>
                    )}
                </div>

                {/* Footer footer */}
                <div className="p-4 border-t border-neutral-800 bg-neutral-950/50 flex justify-end">
                    <button
                        disabled={isEmpty || taking}
                        onClick={handleTakeAll}
                        className="w-full sm:w-auto px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        Take All
                    </button>
                </div>
            </div>
        </div>
    );
}
