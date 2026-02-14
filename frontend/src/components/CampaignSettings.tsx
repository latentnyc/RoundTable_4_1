import { useState, useEffect } from 'react';
import { Shield, Key, CheckCircle, AlertCircle, Save } from 'lucide-react';
import { campaignApi } from '@/lib/api';

interface CampaignSettingsProps {
    campaignId: string;
    isOpen: boolean;
    onClose: () => void;
}

export default function CampaignSettings({ campaignId, isOpen, onClose }: CampaignSettingsProps) {
    const [apiKey, setApiKey] = useState("");
    const [model, setModel] = useState("");
    const [isTestSuccess, setIsTestSuccess] = useState(false);

    // Fetch current settings on open
    // Fetch current settings on open
    useEffect(() => {
        const fetchSettings = async () => {
            if (!isOpen) return;
            try {
                const campaign = await campaignApi.get(campaignId);
                // Only overwrite if not already set (or always overwrite on open? Let's overwrite)
                if (campaign.api_key) setApiKey(campaign.api_key);
                if (campaign.model) setModel(campaign.model);
            } catch (e) { console.error(e); }
        };
        fetchSettings();
    }, [isOpen, campaignId]);
    const [availableModels, setAvailableModels] = useState<string[]>([]);
    const [isTesting, setIsTesting] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [statusMessage, setStatusMessage] = useState<string | null>(null);

    const handleTestAndSave = async () => {
        if (!apiKey) return;

        setIsTesting(true);
        setError(null);
        setStatusMessage(null);

        try {
            // 1. Update Settings with new Key
            await campaignApi.updateSettings(campaignId, {
                api_key: apiKey
            });

            // 2. Test Key & Get Models
            const response = await campaignApi.testKey(apiKey);
            setAvailableModels(response.models);

            setIsTestSuccess(true);
            setStatusMessage("API Key Verified! Select a Model below.");

            // Set default model if current model is not in list or empty
            if (response.models.length > 0 && (!model || !response.models.includes(model))) {
                setModel(response.models[0]);
            }

        } catch (e: unknown) {
            console.error("Failed to test API key", e);
            const err = e as any;
            setError(err.response?.data?.detail || "Invalid API Key or Network Error");
            setIsTestSuccess(false);
        } finally {
            setIsTesting(false);
        }
    };

    const handleSaveModel = async () => {
        try {
            await campaignApi.updateSettings(campaignId, { model });
            setStatusMessage("Model Settings Saved!");
            setTimeout(onClose, 1000);
        } catch {
            setError("Failed to save model");
        }
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
            <div className="bg-neutral-900 border border-white/10 rounded-2xl w-full max-w-md shadow-2xl relative overflow-hidden">
                <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-purple-500 to-pink-500" />

                <div className="p-6 space-y-6">
                    <div className="flex justify-between items-start">
                        <div>
                            <h2 className="text-xl font-bold text-white flex items-center gap-2">
                                <Shield className="w-5 h-5 text-purple-400" />
                                Campaign Settings
                            </h2>
                            <p className="text-sm text-neutral-400 mt-1">
                                Secure Configuration (Admin Only)
                            </p>
                        </div>
                        <button onClick={onClose} className="text-neutral-500 hover:text-white">✕</button>
                    </div>

                    <div className="space-y-4">
                        <div>
                            <label className="block text-sm font-medium text-neutral-400 mb-1">OpenAI API Key</label>
                            <div className="flex gap-2">
                                <div className="relative flex-1">
                                    <Key className="absolute left-3 top-3 w-4 h-4 text-neutral-500" />
                                    <input
                                        type="password"
                                        value={apiKey}
                                        onChange={(e) => setApiKey(e.target.value)}
                                        placeholder="sk-... (Leave blank to use System Key)"
                                        className="w-full bg-black border border-white/10 rounded-xl pl-10 pr-4 py-2.5 focus:outline-none focus:border-purple-500 transition-colors placeholder-neutral-700"
                                    />
                                </div>
                            </div>
                        </div>

                        {error && (
                            <div className="text-red-400 text-sm bg-red-900/20 p-2 rounded flex items-center gap-2">
                                <AlertCircle className="w-4 h-4" /> {error}
                            </div>
                        )}

                        {statusMessage && (
                            <div className="text-green-400 text-sm bg-green-900/20 p-2 rounded flex items-center gap-2">
                                <CheckCircle className="w-4 h-4" /> {statusMessage}
                            </div>
                        )}

                        <button
                            onClick={handleTestAndSave}
                            disabled={isTesting}
                            className="w-full py-2.5 bg-neutral-800 hover:bg-neutral-700 text-white rounded-xl font-medium transition-all border border-white/5 flex items-center justify-center gap-2"
                        >
                            {isTesting ? (
                                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                            ) : (
                                <>{apiKey ? "Save & Test Key" : "Use System Key"} <Save className="w-4 h-4" /></>
                            )}
                        </button>
                    </div>

                    {/* Model Selection - Revealed on Success */}
                    {/* Model Selection - Revealed on Success or if Model is already set */}
                    {(isTestSuccess || availableModels.length > 0 || model) && (
                        <div className="space-y-4 pt-4 border-t border-white/10 animate-in slide-in-from-top-2 fade-in">
                            <div>
                                <label className="block text-sm font-medium text-neutral-400 mb-1">AI Model</label>
                                <select
                                    value={model}
                                    onChange={(e) => setModel(e.target.value)}
                                    className="w-full bg-black border border-white/10 rounded-xl px-4 py-2.5 focus:outline-none focus:border-purple-500 text-white"
                                >
                                    <option value="" disabled>Select a model...</option>
                                    {/* If current model is set but not in list (e.g. before test), show it */}
                                    {model && !availableModels.includes(model) && (
                                        <option value={model}>{model} (Current)</option>
                                    )}
                                    {availableModels.map((m) => (
                                        <option key={m} value={m}>{m}</option>
                                    ))}
                                </select>
                                {!isTestSuccess && availableModels.length === 0 && (
                                    <p className="text-[10px] text-neutral-500 mt-1">
                                        * Re-test API key to refresh available models.
                                    </p>
                                )}
                            </div>

                            <button
                                onClick={handleSaveModel}
                                className="w-full py-2.5 bg-purple-600 hover:bg-purple-500 text-white rounded-xl font-bold transition-colors shadow-lg shadow-purple-900/20"
                            >
                                Confirm Settings
                            </button>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
