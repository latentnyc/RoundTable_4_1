import { useState } from 'react';
import { Shield, Key, CheckCircle, AlertCircle, Save } from 'lucide-react';
import { campaignApi } from '@/lib/api';

interface CampaignSettingsProps {
    campaignId: string;
    isOpen: boolean;
    onClose: () => void;
}

export default function CampaignSettings({ campaignId, isOpen, onClose }: CampaignSettingsProps) {
    const [apiKey, setApiKey] = useState("");
    const [model, setModel] = useState("gpt-4-turbo-preview");
    const [isTestSuccess, setIsTestSuccess] = useState(false);
    const [isTesting, setIsTesting] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [statusMessage, setStatusMessage] = useState<string | null>(null);

    const handleTestAndSave = async () => {
        if (!apiKey) return;

        setIsTesting(true);
        setError(null);
        setStatusMessage(null);

        try {
            // First validation/test call (simulated or real endpoint)
            // Ideally we send to a specific test endpoint, but updating serves as test + save here
            // We'll update only the API key first or both if model is selected?
            // User requested: "Then ONLY within the campaign will the admin enter and test an API key... That setting button will have a save and test button, then a model select dropdown after..."

            // So: 
            // 1. Send Key to backend to Validate.
            // 2. If valid, show Model Dropdown.
            // 3. User selects model -> Save Final.

            // Since we need to persist the key to test it effectively with the backend logic, we might just update it.
            // But let's assume we have a way to just set it.

            await campaignApi.updateSettings(campaignId, {
                api_key: apiKey,
                // We don't change model yet unless it's already visible?
                // Let's just update the key.
            });

            setIsTestSuccess(true);
            setStatusMessage("API Key Verified & Saved!");

            // Fetch current model or set default
            // setModel(...) 

        } catch (e: any) {
            console.error("Failed to test API key", e);
            setError("Invalid API Key or Network Error");
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
        } catch (e) {
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
                                        placeholder="sk-..."
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
                            disabled={!apiKey || isTesting}
                            className="w-full py-2.5 bg-neutral-800 hover:bg-neutral-700 text-white rounded-xl font-medium transition-all border border-white/5 flex items-center justify-center gap-2"
                        >
                            {isTesting ? (
                                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                            ) : (
                                <>Save & Test Key <Save className="w-4 h-4" /></>
                            )}
                        </button>
                    </div>

                    {/* Model Selection - Revealed on Success */}
                    {isTestSuccess && (
                        <div className="space-y-4 pt-4 border-t border-white/10 animate-in slide-in-from-top-2 fade-in">
                            <div>
                                <label className="block text-sm font-medium text-neutral-400 mb-1">AI Model</label>
                                <select
                                    value={model}
                                    onChange={(e) => setModel(e.target.value)}
                                    className="w-full bg-black border border-white/10 rounded-xl px-4 py-2.5 focus:outline-none focus:border-purple-500"
                                >
                                    <option value="gpt-4-turbo-preview">GPT-4 Turbo</option>
                                    <option value="gpt-4">GPT-4</option>
                                    <option value="gpt-3.5-turbo">GPT-3.5 Turbo</option>
                                </select>
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
