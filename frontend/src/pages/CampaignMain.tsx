import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/store/authStore';
import { useSocketStore } from '@/lib/socket';
import { Settings, ChevronLeft } from 'lucide-react';
import GameInterface from '@/components/GameInterface';
import CampaignSettings from '@/components/CampaignSettings';
import ErrorBoundary from '@/components/ErrorBoundary';
import { campaignApi } from '@/lib/api';

export default function CampaignMain() {
    const { id } = useParams<{ id: string }>();
    const navigate = useNavigate();
    const { profile } = useAuthStore();
    const [isSettingsOpen, setIsSettingsOpen] = useState(false);
    const [campaign, setCampaign] = useState<any>(null);

    const isAdmin = profile?.is_admin || false;

    useEffect(() => {
        const fetchCampaignParams = async () => {
            if (!id) return;
            try {
                // We'll just fetch the list and find it for now to get the name
                // Or use a specific get endpoint if available
                const list = await campaignApi.list();
                const found = list.find((c: any) => c.id === id);
                if (found) {
                    setCampaign(found);

                    // Initialize Local Storage for Socket/Chat
                    if (found.model) {
                        localStorage.setItem('selected_model', found.model);
                    }
                    if (found.api_key) {
                        localStorage.setItem('gemini_api_key', found.api_key);
                    }

                    // Initialize Socket Store Stats
                    if (found.total_input_tokens !== undefined || found.total_output_tokens !== undefined) {
                        const input = found.total_input_tokens || 0;
                        const output = found.total_output_tokens || 0;
                        const total = input + output;
                        const count = found.query_count || 0;
                        useSocketStore.getState().setInitialStats(total, input, output, count);
                    }
                } else {
                    console.error("Campaign not found in list");
                }
            } catch (e) {
                console.error("Failed to load campaign info", e);
            }
        };
        fetchCampaignParams();
    }, [id]);

    if (!id) return <div>Invalid Campaign ID</div>;

    return (
        <div className="h-screen w-screen bg-black text-white flex flex-col overflow-hidden">
            {/* Header / Toolbar */}
            <header className="h-14 border-b border-white/10 flex items-center justify-between px-4 bg-neutral-900/50 backdrop-blur shrink-0 z-40 relative">
                <div className="flex items-center gap-4">
                    <button
                        onClick={() => navigate(`/campaign_dash/${id}`)}
                        className="p-2 hover:bg-white/10 rounded-lg transition-colors text-neutral-400 hover:text-white"
                    >
                        <ChevronLeft className="w-5 h-5" />
                    </button>
                    <h1 className="font-bold text-lg max-w-[200px] truncate">
                        {campaign?.name || 'Loading...'}
                    </h1>
                </div>

                <div className="flex items-center gap-2">
                    {isAdmin && (
                        <button
                            onClick={() => setIsSettingsOpen(true)}
                            className="flex items-center gap-2 px-3 py-1.5 bg-neutral-800 hover:bg-neutral-700 border border-white/5 rounded-lg text-sm transition-colors text-neutral-300 hover:text-white"
                        >
                            <Settings className="w-4 h-4" />
                            <span className="hidden sm:inline">Settings</span>
                        </button>
                    )}
                </div>
            </header>

            {/* Game Interface */}
            <div className="flex-1 overflow-hidden relative">
                <ErrorBoundary>
                    <GameInterface campaignId={id} />
                </ErrorBoundary>
            </div>

            {/* Settings Modal (Admin Only) */}
            {isAdmin && isSettingsOpen && (
                <CampaignSettings
                    campaignId={id}
                    isOpen={isSettingsOpen}
                    onClose={() => setIsSettingsOpen(false)}
                />
            )}
        </div>
    );
}
