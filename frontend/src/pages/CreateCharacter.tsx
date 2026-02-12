import { useCreateCharacterStore } from '@/store/createCharacterStore';
import { useCharacterStore } from '@/store/characterStore';
import { useCampaignStore } from '@/store/campaignStore';
import { useAuthStore } from '@/store/authStore';
import { Save, Shield, Sword, Backpack, Activity, Dice5, AlertCircle, Plus, X, Trash2 } from 'lucide-react';
import { itemsApi, compendiumApi, Item } from '@/lib/api';
import { cn } from '@/lib/utils';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { SKILLS_LIST, Skill, Stat, RaceData, ClassData, BackgroundData } from '@/lib/srd-data';
import { adaptRace, adaptClass, adaptBackground } from '@/lib/api-adapters';

export default function CreateCharacterPage() {
    const store = useCreateCharacterStore();
    const characterStore = useCharacterStore();
    const navigate = useNavigate();
    const [isSaving, setIsSaving] = useState(false);
    const [mounted, setMounted] = useState(false);
    const [racesData, setRacesData] = useState<Record<string, RaceData>>({});
    const [classesData, setClassesData] = useState<Record<string, ClassData>>({});
    const [backgroundsData, setBackgroundsData] = useState<Record<string, BackgroundData>>({});
    const [alignmentsList, setAlignmentsList] = useState<string[]>([]);
    const [loadingData, setLoadingData] = useState(true);

    const [searchParams] = useSearchParams();
    const isEditMode = searchParams.get('edit') === 'true';

    useEffect(() => {
        if (!isEditMode) {
            store.resetForm();
        } else {
            // Load existing character for editing
            if (characterStore.activeCharacter) {
                store.loadCharacter(characterStore.activeCharacter);
            }
        }
        setMounted(true);

        const loadData = async () => {
            try {
                const [races, classes, alignments, backgrounds] = await Promise.all([
                    compendiumApi.getRaces(),
                    compendiumApi.getClasses(),
                    compendiumApi.getAlignments(),
                    compendiumApi.getBackgrounds()
                ]);

                // Map Races
                const rMap: Record<string, RaceData> = {};
                for (const r of races) {
                    rMap[r.name] = adaptRace(r);
                }
                setRacesData(rMap);

                // Map Classes
                const cMap: Record<string, ClassData> = {};
                for (const c of classes) {
                    cMap[c.name] = adaptClass(c);
                }
                setClassesData(cMap);

                // Map Backgrounds
                const bMap: Record<string, BackgroundData> = {};
                for (const b of backgrounds) {
                    bMap[b.name] = adaptBackground(b);
                }
                setBackgroundsData(bMap);

                // Map Alignments
                setAlignmentsList(alignments.map(a => a.name));

                // Randomize for new characters
                if (!isEditMode && races.length > 0 && classes.length > 0) {
                    store.randomize();
                }

                // Randomize Alignment
                if (!isEditMode && alignments.length > 0) {
                    const randomAlignment = alignments[Math.floor(Math.random() * alignments.length)].name;
                    store.setField('alignment', randomAlignment);
                }

                // Pre-populate Equipment and Spells
                if (!isEditMode) {
                    // Generate Random Name
                    const prefixes = ["Aer", "Bar", "Ced", "Dorn", "El", "Fae", "Gor", "Ha", "Ili", "Jen", "Kal", "Lum", "Mor", "Nil", "Oli", "Per", "Quin", "Ror", "Syl", "Tor", "Ulf", "Val", "Wyn", "Xar", "Yor", "Zen"];
                    const suffixes = ["a", "an", "ar", "or", "ius", "ia", "on", "in", "en", "el", "eth", "ath", "ith", "yx", "um", "us"];
                    const randomName = prefixes[Math.floor(Math.random() * prefixes.length)] + suffixes[Math.floor(Math.random() * suffixes.length)];
                    store.setField('name', randomName);

                    try {
                        const [armorResults, weaponResults, spellResults] = await Promise.all([
                            itemsApi.search("Leather Armor"),
                            itemsApi.search("Quarterstaff"),
                            compendiumApi.searchSpells("Light")
                        ]);

                        const armor = armorResults.find(i => i.name === "Leather Armor");
                        const weapon = weaponResults.find(i => i.name === "Quarterstaff");
                        const spell = spellResults.find(i => i.name === "Light");

                        const current = useCreateCharacterStore.getState();

                        if (armor && !current.equipment.some(e => e.name === armor.name)) {
                            store.addEquipment(armor);
                        }
                        if (weapon && !current.equipment.some(e => e.name === weapon.name)) {
                            store.addEquipment(weapon);
                        }
                        if (spell && !current.spells.some(s => s.name === spell.name)) {
                            store.addSpell(spell);
                        }
                    } catch (err) {
                        console.error("Failed to pre-populate items", err);
                    }
                }


            } catch (e) {
                console.error("Failed to load compendium data", e);
            } finally {
                setLoadingData(false);
            }
        };
        loadData();
    }, []);

    // Login ID Logic
    useEffect(() => {
        const user = useAuthStore.getState().user;
        if (user) {
            const loginId = user.email || user.displayName || 'Unknown';
            if (store.username !== loginId) {
                store.setField('username', loginId);
            }
        }
    }, [store]);

    // Item Search Logic
    const [showItemSearch, setShowItemSearch] = useState(false);
    const [itemQuery, setItemQuery] = useState('');
    const [itemResults, setItemResults] = useState<Item[]>([]);

    useEffect(() => {
        if (!showItemSearch) return;
        const timer = setTimeout(async () => {
            try {
                const results = await itemsApi.search(itemQuery);
                setItemResults(results);
            } catch (e) {
                console.error("Failed to search items", e);
            }
        }, 300);
        return () => clearTimeout(timer);
    }, [itemQuery, showItemSearch]);

    // Spells Logic
    const [showSpellSearch, setShowSpellSearch] = useState(false);
    const [spellQuery, setSpellQuery] = useState('');
    const [spellResults, setSpellResults] = useState<Item[]>([]);

    useEffect(() => {
        if (!showSpellSearch) return;
        const timer = setTimeout(async () => {
            try {
                const results = await compendiumApi.searchSpells(spellQuery);
                setSpellResults(results);
            } catch (e) {
                console.error("Failed to search spells", e);
            }
        }, 300);
        return () => clearTimeout(timer);
    }, [spellQuery, showSpellSearch]);

    const handleAddSpell = (spell: Item) => {
        store.addSpell(spell);
        setShowSpellSearch(false);
        setSpellQuery('');
    };

    // Feats Logic
    const [showFeatSearch, setShowFeatSearch] = useState(false);
    const [featQuery, setFeatQuery] = useState('');
    const [featResults, setFeatResults] = useState<Item[]>([]);

    useEffect(() => {
        if (!showFeatSearch) return;
        const timer = setTimeout(async () => {
            try {
                const results = await compendiumApi.searchFeats(featQuery);
                setFeatResults(results);
            } catch (e) {
                console.error("Failed to search feats", e);
            }
        }, 300);
        return () => clearTimeout(timer);
    }, [featQuery, showFeatSearch]);

    const handleAddFeat = (feat: Item) => {
        store.addFeat(feat);
        setShowFeatSearch(false);
        setFeatQuery('');
    };

    const handleAddItem = (item: Item) => {
        store.addEquipment(item);
        setShowItemSearch(false);
        setItemQuery('');
    };

    if (!mounted) return null;

    const handleSave = async () => {
        setIsSaving(true);
        try {
            await store.submitCharacter();
            if (!store.error) {
                const campaignId = useCampaignStore.getState().selectedCampaignId;
                if (campaignId) {
                    navigate(`/campaign_dash/${campaignId}`);
                } else {
                    navigate('/campaign_start');
                }
            }
        } catch (e) {
            // Error handled in store
        } finally {
            setIsSaving(false);
        }
    };

    // --- Derived Data Helpers ---
    const raceData = racesData[store.race];
    const classData = classesData[store.role];
    const bgData = store.background ? backgroundsData[store.background] : null;

    // Calculate Bonuses
    const getRacialBonus = (stat: string): number => {
        const bonus = raceData?.bonuses?.[stat as Stat] || 0;
        return bonus;
    };

    const getScore = (stat: string) => (store.stats[stat as Stat] || 8);
    const getTotalScore = (stat: string) => getScore(stat) + getRacialBonus(stat);
    const getMod = (score: number) => Math.floor((score - 10) / 2);
    const formatMod = (mod: number) => (mod >= 0 ? `+${mod}` : `${mod}`);

    // Skill Logic
    const isSkillFromBg = (skill: Skill) => bgData?.skills?.includes(skill);
    const isSkillAllowed = (skill: Skill) => classData?.skills?.from?.includes(skill) || isSkillFromBg(skill);

    const getClassSkillsCount = () => {
        return Object.entries(store.skills).filter(([s, v]) => v && !isSkillFromBg(s as Skill)).length;
    };
    const maxClassSkills = classData?.skills?.choose || 2;

    return (
        <div className="min-h-screen bg-neutral-950 text-neutral-100 p-4 lg:p-8 font-sans">
            {/* Background Atmosphere */}
            <div className="fixed inset-0 overflow-hidden pointer-events-none z-0">
                <div className="absolute top-[-20%] left-[-10%] w-[60vw] h-[60vw] bg-purple-900/10 blur-[150px] rounded-full" />
                <div className="absolute bottom-[-20%] right-[-10%] w-[60vw] h-[60vw] bg-indigo-900/10 blur-[150px] rounded-full" />
            </div>

            <div className="relative z-10 max-w-7xl mx-auto space-y-6">

                {/* Header / Identity Bar */}
                <header className="bg-neutral-900/60 backdrop-blur border border-neutral-800 rounded-xl p-6 shadow-2xl space-y-4 relative">
                    <div className="absolute top-2 right-2 text-[10px] text-neutral-600 font-mono">v2.1 (Refactored)</div>
                    <div className="flex flex-col md:flex-row gap-6 justify-between">
                        {/* Name & ID */}
                        <div className="flex-1 grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div className="space-y-1">
                                <label className="text-xs font-bold text-neutral-500 uppercase tracking-wider">Character Name</label>
                                <input
                                    type="text"
                                    value={store.name}
                                    onChange={(e) => store.setField('name', e.target.value)}
                                    className="w-full bg-transparent border-b border-neutral-700 focus:border-purple-500 text-2xl font-bold text-white placeholder-neutral-800 focus:outline-none transition-colors"
                                    placeholder="Enter Name..."
                                />
                            </div>
                            <div className="space-y-1">
                                <label className="text-xs font-bold text-neutral-500 uppercase tracking-wider">Login ID</label>
                                <input
                                    type="text"
                                    value={store.username}
                                    readOnly
                                    disabled
                                    className="w-full bg-transparent border-b border-neutral-800 text-lg font-mono text-neutral-500 cursor-not-allowed focus:outline-none"
                                    placeholder="Username..."
                                />
                            </div>
                        </div>

                        <button
                            onClick={handleSave}
                            disabled={isSaving || store.isLoading}
                            className="h-12 px-6 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white rounded-lg font-bold shadow-lg shadow-purple-900/30 transition-all hover:scale-105 disabled:opacity-50 disabled:scale-100 whitespace-nowrap flex items-center gap-2 self-start md:self-center"
                        >
                            {isSaving ? 'Processing...' : (store.editingId ? 'Update Character' : 'Save Character')} <Save className="w-5 h-5" />
                        </button>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-4 gap-4 pt-4 border-t border-neutral-800/50">
                        {/* Race */}
                        <div className="space-y-1">
                            <label className="text-xs font-bold text-neutral-500 uppercase tracking-wider">Race</label>
                            <select
                                value={store.race}
                                onChange={(e) => store.setField('race', e.target.value)}
                                className="w-full bg-neutral-900 border border-neutral-700 rounded px-2 py-2 text-neutral-200 focus:border-purple-500 focus:outline-none text-sm"
                                disabled={loadingData}
                            >
                                {loadingData ? <option>Loading...</option> : Object.keys(racesData).map(r => <option key={r} value={r}>{r}</option>)}
                            </select>
                        </div>

                        {/* Class */}
                        <div className="space-y-1">
                            <label className="text-xs font-bold text-neutral-500 uppercase tracking-wider">Class</label>
                            <select
                                value={store.role}
                                onChange={(e) => store.setField('role', e.target.value)}
                                className="w-full bg-neutral-900 border border-neutral-700 rounded px-2 py-2 text-neutral-200 focus:border-purple-500 focus:outline-none text-sm"
                                disabled={loadingData}
                            >
                                {loadingData ? <option>Loading...</option> : Object.keys(classesData).map(c => <option key={c} value={c}>{c}</option>)}
                            </select>
                        </div>

                        {/* Level */}
                        <div className="space-y-1 w-24">
                            <label className="text-xs font-bold text-neutral-500 uppercase tracking-wider">Level</label>
                            <input
                                type="number"
                                value={1}
                                disabled
                                className="w-full bg-neutral-900 border border-neutral-700 rounded px-2 py-2 text-neutral-500 cursor-not-allowed text-center text-sm"
                            />
                        </div>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {/* Alignment */}
                        <div className="space-y-1">
                            <label className="text-xs font-bold text-neutral-500 uppercase tracking-wider">Alignment</label>
                            <select
                                value={store.alignment}
                                onChange={(e) => store.setField('alignment', e.target.value)}
                                className="w-full bg-neutral-900 border border-neutral-700 rounded px-2 py-2 text-neutral-200 focus:border-purple-500 focus:outline-none text-sm"
                                disabled={loadingData}
                            >
                                <option value="" disabled>Select Alignment...</option>
                                {alignmentsList.map(a => <option key={a} value={a}>{a}</option>)}
                            </select>
                        </div>
                    </div>
                </header>

                {store.error && (
                    <div className="bg-red-900/50 border border-red-500 text-red-200 p-4 rounded-lg flex items-center gap-2">
                        <AlertCircle className="w-5 h-5" /> {store.error}
                    </div>
                )}

                {/* Main Content Grid */}
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">

                    {/* Left Column: Stats & Skills */}
                    <div className="lg:col-span-4 space-y-6">
                        {/* Ability Scores */}
                        <section className="bg-neutral-900/60 backdrop-blur border border-neutral-800 rounded-xl p-4 shadow-xl">
                            <div className="flex justify-between items-center mb-4 border-b border-neutral-800 pb-2">
                                <h3 className="flex items-center gap-2 text-lg font-bold text-indigo-400">
                                    <Activity className="w-5 h-5" /> Ability Scores
                                </h3>
                                <div className="flex items-center gap-2 text-xs">
                                    <label className="text-neutral-500 cursor-pointer flex items-center gap-2 hover:text-neutral-300">
                                        <input
                                            type="checkbox"
                                            checked={store.pointBuyMode}
                                            onChange={(e) => store.setField('pointBuyMode', e.target.checked)}
                                            className="accent-purple-500"
                                        /> Point Buy
                                    </label>
                                    {store.pointBuyMode && (
                                        <span className={cn("font-mono font-bold px-2 py-1 rounded bg-neutral-800", store.getPointsRemaining() < 0 ? "text-red-400" : "text-green-400")}>
                                            {store.getPointsRemaining()} pts
                                        </span>
                                    )}
                                </div>
                            </div>

                            <div className="space-y-2">
                                <div className="grid grid-cols-6 text-xs text-neutral-500 uppercase font-bold text-center mb-1">
                                    <span className="col-span-1 text-left">Stat</span>
                                    <span className="col-span-2">Base</span>
                                    <span className="col-span-1">Race</span>
                                    <span className="col-span-1">Total</span>
                                    <span className="col-span-1">Mod</span>
                                </div>
                                {["Strength", "Dexterity", "Constitution", "Intelligence", "Wisdom", "Charisma"].map((stat) => {
                                    const val = store.stats[stat as Stat] || 10;

                                    const racial = getRacialBonus(stat);
                                    const total = getTotalScore(stat);
                                    const mod = getMod(total);
                                    return (
                                        <div key={stat} className="bg-neutral-950/50 rounded-lg p-2 grid grid-cols-6 items-center border border-neutral-800 hover:border-neutral-700 transition-colors">
                                            <div className="col-span-1 font-bold text-neutral-400 text-sm">{stat.slice(0, 3)}</div>

                                            <div className="col-span-2 flex items-center justify-center gap-1">
                                                <button
                                                    onClick={() => store.setStat(stat as Stat, (val as number) - 1)}
                                                    className="w-5 h-5 rounded bg-neutral-800 hover:bg-neutral-700 flex items-center justify-center text-neutral-400 text-xs"
                                                >-</button>
                                                <span className="font-bold w-5 text-center text-sm">{val as number}</span>
                                                <button
                                                    onClick={() => store.setStat(stat as Stat, (val as number) + 1)}
                                                    className="w-5 h-5 rounded bg-neutral-800 hover:bg-neutral-700 flex items-center justify-center text-neutral-400 text-xs"
                                                >+</button>
                                            </div>

                                            <div className="col-span-1 text-center text-indigo-400 text-xs font-medium">
                                                {racial > 0 ? `+${racial}` : '-'}
                                            </div>
                                            <div className="col-span-1 text-center font-bold text-white text-sm">
                                                {total}
                                            </div>
                                            <div className="col-span-1 text-center font-mono font-bold text-sm">
                                                <span className={mod > 0 ? "text-green-400" : mod < 0 ? "text-red-400" : "text-neutral-500"}>
                                                    {formatMod(mod)}
                                                </span>
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        </section>

                        {/* Skills */}
                        <section className="bg-neutral-900/60 backdrop-blur border border-neutral-800 rounded-xl p-4 shadow-xl flex-1">
                            <div className="flex justify-between items-center mb-4 border-b border-neutral-800 pb-2">
                                <h3 className="flex items-center gap-2 text-lg font-bold text-indigo-400">
                                    <Dice5 className="w-5 h-5" /> Skills
                                </h3>
                                <span className={cn("text-xs font-bold px-2 py-1 rounded bg-neutral-800", getClassSkillsCount() > maxClassSkills ? "text-red-400" : "text-neutral-400")}>
                                    {getClassSkillsCount()} / {maxClassSkills} Class Skills
                                </span>
                            </div>

                            <div className="grid grid-cols-2 gap-x-4 gap-y-1 max-h-[400px] overflow-y-auto pr-2 custom-scrollbar">
                                {SKILLS_LIST.map(skill => {
                                    const isProficient = store.skills[skill] || false;
                                    const fromBg = isSkillFromBg(skill);
                                    const allowed = isSkillAllowed(skill);

                                    return (
                                        <div key={skill} className={cn("flex items-center gap-2 p-1.5 rounded text-sm transition-colors", allowed ? "hover:bg-neutral-800/50" : "opacity-50 grayscale")}>
                                            <input
                                                type="checkbox"
                                                checked={isProficient}
                                                onChange={() => fromBg ? null : store.toggleSkill(skill)}
                                                disabled={fromBg || (!isProficient && !allowed)} // Can't uncheck bg, can't check restricted
                                                className={cn("w-4 h-4 rounded border-neutral-600 bg-neutral-900 accent-purple-600", fromBg ? "cursor-not-allowed opacity-70" : "cursor-pointer")}
                                            />
                                            <span className="truncate flex-1">
                                                <span className={cn(isProficient ? "text-white font-medium" : "text-neutral-500")}>{skill}</span>
                                            </span>
                                            {fromBg && <span className="text-[10px] text-indigo-400 bg-indigo-900/30 px-1 rounded">BG</span>}
                                        </div>
                                    );
                                })}
                            </div>
                        </section>
                    </div>

                    {/* Middle Column: Combat (4 spans) */}
                    <div className="lg:col-span-4 space-y-6">
                        {/* Vitals */}
                        <section className="bg-neutral-900/60 backdrop-blur border border-neutral-800 rounded-xl p-4 shadow-xl">
                            <div className="grid grid-cols-3 gap-3 mb-4">
                                <div className="bg-neutral-950/50 border border-neutral-800 rounded-lg p-3 text-center">
                                    <label className="text-xs font-bold text-neutral-500 uppercase block mb-1">AC</label>
                                    <input
                                        type="number"
                                        value={store.ac}
                                        onChange={(e) => store.setField('ac', parseInt(e.target.value) || 10)}
                                        className="w-full bg-transparent text-center text-2xl font-bold text-white focus:outline-none"
                                    />
                                </div>
                                <div className="bg-neutral-950/50 border border-neutral-800 rounded-lg p-3 text-center">
                                    <label className="text-xs font-bold text-neutral-500 uppercase block mb-1">Init</label>
                                    <input
                                        type="number"
                                        value={store.initiative}
                                        onChange={(e) => store.setField('initiative', parseInt(e.target.value) || 0)}
                                        className="w-full bg-transparent text-center text-2xl font-bold text-white focus:outline-none"
                                    />
                                </div>
                                <div className="bg-neutral-950/50 border border-neutral-800 rounded-lg p-3 text-center">
                                    <label className="text-xs font-bold text-neutral-500 uppercase block mb-1">Speed</label>
                                    <div className="text-2xl font-bold text-white">{store.speed}</div>
                                </div>
                            </div>
                            <div className="bg-neutral-950/50 border border-neutral-800 rounded-lg p-4 flex items-center justify-between">
                                <div className="flex-1">
                                    <label className="text-xs font-bold text-neutral-500 uppercase block mb-1">Hit Points</label>
                                    <div className="flex items-center gap-2">
                                        <input
                                            type="number"
                                            value={store.hpCurrent}
                                            onChange={(e) => store.setField('hpCurrent', parseInt(e.target.value) || 0)}
                                            className="w-20 bg-transparent text-right text-3xl font-bold text-white focus:outline-none"
                                        />
                                        <span className="text-2xl text-neutral-600">/</span>
                                        <input
                                            type="number"
                                            value={store.hpMax}
                                            onChange={(e) => store.setField('hpMax', parseInt(e.target.value) || 10)}
                                            className="w-20 bg-transparent text-left text-3xl font-bold text-neutral-400 focus:outline-none"
                                        />
                                    </div>
                                    <p className="text-xs text-neutral-600 mt-1">Hit Die: d{classData?.hitDie}</p>
                                </div>
                                <Shield className="w-10 h-10 text-red-900/50" />
                            </div>
                        </section >

                        <section className="bg-neutral-900/60 backdrop-blur border border-neutral-800 rounded-xl p-4 shadow-xl min-h-[300px]">
                            <h3 className="flex items-center gap-2 text-lg font-bold text-indigo-400 mb-4 border-b border-neutral-800 pb-2 justify-between">
                                <div className="flex items-center gap-2">
                                    <Sword className="w-5 h-5" /> Features & Traits
                                </div>
                                <button
                                    onClick={() => setShowFeatSearch(!showFeatSearch)}
                                    className="p-1 hover:bg-neutral-800 rounded text-neutral-400 hover:text-white transition-colors"
                                    title="Add Feat"
                                >
                                    {showFeatSearch ? <X className="w-4 h-4" /> : <Plus className="w-4 h-4" />}
                                </button>
                            </h3>

                            {showFeatSearch && (
                                <div className="mb-4 bg-neutral-950 border border-neutral-800 rounded-lg p-3 animate-in fade-in slide-in-from-top-2">
                                    <input
                                        type="text"
                                        autoFocus
                                        placeholder="Search feats..."
                                        className="w-full bg-neutral-900 border border-neutral-700 rounded px-3 py-2 text-sm text-white focus:border-purple-500 focus:outline-none mb-2"
                                        value={featQuery}
                                        onChange={(e) => setFeatQuery(e.target.value)}
                                    />
                                    <div className="max-h-40 overflow-y-auto space-y-1 custom-scrollbar">
                                        {featResults.map(feat => (
                                            <button
                                                key={feat.id}
                                                onClick={() => handleAddFeat(feat)}
                                                className="w-full text-left px-2 py-1.5 hover:bg-neutral-800 rounded text-xs text-neutral-300 flex justify-between items-center group"
                                            >
                                                <span className="font-bold group-hover:text-white">{feat.name}</span>
                                            </button>
                                        ))}
                                    </div>
                                </div>
                            )}

                            <div className="space-y-2 h-[400px] overflow-y-auto custom-scrollbar p-1">
                                {/* Auto-derived Features */}
                                {classData?.features.map(f => (
                                    <div key={`class-${f}`} className="bg-neutral-900/50 border border-neutral-800 rounded p-2">
                                        <div className="flex justify-between items-center">
                                            <span className="font-bold text-sm text-white">{f}</span>
                                            <span className="text-[10px] uppercase font-bold text-indigo-400 bg-indigo-950/30 px-1.5 py-0.5 rounded">Class Choice</span>
                                        </div>
                                    </div>
                                ))}
                                {raceData?.traits.map(t => (
                                    <div key={`race-${t}`} className="bg-neutral-900/50 border border-neutral-800 rounded p-2">
                                        <div className="flex justify-between items-center">
                                            <span className="font-bold text-sm text-white">{t}</span>
                                            <span className="text-[10px] uppercase font-bold text-emerald-400 bg-emerald-950/30 px-1.5 py-0.5 rounded">Race Trait</span>
                                        </div>
                                    </div>
                                ))}
                                {bgData?.feature && (
                                    <div className="bg-neutral-900/50 border border-neutral-800 rounded p-2">
                                        <div className="flex justify-between items-center">
                                            <span className="font-bold text-sm text-white">{bgData.feature}</span>
                                            <span className="text-[10px] uppercase font-bold text-amber-400 bg-amber-950/30 px-1.5 py-0.5 rounded">Background</span>
                                        </div>
                                    </div>
                                )}

                                {/* Added Feats */}
                                {(Array.isArray(store.feats) ? store.feats : []).map((feat, idx) => (
                                    <div key={feat.id + idx} className="bg-neutral-900 border border-neutral-800 rounded p-2 flex flex-col gap-1 group relative">
                                        <div className="flex justify-between items-start">
                                            <span className="font-bold text-sm text-neutral-200">{feat.name}</span>
                                            <span className="text-[10px] uppercase font-bold text-purple-400 bg-purple-950/30 px-1.5 py-0.5 rounded">Feat</span>
                                            <button
                                                onClick={() => store.removeFeat(feat.id)}
                                                className="text-neutral-600 hover:text-red-400 p-0.5 rounded opacity-0 group-hover:opacity-100 transition-opacity absolute top-2 right-2"
                                            >
                                                <Trash2 className="w-3.5 h-3.5" />
                                            </button>
                                        </div>
                                        {feat.data.desc && (
                                            <div className="text-[10px] text-neutral-400 line-clamp-3 hover:line-clamp-none cursor-help">
                                                {Array.isArray(feat.data.desc) ? feat.data.desc.join(' ') : feat.data.desc}
                                            </div>
                                        )}
                                        {feat.data.description && (
                                            <div className="text-[10px] text-neutral-400 line-clamp-3 hover:line-clamp-none cursor-help whitespace-pre-line">
                                                {feat.data.description}
                                            </div>
                                        )}
                                    </div>
                                ))}
                            </div>

                            <div className="mt-4 pt-4 border-t border-neutral-800">
                                <label className="text-xs font-bold text-neutral-500 uppercase tracking-wider block mb-2">Additional Notes / Custom Features</label>
                                <textarea
                                    className="w-full h-24 bg-neutral-950/50 border border-neutral-800 rounded-lg p-3 text-neutral-300 resize-none focus:border-purple-500 focus:outline-none text-sm font-mono leading-relaxed"
                                    placeholder="Add custom features, attacks, or notes here..."
                                    value={store.features}
                                    onChange={(e) => store.setField('features', e.target.value)}
                                />
                            </div>
                        </section>


                    </div>

                    {/* Right Column: Inventory & Lorentz */}
                    < div className="lg:col-span-4 space-y-6" >
                        {/* Equipment */}
                        < section className="bg-neutral-900/60 backdrop-blur border border-neutral-800 rounded-xl p-4 shadow-xl" >
                            <h3 className="flex items-center gap-2 text-lg font-bold text-indigo-400 mb-4 border-b border-neutral-800 pb-2 justify-between">
                                <div className="flex items-center gap-2">
                                    <Backpack className="w-5 h-5" /> Equipment
                                </div>
                                <button
                                    onClick={() => setShowItemSearch(!showItemSearch)}
                                    className="p-1 hover:bg-neutral-800 rounded text-neutral-400 hover:text-white transition-colors"
                                    title="Add Equipment from Database"
                                >
                                    {showItemSearch ? <X className="w-4 h-4" /> : <Plus className="w-4 h-4" />}
                                </button>
                            </h3>

                            {
                                showItemSearch && (
                                    <div className="mb-4 bg-neutral-950 border border-neutral-800 rounded-lg p-3 animate-in fade-in slide-in-from-top-2">
                                        <input
                                            type="text"
                                            autoFocus
                                            placeholder="Search 5e items..."
                                            className="w-full bg-neutral-900 border border-neutral-700 rounded px-3 py-2 text-sm text-white focus:border-purple-500 focus:outline-none mb-2"
                                            value={itemQuery}
                                            onChange={(e) => setItemQuery(e.target.value)}
                                        />
                                        <div className="max-h-40 overflow-y-auto space-y-1 custom-scrollbar">
                                            {itemResults.map(item => (
                                                <button
                                                    key={item.id}
                                                    onClick={() => handleAddItem(item)}
                                                    className="w-full text-left px-2 py-1.5 hover:bg-neutral-800 rounded text-xs text-neutral-300 flex justify-between items-center group"
                                                >
                                                    <span className="font-bold group-hover:text-white">{item.name}</span>
                                                    <span className="text-neutral-600 italic">{item.type}</span>
                                                </button>
                                            ))}
                                            {itemResults.length === 0 && (
                                                <div className="text-center text-xs text-neutral-600 py-2">No items found</div>
                                            )}
                                        </div>
                                    </div>
                                )
                            }

                            {/* Equipment List */}
                            <div className="bg-neutral-950/50 border border-neutral-800 rounded-lg p-2 h-64 overflow-y-auto custom-scrollbar space-y-2">
                                {(Array.isArray(store.equipment) ? store.equipment : []).length === 0 && (
                                    <div className="text-neutral-600 text-center py-8 text-sm italic">
                                        No equipment added. Click + to add items.
                                    </div>
                                )}
                                {(Array.isArray(store.equipment) ? store.equipment : []).map((item, idx) => {
                                    // Parse details
                                    const cost = item.data.cost ? `${item.data.cost.quantity} ${item.data.cost.unit}` : null;
                                    const weight = item.data.weight ? `${item.data.weight} lb` : null;
                                    const damage = item.data.damage ? `${item.data.damage.damage_dice} ${item.data.damage.damage_type?.name}` : null;
                                    const ac = item.data.armor_class ? `AC ${item.data.armor_class.base}` : null;
                                    const props = item.data.properties ? item.data.properties.map((p: any) => p.name).join(', ') : null;

                                    return (
                                        <div key={item.id + idx} className="bg-neutral-900 border border-neutral-800 rounded p-2 flex flex-col gap-1 group relative">
                                            <div className="flex justify-between items-start">
                                                <span className="font-bold text-sm text-neutral-200">{item.name}</span>
                                                <button
                                                    onClick={() => store.removeEquipment(item.id)}
                                                    className="text-neutral-600 hover:text-red-400 p-0.5 rounded opacity-0 group-hover:opacity-100 transition-opacity absolute top-2 right-2"
                                                >
                                                    <Trash2 className="w-3.5 h-3.5" />
                                                </button>
                                            </div>

                                            <div className="flex flex-wrap gap-2 text-[10px] text-neutral-500 uppercase font-mono">
                                                {item.type && <span className="bg-neutral-800 px-1 rounded">{item.type}</span>}
                                                {cost && <span>{cost}</span>}
                                                {weight && <span>{weight}</span>}
                                            </div>

                                            {(damage || ac) && (
                                                <div className="text-xs text-indigo-300 font-medium flex gap-2">
                                                    {damage && <span>{damage}</span>}
                                                    {ac && <span>{ac}</span>}
                                                </div>
                                            )}

                                            {props && (
                                                <div className="text-[10px] text-neutral-400 italic">
                                                    {props}
                                                </div>
                                            )}

                                            {item.data.desc && Array.isArray(item.data.desc) && (
                                                <div className="text-[10px] text-neutral-500 line-clamp-2 hover:line-clamp-none cursor-help">
                                                    {item.data.desc.join(' ')}
                                                </div>
                                            )}
                                        </div>
                                    );
                                })}
                            </div>
                        </section >

                        {/* Spells */}
                        <section className="bg-neutral-900/60 backdrop-blur border border-neutral-800 rounded-xl p-4 shadow-xl">
                            <h3 className="flex items-center gap-2 text-lg font-bold text-indigo-400 mb-4 border-b border-neutral-800 pb-2 justify-between">
                                <div className="flex items-center gap-2">
                                    <Activity className="w-5 h-5" /> Spells
                                </div>
                                <button
                                    onClick={() => setShowSpellSearch(!showSpellSearch)}
                                    className="p-1 hover:bg-neutral-800 rounded text-neutral-400 hover:text-white transition-colors"
                                >
                                    {showSpellSearch ? <X className="w-4 h-4" /> : <Plus className="w-4 h-4" />}
                                </button>
                            </h3>

                            {showSpellSearch && (
                                <div className="mb-4 bg-neutral-950 border border-neutral-800 rounded-lg p-3 animate-in fade-in slide-in-from-top-2">
                                    <input
                                        type="text"
                                        autoFocus
                                        placeholder="Search spells..."
                                        className="w-full bg-neutral-900 border border-neutral-700 rounded px-3 py-2 text-sm text-white focus:border-purple-500 focus:outline-none mb-2"
                                        value={spellQuery}
                                        onChange={(e) => setSpellQuery(e.target.value)}
                                    />
                                    <div className="max-h-40 overflow-y-auto space-y-1 custom-scrollbar">
                                        {spellResults.map(spell => (
                                            <button
                                                key={spell.id}
                                                onClick={() => handleAddSpell(spell)}
                                                className="w-full text-left px-2 py-1.5 hover:bg-neutral-800 rounded text-xs text-neutral-300 flex justify-between items-center group"
                                            >
                                                <span className="font-bold group-hover:text-white">{spell.name}</span>
                                                <span className="text-neutral-500 italic ml-2">{spell.data?.level > 0 ? `Lvl ${spell.data.level}` : 'Cantrip'}</span>
                                            </button>
                                        ))}
                                    </div>
                                </div>
                            )}

                            <div className="space-y-2 h-64 overflow-y-auto custom-scrollbar p-1">
                                {(Array.isArray(store.spells) ? store.spells : []).length === 0 && (
                                    <div className="text-neutral-600 text-center py-8 text-sm italic">
                                        No spells added.
                                    </div>
                                )}
                                {(Array.isArray(store.spells) ? store.spells : []).map((spell, idx) => (
                                    <div key={spell.id + idx} className="bg-neutral-900 border border-neutral-800 rounded p-2 flex flex-col gap-1 group relative">
                                        <div className="flex justify-between items-start">
                                            <span className="font-bold text-sm text-indigo-300">{spell.name}</span>
                                            <button
                                                onClick={() => store.removeSpell(spell.id)}
                                                className="text-neutral-600 hover:text-red-400 p-0.5 rounded opacity-0 group-hover:opacity-100 transition-opacity absolute top-2 right-2"
                                            >
                                                <Trash2 className="w-3.5 h-3.5" />
                                            </button>
                                        </div>
                                        <div className="text-[10px] text-neutral-500 flex gap-2">
                                            <span className="bg-neutral-800 px-1 rounded">{spell.data?.level > 0 ? `Level ${spell.data.level}` : 'Cantrip'}</span>
                                            <span>{spell.data?.school?.name || spell.data?.school}</span>
                                        </div>
                                        {spell.data.desc && (
                                            <div className="text-[10px] text-neutral-400 line-clamp-2 hover:line-clamp-none cursor-help">
                                                {Array.isArray(spell.data.desc) ? spell.data.desc.join(' ') : spell.data.desc}
                                            </div>
                                        )}
                                    </div>
                                ))}
                            </div>
                        </section>

                        {/* Backstory */}
                        <section className="bg-neutral-900/60 backdrop-blur border border-neutral-800 rounded-xl p-4 shadow-xl">
                            <h3 className="flex items-center gap-2 text-lg font-bold text-indigo-400 mb-2">
                                <Activity className="w-5 h-5" /> Backstory
                            </h3>
                            <textarea
                                className="w-full h-32 bg-neutral-950/50 border border-neutral-800 rounded-lg p-3 text-neutral-300 resize-none focus:border-purple-500 focus:outline-none text-sm font-sans leading-relaxed"
                                placeholder="Write a short backstory..."
                                value={store.backstory}
                                onChange={(e) => store.setField('backstory', e.target.value)}
                            />
                        </section>

                    </div>
                </div>
            </div>
        </div>
    );
}
