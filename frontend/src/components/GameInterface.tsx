import { useState, useEffect } from 'react';
import ChatInterface from './ChatInterface';
import DebugPanel from './DebugPanel';
import AIStatsPanel from './AIStatsPanel';
import PartyMember from './PartyMember';
import EntityListPanel from './EntityListPanel';
import SceneVisPanel from './SceneVisPanel';
import { useSocketStore } from '@/lib/socket';
import { useAuthStore } from '@/store/authStore';
import { useCharacterStore } from '@/store/characterStore';
import { useCreateCharacterStore } from '@/store/createCharacterStore';
import { Character } from '@/lib/api';
import { Users } from 'lucide-react';

interface GameInterfaceProps {
    campaignId: string;
}

import { useNavigate } from 'react-router-dom';

export default function GameInterface({ campaignId }: GameInterfaceProps) {
    const { gameState } = useSocketStore();
    const { user } = useAuthStore();
    const { activeCharacterId } = useCharacterStore();
    const [activeTab, setActiveTab] = useState<'chat' | 'party' | 'debug'>('chat');
    const navigate = useNavigate();

    // Derived state
    const party = (gameState?.party || []) as Character[];
    // const activeCharacter = party.find(p => p.id === activeCharacterId) || party[0]; // activeCharacter is unused

    useEffect(() => {
        if (campaignId && user?.uid) {
            useSocketStore.getState().connect(campaignId, user.uid, activeCharacterId || undefined);
        }

        return () => {
            useSocketStore.getState().disconnect();
        };
    }, [campaignId, user, activeCharacterId]);

    return (
        <div className="flex h-full w-full gap-4 p-4">
            {/* Left Sidebar: Party List & Scene Vis (Hidden on mobile, visible on lg) */}
            <div className="hidden lg:flex w-64 flex-col gap-4 shrink-0">
                <div className="flex-[2] bg-neutral-900/50 rounded-xl border border-neutral-800 p-4 overflow-y-auto">
                    <h3 className="text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-4 flex items-center gap-2">
                        <Users className="w-4 h-4" />
                        Party Members
                    </h3>
                    <div className="space-y-4">
                        {party.map(char => (
                            <PartyMember
                                key={char.id}
                                character={char}
                                isActive={false} // Future implementation: Highlight active turn based on initiative order
                                onClick={() => {
                                    useCreateCharacterStore.getState().loadCharacter(char);
                                    navigate('/create-character?edit=true');
                                }}
                            />
                        ))}
                        {party.length === 0 && (
                            <div className="text-neutral-600 text-sm italic text-center">
                                Waiting for party...
                            </div>
                        )}
                    </div>
                </div>

                {/* Scene Visualization Panel */}
                <div className="flex-1 min-h-0">
                    <SceneVisPanel
                        campaignId={campaignId}
                        locationName={gameState?.location?.name}
                        description={typeof gameState?.location?.description === 'string' ? gameState.location.description : JSON.stringify(gameState?.location?.description)}
                    />
                </div>
            </div>

            {/* Main Content Area */}
            <div className="flex-1 flex flex-col min-w-0">
                {/* Mobile Tabs */}
                <div className="lg:hidden flex mb-2 bg-neutral-900/50 p-1 rounded-lg">
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
                <div className="flex-1 relative overflow-hidden rounded-xl border border-neutral-800 bg-black/40 backdrop-blur">
                    {/* On Desktop, Chat is always main. On Mobile, depends on tab. */}
                    <div className={`${activeTab === 'chat' || 'hidden lg:block'} h-full`}>
                        <ChatInterface campaignId={campaignId} characterId={activeCharacterId || undefined} />
                    </div>

                    {/* Mobile Only Views */}
                    <div className={`${activeTab === 'party' ? 'block' : 'hidden'} lg:hidden h-full p-4 overflow-y-auto`}>
                        <div className="space-y-4">
                            {party.map(char => (
                                <PartyMember key={char.id} character={char} />
                            ))}
                        </div>
                    </div>

                    <div className={`${activeTab === 'debug' ? 'block' : 'hidden'} lg:hidden h-full`}>
                        <DebugPanel campaignId={campaignId} />
                    </div>
                </div>
            </div>

            {/* Right Sidebar: Debug / Info (Hidden on mobile, visible on lg) */}
            <div className="hidden lg:flex w-80 flex-col gap-4 shrink-0">
                <div className="flex-[2] overflow-hidden min-h-0">
                    <EntityListPanel />
                </div>
                <div className="flex-1 overflow-hidden min-h-0">
                    <AIStatsPanel />
                </div>
            </div>
        </div>
    );
}
