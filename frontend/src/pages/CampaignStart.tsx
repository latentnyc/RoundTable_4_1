import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/store/authStore';
import { Plus, Play, ArrowRight, Shield, LogOut, Trash2 } from 'lucide-react';
import { campaignApi, CampaignTemplate } from '@/lib/api';

interface Campaign {
    id: string;
    name: string;
    description?: string;
    gm_id: string;
    status: string;
    created_at: string;
    template_id?: string;
}

export default function CampaignStart() {
    const { user, profile, signOut } = useAuthStore();
    const navigate = useNavigate();

    // Campaign List State
    const [campaigns, setCampaigns] = useState<Campaign[]>([]);
    const [isLoadingCampaigns, setIsLoadingCampaigns] = useState(true);
    const [selectedCampaignId, setSelectedCampaignId] = useState<string>("");

    // Templates State
    const [templates, setTemplates] = useState<CampaignTemplate[]>([]);
    const [isLoadingTemplates, setIsLoadingTemplates] = useState(false);

    // Deletion State
    const [campaignToDelete, setCampaignToDelete] = useState<string | null>(null);
    const [isDeleting, setIsDeleting] = useState(false);

    // Creation State
    // const [isCreating, setIsCreating] = useState(false); // Unused
    const [newCampaignName, setNewCampaignName] = useState("");
    const [selectedTemplate, setSelectedTemplate] = useState<string>("");
    // const [apiKey, setApiKey] = useState(""); // Removed per request
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Initial Fetch
    useEffect(() => {
        fetchCampaigns();
        fetchTemplates();
    }, []);

    const fetchCampaigns = async () => {
        setIsLoadingCampaigns(true);
        try {
            const data = await campaignApi.list();
            setCampaigns(data);
            if (data.length > 0) {
                // Select first by default if not set
                if (!selectedCampaignId) setSelectedCampaignId(data[0].id);
            }
        } catch (e) {
            console.error("Failed to fetch campaigns", e);
        } finally {
            setIsLoadingCampaigns(false);
        }
    };

    const fetchTemplates = async () => {
        setIsLoadingTemplates(true);
        try {
            const data = await campaignApi.listTemplates();
            setTemplates(data);
            if (data.length > 0) {
                // Default to Goblin Combat Test if available
                const defaultTemplate = data.find(t => t.id === "combat_test_goblin");
                setSelectedTemplate(defaultTemplate ? defaultTemplate.id : data[0].id);
            }
        } catch (e) {
            console.error("Failed to fetch templates", e);
        } finally {
            setIsLoadingTemplates(false);
        }
    };

    const handleCreateCampaign = async () => {
        if (!newCampaignName.trim()) return;
        if (!user?.uid) {
            setError("User not authenticated");
            return;
        }

        setIsSubmitting(true);
        setError(null);
        try {
            // Note: API key/Model are now set INSIDE the campaign settings, not at creation
            // We'll pass empty/defaults for now or update the backend to not require them at creation
            await campaignApi.create({
                name: newCampaignName,
                gm_id: user?.uid,
                // api_key: apiKey, // Removed
                model: "gemini-3-flash-preview", // Default to flash for speed/cost equivalent
                system_prompt: "You are a Dungeon Master.",
                template_id: selectedTemplate || undefined
            });

            setNewCampaignName("");
            // setIsCreating(false);
            fetchCampaigns(); // Refresh list
        } catch (e: any) {
            console.error("Failed to create campaign", e);
            setError(e.response?.data?.detail || "Failed to create campaign");
        } finally {
            setIsSubmitting(false);
        }
    };

    const handleEnterCampaign = () => {
        if (selectedCampaignId) {
            navigate(`/campaign_dash/${selectedCampaignId}`); // Redirect to dashboard instead of direct game
            // We need to ensure the store knows the selected campaign.
            // It is already set via setSelectedCampaignId but we might want to persis/check it.
        }
    };

    const handleDeleteClick = (e: React.MouseEvent, id: string) => {
        e.stopPropagation();
        if (!profile?.is_admin) return;
        setCampaignToDelete(id);
    };

    const confirmDelete = async () => {
        if (!campaignToDelete) return;

        setIsDeleting(true);
        try {
            await campaignApi.delete(campaignToDelete);
            if (selectedCampaignId === campaignToDelete) setSelectedCampaignId("");
            fetchCampaigns();
            setCampaignToDelete(null);
        } catch (e) {
            console.error("Failed to delete campaign", e);
            setError("Failed to delete campaign");
        } finally {
            setIsDeleting(false);
        }
    };

    const isAdmin = profile?.is_admin || false;
    const selectedTemplateData = templates.find(t => t.id === selectedTemplate);

    return (
        <div className="min-h-screen bg-black text-white p-6 md:p-12">

            {/* Delete Confirmation Modal */}
            {campaignToDelete && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
                    <div className="bg-neutral-900 border border-red-500/30 rounded-2xl p-6 max-w-md w-full shadow-2xl shadow-red-900/20">
                        <h3 className="text-xl font-bold text-white mb-2 flex items-center gap-2">
                            <Trash2 className="w-5 h-5 text-red-500" />
                            Delete Campaign?
                        </h3>
                        <p className="text-neutral-400 mb-6">
                            Are you sure you want to delete this campaign? This action cannot be undone and will remove all associated characters and chat logs.
                        </p>

                        <div className="flex justify-end gap-3">
                            <button
                                onClick={() => setCampaignToDelete(null)}
                                className="px-4 py-2 bg-transparent hover:bg-white/5 text-neutral-300 rounded-lg transition-colors border border-transparent hover:border-white/10"
                                disabled={isDeleting}
                            >
                                Cancel
                            </button>
                            <button
                                onClick={confirmDelete}
                                disabled={isDeleting}
                                className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg transition-colors font-medium flex items-center gap-2"
                            >
                                {isDeleting ? "Deleting..." : "Delete Permanently"}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            <div className="max-w-4xl mx-auto space-y-12">
                {/* Header */}
                <header className="flex justify-between items-center border-b border-white/10 pb-6">
                    <div>
                        <h1 className="text-4xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-purple-400">
                            Welcome, {profile?.username || user?.email?.split('@')[0] || "Adventurer"}
                        </h1>
                        <p className="text-neutral-400 mt-2">Select a campaign to begin your journey.</p>
                    </div>

                    <div className="flex items-center gap-4">
                        {/* Admin Badge if applicable */}
                        {isAdmin && (
                            <div className="flex items-center gap-4">
                                <div className="px-3 py-1 bg-purple-900/30 border border-purple-500/30 rounded-full text-xs text-purple-300 flex items-center gap-2">
                                    <Shield className="w-3 h-3" />
                                    Admin Access
                                </div>
                                <button
                                    onClick={() => navigate('/users')}
                                    className="text-sm text-neutral-400 hover:text-white transition-colors"
                                >
                                    Manage Users
                                </button>
                            </div>
                        )}

                        <button
                            onClick={() => signOut()}
                            className="flex items-center gap-2 px-4 py-2 bg-neutral-800 hover:bg-neutral-700 text-neutral-300 rounded-lg transition-colors text-sm font-medium border border-white/5"
                        >
                            <LogOut className="w-4 h-4" />
                            Sign Out
                        </button>
                    </div>
                </header>

                <main className="grid gap-8 md:grid-cols-2">
                    {/* Left Column: Select & Enter */}
                    <div className="space-y-6">
                        <h2 className="text-xl font-semibold text-white flex items-center gap-2">
                            <Play className="w-5 h-5 text-purple-400" />
                            Continue Adventure
                        </h2>

                        <div className="bg-neutral-900/50 p-6 rounded-2xl border border-white/5 space-y-4">
                            {isLoadingCampaigns ? (
                                <div className="text-center py-8 text-neutral-500">Loading campaigns...</div>
                            ) : campaigns.length > 0 ? (
                                <>
                                    <div className="space-y-2">
                                        <label className="block text-sm font-medium text-neutral-400 mb-2">Select Campaign</label>
                                        <div className="space-y-2 max-h-[400px] overflow-y-auto pr-2 custom-scrollbar">
                                            {campaigns.map(c => (
                                                <div
                                                    key={c.id}
                                                    onClick={() => setSelectedCampaignId(c.id)}
                                                    className={`w-full text-left px-4 py-3 rounded-xl border transition-all flex items-center justify-between cursor-pointer group ${selectedCampaignId === c.id
                                                        ? 'bg-purple-900/20 border-purple-500/50'
                                                        : 'bg-black border-white/10 hover:border-white/20'
                                                        }`}
                                                >
                                                    <div>
                                                        <div className={`font-medium ${selectedCampaignId === c.id ? 'text-purple-300' : 'text-neutral-300'}`}>
                                                            {c.name}
                                                        </div>
                                                        {c.status !== 'active' && (
                                                            <div className="text-xs text-neutral-500">{c.status}</div>
                                                        )}
                                                    </div>

                                                    <button
                                                        onClick={(e) => handleDeleteClick(e, c.id)}
                                                        disabled={!isAdmin}
                                                        title={isAdmin ? "Delete Campaign" : "Admin Only"}
                                                        className={`p-2 rounded-lg transition-colors ${isAdmin
                                                            ? 'text-neutral-500 hover:text-red-400 hover:bg-white/5'
                                                            : 'text-neutral-700 cursor-not-allowed'
                                                            }`}
                                                    >
                                                        <Trash2 className="w-4 h-4" />
                                                    </button>
                                                </div>
                                            ))}
                                        </div>
                                    </div>

                                    <button
                                        onClick={handleEnterCampaign}
                                        disabled={!selectedCampaignId}
                                        className="w-full py-4 bg-white text-black rounded-xl font-bold hover:bg-neutral-200 transition-all flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed group"
                                    >
                                        Enter Campaign
                                        <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                                    </button>
                                </>
                            ) : (
                                <div className="text-center py-8 text-neutral-500">
                                    No campaigns found.
                                    {isAdmin ? " Create one to get started." : " Ask your DM to create one."}
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Right Column: Create (Admin Only) */}
                    {isAdmin && (
                        <div className="space-y-6">
                            <h2 className="text-xl font-semibold text-white flex items-center gap-2">
                                <Plus className="w-5 h-5 text-green-400" />
                                New Campaign
                            </h2>

                            <div className="bg-neutral-900/50 p-6 rounded-2xl border border-white/5 space-y-4">
                                <div>
                                    <label className="block text-sm font-medium text-neutral-400 mb-2">Campaign Name</label>
                                    <input
                                        type="text"
                                        value={newCampaignName}
                                        onChange={(e) => setNewCampaignName(e.target.value)}
                                        placeholder="E.g. The Curse of Strahd"
                                        className="w-full bg-black border border-white/10 rounded-xl px-4 py-3 focus:outline-none focus:border-purple-500 transition-colors placeholder-neutral-700"
                                    />
                                </div>

                                <div>
                                    <label className="block text-sm font-medium text-neutral-400 mb-2">Template (Optional)</label>
                                    <select
                                        value={selectedTemplate}
                                        onChange={(e) => setSelectedTemplate(e.target.value)}
                                        className="w-full bg-black border border-white/10 rounded-xl px-4 py-3 focus:outline-none focus:border-purple-500 transition-colors text-white"
                                        disabled={isLoadingTemplates}
                                    >
                                        <option value="">Blank Campaign</option>
                                        {templates.map(t => (
                                            <option key={t.id} value={t.id}>{t.name} ({t.genre})</option>
                                        ))}
                                    </select>
                                </div>

                                {/* Friendly Description Display */}
                                {selectedTemplateData && (
                                    <div className="bg-black/50 p-4 rounded-xl border border-white/10 text-sm text-neutral-300 italic">
                                        {selectedTemplateData.description}
                                    </div>
                                )}

                                {error && (
                                    <div className="text-red-400 text-sm bg-red-900/20 p-2 rounded border border-red-900/50">
                                        {error}
                                    </div>
                                )}

                                <button
                                    onClick={handleCreateCampaign}
                                    disabled={!newCampaignName.trim() || isSubmitting}
                                    className="w-full py-3 bg-purple-600 hover:bg-purple-700 text-white rounded-xl font-semibold transition-all border border-white/5 flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-purple-900/20"
                                >
                                    {isSubmitting ? (
                                        <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                                    ) : (
                                        <>Create Campaign</>
                                    )}
                                </button>
                                <p className="text-xs text-neutral-500 text-center">
                                    API Key & Model settings are configured after creation.
                                </p>
                            </div>
                        </div>
                    )}
                </main>
            </div>
        </div>
    );
}
