
import { useCharacterStore } from '@/store/characterStore';
import { useAuthStore } from '@/store/authStore';
import { useCampaignStore } from '@/store/campaignStore';
import { useEffect, useState, useCallback } from 'react';
import { campaignApi, characterApi, settingsApi, Character, Campaign, CampaignParticipant } from '@/lib/api';
import { useNavigate, Link } from 'react-router-dom';
import { Trash2, User, Bot, Ghost, Play, Settings, Loader2, Check, X, Shield, Users } from 'lucide-react';

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
    // Datasets & Templates removed from settings UI

    const [isTesting, setIsTesting] = useState(false);
    const [testStatus, setTestStatus] = useState<'idle' | 'success' | 'error'>('idle');
    const [errorCountdown, setErrorCountdown] = useState(0);

    // Participant State
    const [participantStatus, setParticipantStatus] = useState<string | null>(null);
    const [participantRole, setParticipantRole] = useState<string | null>(null);
    const [showMemberlist, setShowMemberlist] = useState(false);
    const [showManagePlayers, setShowManagePlayers] = useState(false);
    const [participants, setParticipants] = useState<CampaignParticipant[]>([]);
    const [isLoadingParticipants, setIsLoadingParticipants] = useState(false);

    // Status Checks
    const [apiKeyPresent, setApiKeyPresent] = useState(false);
    const [datasetLoaded, setDatasetLoaded] = useState(false);
    const [checksLoaded, setChecksLoaded] = useState(false);
    const [joinCheckDone, setJoinCheckDone] = useState(false);

    const navigate = useNavigate();

    // Countdown Effect for Error Revert
    useEffect(() => {
        let interval: NodeJS.Timeout;
        if (testStatus === 'error') {
            setErrorCountdown(5);
            interval = setInterval(() => {
                setErrorCountdown(prev => {
                    if (prev <= 1) {
                        setTestStatus('idle');
                        return 0;
                    }
                    return prev - 1;
                });
            }, 1000);
        } else {
            setErrorCountdown(0);
        }
        return () => clearInterval(interval);
    }, [testStatus]);

    const fetchStatusChecks = useCallback(async () => {
        if (!id) return;
        try {
            // Check Campaign API Key AND Participant Status
            const camp = await campaignApi.get(id);
            // Strict check: Only green if verified
            setApiKeyPresent(!!camp.api_key_verified);

            // Participant Logic
            if (camp.user_status) {
                setParticipantStatus(camp.user_status);
                setParticipantRole(camp.user_role || 'player');
            } else {
                // Not joined? Auto-join
                try {
                    const res = await campaignApi.join(id);
                    setParticipantStatus(res.status);
                    setParticipantRole(res.role);
                } catch (e) {
                    console.error("Failed to join campaign", e);
                }
            }

            // Check Dataset Status
            const datasets = await settingsApi.getDatasets();
            const isLoaded = datasets.some(d => d.is_loaded);
            setDatasetLoaded(isLoaded);

            setChecksLoaded(true);
            setJoinCheckDone(true);
        } catch (e) {
            console.error("Failed to perform status checks", e);
        }
    }, [id]);

    const openSettings = async () => {
        if (!id) return;
        try {
            const camp = await campaignApi.get(id);
            setCurrentCampaign(camp);
            setShowSettings(true);
            setTestStatus('idle');

            // Datasets/Templates fetching removed
            // try {
            //     const [dList, tList] = await Promise.all([
            //         settingsApi.getDatasets(),
            //         settingsApi.getGameTemplates()
            //     ]);
            //     ...
            // } catch (e) { ... }

            // Also update our top-level status
            setApiKeyPresent(!!camp.api_key_verified);
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

    const fetchParticipants = async () => {
        if (!id) return;
        setIsLoadingParticipants(true);
        try {
            const data = await campaignApi.getParticipants(id);

            setParticipants(data);

        } catch (e) {
            console.error("Failed to fetch participants", e);
        } finally {
            setIsLoadingParticipants(false);
        }
    };

    const handleUpdateParticipant = async (userId: string, status: string) => {
        if (!id) return;
        try {
            await campaignApi.updateParticipant(id, userId, { status });
            fetchParticipants(); // Refresh
        } catch (e) {
            console.error("Failed to update participant", e);
            alert("Failed to update participant status");
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
            // Only strictly verified keys get the green light
            if (testStatus === 'success') {
                setApiKeyPresent(true);
            } else {
                // If status was 'idle', we might have kept previous verified state...
                // But better to be safe and assume false unless we just proved it or we re-fetch.
                // Re-fetching is safer.
                try {
                    const fresh = await campaignApi.get(id);
                    setApiKeyPresent(!!fresh.api_key_verified);
                } catch { setApiKeyPresent(false); }
            }

            setShowSettings(false);
        } catch (e) {
            console.error("Failed to save settings", e);
            alert("Failed to save settings");
        }
    };

    const fetchCharacters = useCallback(() => {
        if (profile?.id && id) {
            // Fetch characters for the specific campaign
            characterApi.list(profile.id, id).then(setCharacters);
        }
    }, [profile?.id, id]);

    useEffect(() => {
        if (id) {
            setSelectedCampaignId(id);
            fetchCharacters();
            fetchStatusChecks();
        }
    }, [id, setSelectedCampaignId, fetchCharacters, fetchStatusChecks]);

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
    const isGM = participantRole === 'gm' || profile?.is_admin;


    if (!joinCheckDone) {
        return <div className="min-h-screen bg-black text-white flex items-center justify-center">Loading...</div>;
    }

    if (participantStatus === 'interested') {
        return (
            <div className="min-h-screen bg-black text-white flex flex-col items-center justify-center p-6 text-center space-y-6">
                <div className="w-16 h-16 bg-purple-900/30 rounded-full flex items-center justify-center mb-4 animate-pulse">
                    <Shield className="w-8 h-8 text-purple-400" />
                </div>
                <h1 className="text-3xl font-bold">Request Pending</h1>
                <p className="text-neutral-400 max-w-md">
                    You have joined the campaign as an interested player.
                    <br />
                    Please wait for the GM to approve your request.
                </p>
                <button
                    onClick={() => { window.location.reload(); }}
                    className="px-6 py-2 bg-neutral-800 hover:bg-neutral-700 rounded-lg transition-colors"
                >
                    Check Status
                </button>
                <button
                    onClick={() => navigate('/campaign_start')}
                    className="text-neutral-500 hover:text-white text-sm"
                >
                    Back to Campaign List
                </button>
            </div>
        );
    }

    if (participantStatus === 'banned') {
        return (
            <div className="min-h-screen bg-black text-white flex flex-col items-center justify-center p-6 text-center space-y-6">
                <h1 className="text-3xl font-bold text-red-500">Access Denied</h1>
                <p className="text-neutral-400">You have been banned from this campaign.</p>
                <button onClick={() => navigate('/campaign_start')} className="text-neutral-300 hover:text-white">Back</button>
            </div>
        );
    }

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
                                    title={apiKeyPresent ? "API Key Configured & Verified" : "API Key Missing or Unverified"}
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
                <div className="flex gap-3">
                    <button
                        onClick={() => {
                            fetchParticipants();
                            setShowMemberlist(true);
                        }}
                        className="flex items-center gap-2 bg-neutral-800 hover:bg-neutral-700 text-white px-4 py-2 rounded-lg font-medium transition-colors"
                    >
                        <Users className="w-5 h-5" />
                        Members
                    </button>
                    {isGM && (
                        <button
                            onClick={() => {
                                fetchParticipants();
                                setShowManagePlayers(true);
                            }}
                            className="flex items-center gap-2 bg-neutral-800 hover:bg-neutral-700 text-purple-300 border border-purple-500/30 px-4 py-2 rounded-lg font-medium transition-colors"
                        >
                            <Shield className="w-5 h-5" />
                            Manage
                        </button>
                    )}
                    <button
                        onClick={openSettings}
                        className="flex items-center gap-2 bg-neutral-800 hover:bg-neutral-700 text-white px-4 py-2 rounded-lg font-medium transition-colors"
                    >
                        <Settings className="w-5 h-5" />
                    </button>
                    <button
                        onClick={() => navigate('/campaign_start')}
                        className="flex items-center gap-2 bg-purple-600 hover:bg-purple-700 text-white px-4 py-2 rounded-lg font-bold transition-colors shadow-lg shadow-purple-900/20"
                    >
                        <Play className="w-5 h-5" />
                        Switch
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
                                        className={`w-full text-white text-sm py-2 rounded-lg transition-all duration-300 flex items-center justify-center gap-2 ${testStatus === 'error'
                                            ? 'bg-red-500/20 border border-red-500/50 text-red-200'
                                            : 'bg-neutral-800 hover:bg-neutral-700 disabled:opacity-50'
                                            }`}
                                    >
                                        {isTesting ? <Loader2 className="w-4 h-4 animate-spin" /> :
                                            testStatus === 'success' ? <Check className="w-4 h-4 text-green-500" /> :
                                                testStatus === 'error' ? <X className="w-4 h-4 text-red-500" /> : null}
                                        {isTesting ? 'Testing...' :
                                            testStatus === 'success' ? 'Validated & Models Loaded' :
                                                testStatus === 'error' ? `Validation Failed (Reverting in ${errorCountdown}s)` : 'Save & Test Key'}
                                    </button>
                                </div>
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-neutral-400 mb-1">Model</label>
                                <select
                                    value={currentCampaign.model || 'gemini-3-flash-preview'}
                                    onChange={(e) => setCurrentCampaign({ ...currentCampaign, model: e.target.value })}
                                    className="w-full bg-neutral-900 border border-neutral-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-neutral-500"
                                >
                                    {modelList.length > 0 ? (
                                        modelList.map(m => (
                                            <option key={m} value={m}>{m}</option>
                                        ))
                                    ) : (
                                        <>
                                            <optgroup label="Advanced Models">
                                                <option value="gemini-1.5-pro">Gemini 1.5 Pro</option>
                                                <option value="gemini-2.5-pro-preview">Gemini 2.5 Pro</option>
                                                <option value="gemini-3-pro-preview">Gemini 3.0 Pro</option>
                                            </optgroup>
                                            <optgroup label="Fast/Cost-Effective Models">
                                                <option value="gemini-1.5-flash">Gemini 1.5 Flash</option>
                                                <option value="gemini-2.0-flash">Gemini 2.0 Flash</option>
                                                <option value="gemini-2.5-flash">Gemini 2.5 Flash</option>
                                                <option value="gemini-3-flash-preview">Gemini 3.0 Flash</option>
                                            </optgroup>
                                            <option disabled>-- Test API key to fetch more --</option>
                                        </>
                                    )}
                                </select>
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


            {/* Member List Modal */}
            {
                showMemberlist && (
                    <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
                        <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-6 max-w-2xl w-full max-h-[80vh] flex flex-col">
                            <div className="flex justify-between items-center mb-6">
                                <h2 className="text-2xl font-bold flex items-center gap-2">
                                    <Users className="w-6 h-6 text-purple-400" />
                                    Campaign Members
                                </h2>
                                <button onClick={() => setShowMemberlist(false)} className="text-neutral-500 hover:text-white">
                                    <X className="w-6 h-6" />
                                </button>
                            </div>

                            <div className="flex-1 overflow-y-auto custom-scrollbar space-y-4">
                                {isLoadingParticipants ? (
                                    <div className="text-center py-8 text-neutral-500">Loading members...</div>
                                ) : (
                                    participants
                                        .filter(p => p.status === 'active' || p.status === 'interested') // Show interested too? Maybe just active for general list
                                        .map(p => (
                                            <div key={p.id} className="bg-black/40 border border-white/5 rounded-lg p-4">
                                                <div className="flex justify-between items-center mb-2">
                                                    <div className="flex items-center gap-3">
                                                        <span className={`font-bold ${p.role === 'gm' ? 'text-purple-400' : 'text-neutral-200'}`}>
                                                            {p.username}
                                                        </span>
                                                        {p.role === 'gm' && <span className="text-xs bg-purple-900/50 text-purple-300 px-2 py-0.5 rounded border border-purple-500/30">GM</span>}
                                                        {p.status === 'interested' && <span className="text-xs bg-yellow-900/50 text-yellow-300 px-2 py-0.5 rounded border border-yellow-500/30">Pending</span>}
                                                    </div>
                                                </div>

                                                {/* Character List */}
                                                {p.characters && p.characters.length > 0 ? (
                                                    <div className="grid gap-2 mt-2 pl-4 border-l-2 border-white/5">
                                                        {p.characters.map(c => (
                                                            <div key={c.id} className="text-sm flex items-center gap-2 text-neutral-400">
                                                                <span className="text-neutral-300 font-medium">{c.name}</span>
                                                                <span className="w-1 h-1 rounded-full bg-neutral-600" />
                                                                <span>{c.race} {c.class_name}</span>
                                                                <span className="w-1 h-1 rounded-full bg-neutral-600" />
                                                                <span className="text-neutral-500">Lvl {c.level}</span>
                                                            </div>
                                                        ))}
                                                    </div>
                                                ) : (
                                                    <p className="text-xs text-neutral-600 italic pl-4">No characters yet.</p>
                                                )}
                                            </div>
                                        ))
                                )}
                            </div>
                        </div>
                    </div>
                )
            }

            {/* Manage Players Modal (GM Only) */}
            {
                showManagePlayers && isGM && (
                    <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
                        <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-6 max-w-2xl w-full max-h-[80vh] flex flex-col">
                            <div className="flex justify-between items-center mb-6">
                                <h2 className="text-2xl font-bold flex items-center gap-2">
                                    <Shield className="w-6 h-6 text-purple-400" />
                                    Manage Players
                                </h2>
                                <button onClick={() => setShowManagePlayers(false)} className="text-neutral-500 hover:text-white">
                                    <X className="w-6 h-6" />
                                </button>
                            </div>

                            <div className="flex-1 overflow-y-auto custom-scrollbar space-y-4">
                                {isLoadingParticipants ? (
                                    <div className="text-center py-8 text-neutral-500">Loading...</div>
                                ) : (
                                    participants.map(p => (
                                        <div key={p.id} className="bg-black/40 border border-white/5 rounded-lg p-4 flex items-center justify-between">
                                            <div>
                                                <div className="flex items-center gap-2">
                                                    <span className="font-bold text-neutral-200">{p.username}</span>
                                                    {p.role === 'gm' && <span className="text-xs bg-purple-900/50 text-purple-300 px-2 py-0.5 rounded border border-purple-500/30">GM</span>}
                                                </div>
                                                <p className="text-sm text-neutral-500">
                                                    Joined: {new Date(p.joined_at).toLocaleDateString()}
                                                    {p.characters.length > 0 && ` • ${p.characters.length} Character(s)`}
                                                </p>
                                            </div>

                                            <div className="flex items-center gap-2">
                                                {p.role !== 'gm' && (
                                                    <>
                                                        {p.status === 'interested' && (
                                                            <button
                                                                onClick={() => handleUpdateParticipant(p.id, 'active')}
                                                                className="px-3 py-1 bg-green-900/30 hover:bg-green-900/50 text-green-400 border border-green-500/30 rounded text-sm transition-colors"
                                                            >
                                                                Approve
                                                            </button>
                                                        )}
                                                        {p.status === 'active' && (
                                                            <button
                                                                onClick={() => handleUpdateParticipant(p.id, 'banned')}
                                                                className="px-3 py-1 bg-red-900/20 hover:bg-red-900/40 text-red-400 border border-red-500/20 rounded text-sm transition-colors"
                                                            >
                                                                Ban
                                                            </button>
                                                        )}
                                                        {p.status === 'banned' && (
                                                            <button
                                                                onClick={() => handleUpdateParticipant(p.id, 'active')}
                                                                className="px-3 py-1 bg-neutral-800 hover:bg-neutral-700 text-neutral-400 rounded text-sm transition-colors"
                                                            >
                                                                Unban
                                                            </button>
                                                        )}
                                                    </>
                                                )}
                                            </div>
                                        </div>
                                    ))
                                )}
                            </div>
                        </div>
                    </div>
                )
            }
        </div>
    );
}
