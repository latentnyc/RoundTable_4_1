import { useState, useEffect } from 'react';
import ChatInterface from './ChatInterface';
import DebugPanel from './DebugPanel';
import AIStatsPanel from './AIStatsPanel';
import EntityListPanel from './EntityListPanel';
import BattlemapPanel from './BattlemapPanel';
import LootModal, { VesselData } from './LootModal';
import { useSocketContext } from '@/lib/SocketProvider';
import { useAuthStore } from '@/store/authStore';
import { useCharacterStore } from '@/store/characterStore';
import { useCreateCharacterStore } from '@/store/createCharacterStore';
import CreateCharacterPage from '@/pages/CreateCharacter';
import { Character } from '@/lib/api';
import { ChevronLeft, Settings } from 'lucide-react';

interface GameInterfaceProps {
    campaignId: string;
    campaignName: string;
    isAdmin: boolean;
    onBack: () => void;
    onOpenSettings: () => void;
}

export default function GameInterface({ campaignId, campaignName, isAdmin, onBack, onOpenSettings }: GameInterfaceProps) {
    const { socket, connect, disconnect } = useSocketContext();
    const { user } = useAuthStore();
    const { activeCharacterId } = useCharacterStore();
    const [activeTab, setActiveTab] = useState<'map' | 'chat' | 'party' | 'debug'>('chat');
    const [activeVessel, setActiveVessel] = useState<VesselData | null>(null);
    const [showCharacterSheet, setShowCharacterSheet] = useState(false);

    useEffect(() => {
        if (campaignId && user?.uid) {
            connect(campaignId).catch(err => {
                console.warn('Socket connection aborted or failed:', err.message);
            });
        }

        return () => {
            disconnect();
        };
    }, [campaignId, user?.uid]);

    useEffect(() => {
        if (!socket) return;

        const handleVesselOpened = (data: { vessel: VesselData, opener_id: string }) => {
            // Only show modal if this user is the opener
            if (data.opener_id === user?.uid || data.opener_id === activeCharacterId) {
                setActiveVessel(data.vessel);
            }
        };

        socket.on('vessel_opened', handleVesselOpened);
        return () => {
            socket.off('vessel_opened', handleVesselOpened);
        };
    }, [socket, user?.uid, activeCharacterId]);

    return (
        <div className="flex h-full w-full gap-4 p-4 relative">
            {/* Character Sheet Modal */}
            {showCharacterSheet && (
                <div className="absolute inset-0 z-50 bg-black/80 backdrop-blur flex items-center justify-center p-0 lg:p-10 pointer-events-auto">
                    <div className="w-full h-full max-w-7xl bg-neutral-950 lg:rounded-2xl shadow-2xl overflow-hidden border border-neutral-800 flex flex-col animate-in slide-in-from-bottom-4 zoom-in-95">
                        <CreateCharacterPage
                            onClose={() => setShowCharacterSheet(false)}
                            embedded={true}
                            forceEditMode={true}
                        />
                    </div>
                </div>
            )}

            {/* Loot Modal */}
            {activeVessel && (
                <LootModal
                    vessel={activeVessel}
                    campaignId={campaignId}
                    onClose={() => setActiveVessel(null)}
                />
            )}


            {/* Main Content Area */}
            <div className="flex-1 flex flex-col min-w-0">
                {/* Mobile Tabs */}
                <div className="lg:hidden flex mb-2 bg-neutral-900/50 p-1 rounded-lg">
                    <button
                        onClick={() => setActiveTab('map')}
                        className={`flex-1 py-2 text-xs font-bold rounded-md transition-colors ${activeTab === 'map' ? 'bg-neutral-800 text-white' : 'text-neutral-500'}`}
                    >
                        Map
                    </button>
                    <button
                        onClick={() => setActiveTab('party')}
                        className={`flex-1 py-2 text-xs font-bold rounded-md transition-colors ${activeTab === 'party' ? 'bg-neutral-800 text-white' : 'text-neutral-500'}`}
                    >
                        Party
                    </button>
                    <button
                        onClick={() => setActiveTab('chat')}
                        className={`flex-1 py-2 text-xs font-bold rounded-md transition-colors ${activeTab === 'chat' ? 'bg-neutral-800 text-white' : 'text-neutral-500'}`}
                    >
                        Chat
                    </button>
                    <button
                        onClick={() => setActiveTab('debug')}
                        className={`flex-1 py-2 text-xs font-bold rounded-md transition-colors ${activeTab === 'debug' ? 'bg-neutral-800 text-white' : 'text-neutral-500'}`}
                    >
                        Log
                    </button>
                </div>

                {/* Content */}
                <div className="flex-1 relative overflow-hidden rounded-xl border border-neutral-800 bg-black/40 backdrop-blur flex flex-col">
                    {/* On Desktop, Map is top 50%, Chat is bottom 50%. On Mobile, depends on tab. */}

                    {/* Battlemap */}
                    <div className={`${activeTab === 'map' ? 'block' : 'hidden'} lg:block flex-1 min-h-0 lg:border-b lg:border-neutral-800`}>
                        <BattlemapPanel />
                    </div>

                    {/* Chat */}
                    <div className={`${activeTab === 'chat' ? 'block' : 'hidden'} lg:block flex-1 min-h-0`}>
                        <ChatInterface campaignId={campaignId} characterId={activeCharacterId || undefined} />
                    </div>

                    {/* Mobile Only Views */}
                    <div className={`${activeTab === 'party' ? 'block' : 'hidden'} lg:hidden h-full p-4 overflow-y-auto`}>
                        <div className="space-y-4 text-center text-sm text-neutral-500 italic mt-10">
                            See the right panel (or swipe over on mobile) for the party details.
                        </div>
                    </div>

                    <div className={`${activeTab === 'debug' ? 'block' : 'hidden'} lg:hidden h-full`}>
                        <DebugPanel campaignId={campaignId} />
                    </div>
                </div>
            </div>

            <div className="hidden lg:flex w-80 flex-col gap-4 shrink-0">
                {/* Top Bar relocated from CampaignMain */}
                <div className="flex flex-col gap-2 bg-neutral-900/50 rounded-xl border border-neutral-800 p-3 shrink-0 relative">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2 min-w-0">
                            <button
                                onClick={onBack}
                                className="p-1.5 hover:bg-white/10 rounded-lg transition-colors text-neutral-400 hover:text-white shrink-0"
                            >
                                <ChevronLeft className="w-4 h-4" />
                            </button>
                            <h1 className="font-bold text-sm truncate text-neutral-200" title={campaignName}>
                                {campaignName}
                            </h1>
                        </div>

                        {isAdmin && (
                            <button
                                onClick={onOpenSettings}
                                className="p-1.5 hover:bg-white/10 rounded-lg transition-colors text-neutral-400 hover:text-white shrink-0"
                                title="Campaign Settings"
                            >
                                <Settings className="w-4 h-4" />
                            </button>
                        )}
                    </div>
                </div>

                <div className="flex-[2] overflow-hidden min-h-0">
                    <EntityListPanel
                        onCharacterClick={(char: Character) => {
                            useCreateCharacterStore.getState().loadCharacter(char);
                            setShowCharacterSheet(true);
                        }}
                    />
                </div>
                <div className="shrink-0">
                    <AIStatsPanel />
                </div>
            </div>
        </div>
    );
}
