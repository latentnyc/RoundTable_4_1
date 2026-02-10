
import { useCharacterStore } from '@/store/characterStore';
import { useAuthStore } from '@/store/authStore';
import { useCampaignStore } from '@/store/campaignStore';
import { useEffect, useState } from 'react';
import { campaignApi, characterApi, settingsApi, Character, Campaign, DatasetInfo } from '@/lib/api';
import { useNavigate, Link } from 'react-router-dom';
import { Trash2, User, Bot, Ghost, Play, Settings, Loader2, Check, X } from 'lucide-react';

import { useParams } from 'react-router-dom';

export default function CampaignDash() {
    const { id } = useParams<{ id: string }>();
    const { deleteCharacter } = useCharacterStore();
    const { profile } = useAuthStore();
    const { setSelectedCampaignId } = useCampaignStore();
    const [characters, setCharacters] = useState<Character[]>([]);

    // Settings State
    const [showSettings, setShowSettings] = useState(false);
    const [currentCampaign, setCurrentCampaign] = useState<Campaign | null>(null);
    const [modelList, setModelList] = useState<string[]>([]);
    const [isTesting, setIsTesting] = useState(false);
    const [testStatus, setTestStatus] = useState<'idle' | 'success' | 'error'>('idle');

    // Dataset State
    const [datasetList, setDatasetList] = useState<DatasetInfo[]>([]);
    const [selectedDatasetId, setSelectedDatasetId] = useState<string>("basic");
    const [loadActionStatus, setLoadActionStatus] = useState<Record<string, 'idle' | 'loading' | 'success' | 'error'>>({});

    // Status Checks
    const [apiKeyPresent, setApiKeyPresent] = useState(false);
    const [datasetLoaded, setDatasetLoaded] = useState(false);
    const [checksLoaded, setChecksLoaded] = useState(false);

    const navigate = useNavigate();

    const fetchStatusChecks = async () => {
        if (!id) return;
        try {
            // Check Campaign API Key
            // We fetch the latest campaign data to be sure
            const camp = await campaignApi.get(id);
            setApiKeyPresent(!!camp.api_key_verified || !!camp.api_key_configured);

            // Check Dataset Status
            const datasets = await settingsApi.getDatasets();
            const isLoaded = datasets.some(d => d.is_loaded);
            setDatasetLoaded(isLoaded);

            setChecksLoaded(true);
        } catch (e) {
            console.error("Failed to perform status checks", e);
        }
    };

    const openSettings = async () => {
        if (!id) return;
        try {
            const camp = await campaignApi.get(id);
            setCurrentCampaign(camp);
            setShowSettings(true);
            setTestStatus('idle');

            // Fetch datasets
            try {
                const list = await settingsApi.getDatasets();
                setDatasetList(list);
                // Default selection logic: Pick loaded one, or first, or 'basic'
                const loaded = list.find(d => d.is_loaded);
                if (loaded) setSelectedDatasetId(loaded.id);
                else if (list.length > 0) setSelectedDatasetId(list[0].id);
            } catch (e) {
                console.error("Failed to fetch datasets", e);
            }

            // Also update our top-level status
            setApiKeyPresent(!!camp.api_key_verified || !!camp.api_key_configured);
            // We will update datasetLoaded after closing settings or if we load it inside settings

            if (camp.api_key) {
                setIsTesting(true);
                try {
                    const res = await campaignApi.testKey(camp.api_key);
                    setModelList(res.models);
                    setTestStatus('success');
                } catch (e) {
                    console.error("Failed to auto-fetch models", e);
                } finally {
                    setIsTesting(false);
                }
            } else {
                setModelList([]);
            }
        } catch (e) {
            console.error("Failed to load campaign settings", e);
            alert("Failed to load settings. You might not have permission.");
        }
    };

    const handleLoadDataset = async (datasetId: string) => {
        setLoadActionStatus(prev => ({ ...prev, [datasetId]: 'loading' }));
        try {
            await settingsApi.loadDataset(datasetId);
            // Refresh list to update status
            const list = await settingsApi.getDatasets();
            setDatasetList(list);
            setLoadActionStatus(prev => ({ ...prev, [datasetId]: 'success' }));

            // Update global status
            setDatasetLoaded(true);
        } catch (e) {
            console.error("Failed to load dataset", e);
            setLoadActionStatus(prev => ({ ...prev, [datasetId]: 'error' }));
            alert("Failed to load dataset. Check server logs.");
        }
    };

    const saveSettings = async () => {
        if (!currentCampaign || !id) return;
        try {
            await campaignApi.update(id, {
                name: currentCampaign.name,
                api_key: currentCampaign.api_key,
                // If we successfully tested THIS key in THIS session, verify it.
                // Otherwise if it was ALREADY verified and we didn't change it, it stays verified (handled by backend if we don't send false)
                // But simplified: If testStatus is success, we send true. 
                // If we didn't test but we touched the key? Backend handles resetting if key passes but verified not passed.
                // Safest: Send verified=true if testStatus='success'.
                api_key_verified: testStatus === 'success' ? true : undefined,
                model: currentCampaign.model,
                system_prompt: currentCampaign.system_prompt
            });

            // Update status - fetch fresh to be sure or optimistic
            // optimistic:
            setApiKeyPresent(testStatus === 'success' || (!!currentCampaign.api_key_verified && testStatus === 'idle') || !!currentCampaign.api_key_configured);
            // Actually relying on the save result would be better but let's just use what we know.
            if (testStatus === 'success') {
                setApiKeyPresent(true);
            } else {
                setApiKeyPresent(false);
            }

            setShowSettings(false);
        } catch (e) {
            console.error("Failed to save settings", e);
            alert("Failed to save settings");
        }
    };

    const fetchCharacters = () => {
        if (profile?.id && id) {
            // Fetch characters for the specific campaign
            characterApi.list(profile.id, id).then(setCharacters);
        }
    };

    useEffect(() => {
        if (id) {
            setSelectedCampaignId(id);
            fetchCharacters();
            fetchStatusChecks();
        }
    }, [profile, id]);

    const handleToggleMode = async (e: React.MouseEvent, char: Character) => {
        e.stopPropagation();

        if (!apiKeyPresent || !datasetLoaded) {
            alert("Please set API Key and Load Dataset in Settings first.");
            return;
        }

        const modes: Character['control_mode'][] = ['human', 'ai', 'disabled'];
        // Default to 'human' if undefined
        const currentMode = char.control_mode || 'human';
        const currentIdx = modes.indexOf(currentMode);
        const nextMode = modes[(currentIdx + 1) % modes.length];

        // Check active limit
        const activeCount = characters.filter(c => (c.control_mode || 'human') !== 'disabled').length;
        // If we are enabling a disabled character (increasing active count)
        if (currentMode === 'disabled' && nextMode !== 'disabled' && activeCount >= 4) {
            alert("Maximum of 4 active characters allowed.");
            return;
        }

        // Optimistic update
        setCharacters(chars => chars.map(c => c.id === char.id ? { ...c, control_mode: nextMode } : c));

        try {
            await characterApi.update(char.id, { control_mode: nextMode });
        } catch (err) {
            console.error("Failed to update mode", err);
            // Revert on failure
            setCharacters(chars => chars.map(c => c.id === char.id ? { ...c, control_mode: currentMode } : c));
        }
    };

    const handleDelete = async (e: React.MouseEvent, id: string) => {
        e.stopPropagation();
        if (confirm('Are you sure you want to delete this character?')) {
            await deleteCharacter(id);
            fetchCharacters(); // Refresh list
        }
    };

    const isReady = apiKeyPresent && datasetLoaded;

    return (
        <div className="min-h-screen bg-neutral-950 text-white p-8">
            <div className="flex justify-between items-center mb-6">
                <div>
                    <div className="flex items-center gap-4">
                        <h1 className="text-3xl font-bold">Campaign Dashboard</h1>
                        {checksLoaded && (
                            <div className="flex gap-2">
                                <div
                                    className={`flex items-center gap-1 text-xs px-2 py-1 rounded border ${apiKeyPresent ? 'bg-green-500/10 border-green-500/20 text-green-400' : 'bg-red-500/10 border-red-500/20 text-red-400'}`}
                                    title={apiKeyPresent ? "API Key Configured" : "API Key Missing"}
                                >
                                    <div className={`w-2 h-2 rounded-full ${apiKeyPresent ? 'bg-green-500' : 'bg-red-500'}`} />
                                    <span className="font-mono">API_KEY</span>
                                </div>
                                <div
                                    className={`flex items-center gap-1 text-xs px-2 py-1 rounded border ${datasetLoaded ? 'bg-green-500/10 border-green-500/20 text-green-400' : 'bg-red-500/10 border-red-500/20 text-red-400'}`}
                                    title={datasetLoaded ? "Dataset Loaded" : "Dataset Missing"}
                                >
                                    <div className={`w-2 h-2 rounded-full ${datasetLoaded ? 'bg-green-500' : 'bg-red-500'}`} />
                                    <span className="font-mono">DATA</span>
                                </div>
                            </div>
                        )}
                    </div>
                    {profile && <p className="text-neutral-400">Welcome, {profile.username}</p>}
                </div>
                <div className="flex">
                    <button
                        onClick={openSettings}
                        className="flex items-center gap-2 bg-neutral-800 hover:bg-neutral-700 text-white px-6 py-3 rounded-lg font-bold transition-colors mr-3"
                    >
                        <Settings className="w-5 h-5" />
                        Settings
                    </button>
                    <button
                        onClick={() => navigate('/campaign_start')}
                        className="flex items-center gap-2 bg-purple-600 hover:bg-purple-700 text-white px-6 py-3 rounded-lg font-bold transition-colors shadow-lg shadow-purple-900/20"
                    >
                        <Play className="w-5 h-5" />
                        Switch Campaign
                    </button>
                </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {characters.map(char => {
                    const mode = char.control_mode || 'human';
                    let borderColor = mode === 'ai' ? 'border-purple-500/50' : mode === 'disabled' ? 'border-neutral-800' : 'border-green-500/30';
                    let opacity = mode === 'disabled' ? 'opacity-50' : 'opacity-100';

                    // Force greyed out look if not ready
                    if (!isReady) {
                        borderColor = 'border-neutral-800';
                        opacity = 'opacity-50 grayscale';
                    }

                    return (
                        <div
                            key={char.id}
                            onClick={() => {
                                if (!isReady) {
                                    alert("Please set API Key and Load Dataset in Settings first.");
                                    return;
                                }
                                if (!id) {
                                    navigate('/campaign_start');
                                    return;
                                }
                            }}
                            className={`bg-neutral-900 border ${borderColor} p-6 rounded-xl transition-all ${opacity} relative ${isReady ? 'hover:border-purple-500 cursor-pointer' : 'cursor-not-allowed'}`}
                        >
                            <div className="flex justify-between items-start mb-2">
                                <h2 className="text-xl font-bold text-neutral-200">{char.name}</h2>
                                <div className="flex gap-2">
                                    <button
                                        onClick={(e) => {
                                            if (!isReady) return;
                                            e.stopPropagation();
                                            handleToggleMode(e, char);
                                        }}
                                        disabled={!isReady}
                                        className={`p-2 rounded transition-colors ${!isReady ? 'text-neutral-600 cursor-not-allowed' :
                                            mode === 'human' ? 'bg-green-500/20 text-green-400 hover:bg-green-500/30' :
                                                mode === 'ai' ? 'bg-purple-500/20 text-purple-400 hover:bg-purple-500/30' :
                                                    'bg-neutral-800 text-neutral-500 hover:bg-neutral-700'
                                            }`}
                                        title={`Mode: ${mode.toUpperCase()}`}
                                    >
                                        {mode === 'human' && <User className="w-5 h-5" />}
                                        {mode === 'ai' && <Bot className="w-5 h-5" />}
                                        {mode === 'disabled' && <Ghost className="w-5 h-5" />}
                                    </button>
                                    <button
                                        onClick={(e) => {
                                            if (!isReady) return;
                                            handleDelete(e, char.id);
                                        }}
                                        disabled={!isReady}
                                        className={`text-neutral-600 p-2 rounded transition-colors ${isReady ? 'hover:text-red-500 hover:bg-neutral-800' : 'cursor-not-allowed opacity-50'}`}
                                        title="Delete Character"
                                    >
                                        <Trash2 className="w-5 h-5" />
                                    </button>
                                </div>
                            </div>
                            <p className="text-neutral-300 mb-4">{char.role} - Level {char.level}</p>

                            <div className="grid grid-cols-2 gap-2 text-sm text-neutral-500">
                                {char.sheet_data?.stats && Object.entries(char.sheet_data.stats).map(([stat, val]) => (
                                    <div key={stat} className="flex justify-between">
                                        <span className="capitalize">{stat}</span>
                                        <span className="text-white font-mono">{val as number}</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    );
                })}

                {characters.length < 4 && (
                    <Link
                        to={isReady ? "/create-character" : "#"}
                        onClick={(e) => {
                            if (!isReady) {
                                e.preventDefault();
                                alert("Please configure campaign settings first.");
                            }
                        }}
                        className={`flex flex-col items-center justify-center p-6 border border-dashed border-neutral-800 rounded-xl transition-colors min-h-[200px] ${isReady ? 'hover:bg-neutral-900/50 hover:border-neutral-700 cursor-pointer text-decoration-none' : 'opacity-30 cursor-not-allowed'}`}
                    >
                        <span className="text-4xl mb-2 text-neutral-600">+</span>
                        <span className="text-neutral-500">Create New Character</span>
                    </Link>
                )}
            </div>

            <div className="flex justify-center mt-8">
                <button
                    disabled={!isReady || characters.filter(c => c.control_mode === 'human').length !== 1}
                    onClick={() => {
                        const humanChar = characters.find(c => c.control_mode === 'human');
                        if (humanChar && id) {
                            useCharacterStore.getState().selectCharacter(humanChar.id);
                            navigate(`/campaign_main/${id}`);
                        }
                    }}
                    className={`
                        flex items-center gap-2 px-8 py-4 rounded-lg font-bold text-lg transition-all shadow-lg
                        ${isReady && characters.filter(c => c.control_mode === 'human').length === 1
                            ? 'bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white shadow-purple-900/20'
                            : 'bg-neutral-800 text-neutral-500 cursor-not-allowed'}
                    `}
                >
                    <Play className="w-6 h-6" />
                    Enter Campaign
                </button>
            </div>
            {isReady && characters.filter(c => c.control_mode === 'human').length !== 1 && (
                <p className="text-center text-neutral-500 mt-2">
                    {characters.filter(c => c.control_mode === 'human').length === 0 ? "Select a character to play as (Set mode to Human)" : "You can only play as one character at a time"}
                </p>
            )}
            {!isReady && (
                <p className="text-center text-red-500 mt-2 font-bold">
                    Campaign Configuration Missing: {(!apiKeyPresent ? "API Key" : "")} {(!apiKeyPresent && !datasetLoaded ? "&" : "")} {(!datasetLoaded ? "Dataset" : "")}
                </p>
            )}

            {/* Campaign Settings Modal */}
            {showSettings && currentCampaign && (
                <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
                    <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-8 max-w-md w-full space-y-6">
                        <h2 className="text-2xl font-bold">Campaign Settings</h2>

                        <div className="space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-neutral-400 mb-1">Campaign Name</label>
                                <input
                                    type="text"
                                    value={currentCampaign.name}
                                    onChange={e => setCurrentCampaign({ ...currentCampaign, name: e.target.value })}
                                    className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-4 py-2 text-white"
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-neutral-400 mb-1">API Key</label>
                                <div className="space-y-2">
                                    <input
                                        type="password"
                                        value={currentCampaign.api_key || ''}
                                        onChange={e => setCurrentCampaign({ ...currentCampaign, api_key: e.target.value })}
                                        placeholder="Sk-..."
                                        className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-4 py-2 text-white"
                                    />
                                    <button
                                        onClick={async () => {
                                            if (!currentCampaign.api_key) return;
                                            setIsTesting(true);
                                            setTestStatus('idle');
                                            try {
                                                const res = await campaignApi.testKey(currentCampaign.api_key);
                                                setModelList(res.models);
                                                setTestStatus('success');
                                            } catch (e) {
                                                console.error(e);
                                                setTestStatus('error');
                                            } finally {
                                                setIsTesting(false);
                                            }
                                        }}
                                        disabled={!currentCampaign.api_key || isTesting}
                                        className="w-full bg-neutral-800 hover:bg-neutral-700 disabled:opacity-50 text-white text-sm py-2 rounded-lg transition-colors flex items-center justify-center gap-2"
                                    >
                                        {isTesting ? <Loader2 className="w-4 h-4 animate-spin" /> :
                                            testStatus === 'success' ? <Check className="w-4 h-4 text-green-500" /> :
                                                testStatus === 'error' ? <X className="w-4 h-4 text-red-500" /> : null}
                                        {isTesting ? 'Testing...' :
                                            testStatus === 'success' ? 'Validated & Models Loaded' :
                                                testStatus === 'error' ? 'Validation Failed' : 'Save & Test Key'}
                                    </button>
                                </div>
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-neutral-400 mb-1">Model</label>
                                <select
                                    value={currentCampaign.model || 'gemini-1.5-pro'}
                                    onChange={e => setCurrentCampaign({ ...currentCampaign, model: e.target.value })}
                                    className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-4 py-2 text-white"
                                >
                                    {modelList.length > 0 ? (
                                        modelList.map(m => (
                                            <option key={m} value={m}>{m}</option>
                                        ))
                                    ) : (
                                        <>
                                            <option value="gemini-1.5-pro">Gemini 1.5 Pro</option>
                                            <option value="gemini-1.5-flash">Gemini 1.5 Flash</option>
                                            <option value="gemini-2.0-flash">Gemini 2.0 Flash</option>
                                            <option disabled>-- Test API key to fetch more --</option>
                                        </>
                                    )}
                                </select>
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-neutral-400 mb-1">System Prompt</label>
                                <textarea
                                    value={currentCampaign.system_prompt || ''}
                                    onChange={e => setCurrentCampaign({ ...currentCampaign, system_prompt: e.target.value })}
                                    placeholder="Enter custom system prompt..."
                                    className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-4 py-2 text-white min-h-[100px]"
                                />
                            </div>

                            {/* Dataset Selection */}
                            <div className="pt-4 border-t border-neutral-800 text-sm">
                                <label className="block text-sm font-medium text-neutral-400 mb-1">Game Data (Global)</label>
                                <div className="flex gap-2">
                                    <select
                                        value={selectedDatasetId}
                                        onChange={e => setSelectedDatasetId(e.target.value)}
                                        className="flex-1 bg-neutral-800 border border-neutral-700 rounded-lg px-4 py-2 text-white"
                                    >
                                        {datasetList.map(d => (
                                            <option key={d.id} value={d.id}>
                                                {d.name} {d.is_loaded ? '(Loaded)' : '(Not Loaded)'}
                                            </option>
                                        ))}
                                        {datasetList.length === 0 && <option value="basic">Basic (Default)</option>}
                                    </select>

                                    {(() => {
                                        const selected = datasetList.find(d => d.id === selectedDatasetId);
                                        // If selected is not loaded, show Load button
                                        // OR if we just want to allow reloading? 
                                        // The prompt says "logic to investigate if this json data has been loaded... with a 'load' button to accomplish this."
                                        // Implies if not loaded, show load.
                                        if (selected && !selected.is_loaded) {
                                            const status = loadActionStatus[selected.id] || 'idle';
                                            return (
                                                <button
                                                    onClick={() => handleLoadDataset(selected.id)}
                                                    disabled={status === 'loading'}
                                                    className="bg-neutral-700 hover:bg-neutral-600 text-white px-3 py-2 rounded-lg font-medium transition-colors flex items-center gap-2"
                                                >
                                                    {status === 'loading' ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
                                                    {status === 'loading' ? 'Loading...' : 'Load'}
                                                </button>
                                            )
                                        }
                                        // If loaded, maybe show a checkmark or nothing
                                        if (selected && selected.is_loaded) {
                                            return (
                                                <div className="flex items-center gap-2 px-3 py-2 text-green-500 bg-green-500/10 rounded-lg border border-green-500/20">
                                                    <Check className="w-4 h-4" />
                                                    <span className="text-xs font-bold">Active</span>
                                                </div>
                                            )
                                        }
                                        return null;
                                    })()}
                                </div>
                                <p className="text-xs text-neutral-500 mt-1">
                                    {datasetList.find(d => d.id === selectedDatasetId)?.description || "Standard 5e Data"}
                                </p>
                            </div>
                        </div>

                        <div className="flex gap-3 pt-2">
                            <button
                                onClick={saveSettings}
                                className="flex-1 bg-purple-600 hover:bg-purple-500 py-3 rounded-lg font-bold"
                            >
                                Save Changes
                            </button>
                            <button
                                onClick={() => setShowSettings(false)}
                                className="flex-1 bg-neutral-800 hover:bg-neutral-700 py-3 rounded-lg font-medium"
                            >
                                Cancel
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
