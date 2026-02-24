import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/store/authStore';
import { useSocketStore } from '@/lib/socket';
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
                        const images = found.image_count || 0;
                        useSocketStore.getState().setInitialStats(total, input, output, count, images);
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
            {/* Game Interface */}
            <div className="flex-1 overflow-hidden relative">
                <ErrorBoundary>
                    <GameInterface
                        campaignId={id}
                        campaignName={campaign?.name || 'Loading...'}
                        isAdmin={isAdmin}
                        onBack={() => navigate(`/campaign_dash/${id}`)}
                        onOpenSettings={() => setIsSettingsOpen(true)}
                    />
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
