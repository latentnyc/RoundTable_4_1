import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { characterApi, Profile, Item } from '@/lib/api';
import { useAuthStore } from '@/store/authStore';
import { useCampaignStore } from '@/store/campaignStore';
import { RACES, CLASSES, BACKGROUNDS, Stat, Skill, Alignment } from '@/lib/srd-data';

interface CharacterState {
    step: number;
    // Form Data
    username: string;
    name: string;
    role: string;
    race: string;
    subrace: string | null;
    background: string | null;
    alignment: Alignment | string;
    level: number;
    xp: number;

    // Rules Logic state
    pointBuyMode: boolean;

    // Flexible data for the sheet
    sheetData: {
        stats: Record<Stat, number>;
        skills: Record<Skill, boolean>;
        savingThrows: Record<Stat, boolean>;
        hpMax: number;
        hpCurrent: number;
        ac: number;
        initiative: number;
        speed: number;
        attacks: any[];
        equipment: Item[];
        spells: Item[];
        feats: Item[];
        features: string;
        [key: string]: any;
    };
    backstory: string;

    // App State
    profile: Profile | null;
    activeCharacterId: string | null;
    currentCampaignId: string | null; // Track campaign context
    editingId: string | null;
    isLoading: boolean;
    error: string | null;

    // Actions
    setField: (field: keyof CharacterState | string, value: any) => void;
    setSheetData: (path: string, value: any) => void;
    toggleSkill: (skill: Skill) => void;
    setStat: (stat: Stat, value: number) => void;
    loginAndCreate: () => Promise<void>;
    loadCharacter: (character: any) => void; // New action
    selectCharacter: (id: string) => void;
    getPointsRemaining: () => number;
    deleteCharacter: (id: string) => Promise<void>;
    addEquipment: (item: Item) => void;
    removeEquipment: (itemId: string) => void;
    addSpell: (spell: Item) => void;
    removeSpell: (spellId: string) => void;
    addFeat: (feat: Item) => void;
    removeFeat: (featId: string) => void; // Fixed
    resetForm: () => void;
}

const COST_TABLE: Record<number, number> = {
    8: 0, 9: 1, 10: 2, 11: 3, 12: 4, 13: 5, 14: 7, 15: 9
};

export const useCharacterStore = create<CharacterState>()(
    persist(
        (set, get) => ({
            step: 1,
            username: '',
            name: '',
            role: 'Fighter',
            race: 'Human',
            subrace: null,
            background: null,
            alignment: '',
            level: 1,
            xp: 0,
            pointBuyMode: false,

            sheetData: {
                stats: { Strength: 10, Dexterity: 10, Constitution: 10, Intelligence: 10, Wisdom: 10, Charisma: 10 },
                skills: {} as Record<Skill, boolean>,
                savingThrows: {} as Record<Stat, boolean>,
                hpMax: 10,
                hpCurrent: 10,
                ac: 10,
                initiative: 0,
                speed: 30,
                attacks: [],
                equipment: [],
                spells: [],
                feats: [],
                features: '',
            },
            backstory: '',
            profile: null,
            activeCharacterId: null,
            currentCampaignId: null,
            editingId: null,
            isLoading: false,
            error: null,

            setField: (field, value) => set((state) => {
                const updates: any = { [field]: value };

                // Logic side-effects
                if (field === 'role') {
                    // Update Hit Die/HP base on class
                    const cls = CLASSES[value as string];
                    if (cls) {
                        // Default HP at level 1: Max Hit Die + Con Mod
                    }
                }

                if (field === 'race') {
                    updates.subrace = null; // Reset subrace
                    const r = RACES[value as string];
                    if (r) {
                        // updates.sheetData = { ...state.sheetData, speed: r.speed }; 
                    }
                }

                if (field === 'background') {
                    // Auto-select background skills
                    const bg = BACKGROUNDS[value as string];
                    if (bg) {
                        const newSkills = { ...state.sheetData.skills };
                        bg.skills.forEach(s => newSkills[s] = true);
                        return {
                            ...state,
                            [field]: value,
                            sheetData: { ...state.sheetData, skills: newSkills }
                        };
                    }
                }

                return { ...state, ...updates };
            }),

            setSheetData: (path, value) => set((state) => {
                const parts = path.split('.');
                if (parts.length === 1) {
                    return { sheetData: { ...state.sheetData, [path]: value } };
                }
                if (parts[0] === 'stats') {
                    return {
                        sheetData: {
                            ...state.sheetData,
                            stats: { ...state.sheetData.stats, [parts[1]]: value }
                        }
                    };
                }
                if (parts[0] === 'skills') {
                    return {
                        sheetData: {
                            ...state.sheetData,
                            skills: { ...state.sheetData.skills, [parts[1]]: value }
                        }
                    };
                }
                if (parts[0] === 'savingThrows') {
                    return {
                        sheetData: {
                            ...state.sheetData,
                            savingThrows: { ...state.sheetData.savingThrows, [parts[1]]: value }
                        }
                    };
                }
                return { sheetData: { ...state.sheetData, [path]: value } };
            }),

            setStat: (stat, value) => set((state) => {
                // If in point buy mode, ensure validity
                if (state.pointBuyMode) {
                    if (value < 8 || value > 15) return state; // Hard limits for base score
                    // Check budget
                    const currentCost = COST_TABLE[state.sheetData.stats[stat]] || 0;
                    const newCost = COST_TABLE[value] || 0;
                    const costDiff = newCost - currentCost;
                    const remaining = get().getPointsRemaining();

                    if (remaining - costDiff < 0) return state; // Cannot afford
                }

                return {
                    sheetData: {
                        ...state.sheetData,
                        stats: { ...state.sheetData.stats, [stat]: value }
                    }
                };
            }),

            toggleSkill: (skill) => set((state) => {
                // Logic: Prevent unchecking Background skills?
                // For now, allow freedom but UI will show "locked".
                const current = state.sheetData.skills[skill] || false;
                return {
                    sheetData: {
                        ...state.sheetData,
                        skills: { ...state.sheetData.skills, [skill]: !current }
                    }
                };
            }),

            getPointsRemaining: () => {
                const { sheetData } = get();
                const totalSpent = Object.values(sheetData.stats).reduce((acc, val) => acc + (COST_TABLE[val] || 0), 0);
                return 27 - totalSpent;
            },

            selectCharacter: (id) => set({ activeCharacterId: id }),

            loadCharacter: (char) => {
                const sheet = char.sheet_data || {};
                set({
                    editingId: char.id,
                    name: char.name,
                    role: char.role,
                    race: char.race,
                    level: char.level,
                    xp: char.xp || 0,
                    backstory: char.backstory || '',
                    subrace: sheet.subrace || null,
                    background: sheet.background || null,
                    alignment: sheet.alignment || '',
                    sheetData: {
                        stats: sheet.stats || { Strength: 10, Dexterity: 10, Constitution: 10, Intelligence: 10, Wisdom: 10, Charisma: 10 },
                        skills: sheet.skills || {},
                        savingThrows: sheet.savingThrows || {},
                        hpMax: sheet.hpMax || 10,
                        hpCurrent: sheet.hpCurrent || 10,
                        ac: sheet.ac || 10,
                        initiative: sheet.initiative || 0,
                        speed: sheet.speed || 30,
                        attacks: sheet.attacks || [],
                        equipment: sheet.equipment || [],
                        spells: sheet.spells || [],
                        feats: sheet.feats || [],
                        features: sheet.features || '',
                    },
                    currentCampaignId: char.campaign_id
                });
            },

            loginAndCreate: async () => {
                const { editingId, name, role, race, subrace, background, alignment, level, xp, sheetData, backstory } = get();
                set({ isLoading: true, error: null });

                try {
                    // if (!username) throw new Error("Username is required"); // Removed check as it might persist

                    const profile = useAuthStore.getState().profile;
                    if (!profile) throw new Error("User not authenticated");
                    set({ profile });

                    const campaignId = useCampaignStore.getState().selectedCampaignId || get().currentCampaignId;

                    // Finalize sheet data with derived values like subrace/background if needed
                    const finalSheet = {
                        ...sheetData,
                        subrace,
                        background,
                        alignment
                    };

                    if (!campaignId) {
                        throw new Error("No campaign selected. Please return to the campaign dashboard.");
                    }

                    if (editingId) {
                        await characterApi.update(editingId, {
                            name,
                            role,
                            race,
                            level,
                            xp,
                            sheet_data: finalSheet,
                            backstory,
                            campaign_id: campaignId
                        });
                        // Clear editing state on success? Or maybe keep it until nav?
                        // set({ editingId: null }); 
                    } else {
                        await characterApi.create({
                            user_id: profile.id,
                            campaign_id: campaignId,
                            name,
                            role,
                            race, // Base race string for now
                            level,
                            xp,
                            sheet_data: finalSheet,
                            backstory,
                        });
                    }

                } catch (err: any) {
                    console.error(err);
                    set({ error: err.message || 'Failed to save character' });
                } finally {
                    set({ isLoading: false });
                }
            },

            deleteCharacter: async (id) => {
                set({ isLoading: true, error: null });
                try {
                    await characterApi.delete(id);
                    if (get().activeCharacterId === id) {
                        set({ activeCharacterId: null });
                    }
                } catch (err: any) {
                    console.error(err);
                    set({ error: err.message || 'Failed to delete character' });
                    throw err; // Re-throw so UI can update list
                } finally {
                    set({ isLoading: false });
                }
            },

            addEquipment: (item) => set((state) => ({
                sheetData: {
                    ...state.sheetData,
                    equipment: [...state.sheetData.equipment, item]
                }
            })),

            removeEquipment: (itemId) => set((state) => ({
                sheetData: {
                    ...state.sheetData,
                    equipment: state.sheetData.equipment.filter((i) => i.id !== itemId)
                }
            })),

            addSpell: (spell) => set((state) => ({
                sheetData: {
                    ...state.sheetData,
                    spells: [...(state.sheetData.spells || []), spell]
                }
            })),

            removeSpell: (spellId) => set((state) => ({
                sheetData: {
                    ...state.sheetData,
                    spells: (state.sheetData.spells || []).filter((s: Item) => s.id !== spellId)
                }
            })),

            addFeat: (feat) => set((state) => ({
                sheetData: {
                    ...state.sheetData,
                    feats: [...(state.sheetData.feats || []), feat]
                }
            })),

            removeFeat: (featId) => set((state) => ({
                sheetData: {
                    ...state.sheetData,
                    feats: (state.sheetData.feats || []).filter((f: Item) => f.id !== featId)
                }
            })),

            resetForm: () => {
                const defaultRace = 'Human';
                const defaultClass = 'Barbarian';
                const defaultBackground = 'Acolyte';
                const defaultAlignment = 'Lawful Good';

                // Get background skills
                const bgSkills = BACKGROUNDS[defaultBackground].skills;
                const initialSkills: Record<Skill, boolean> = {} as Record<Skill, boolean>;
                bgSkills.forEach(s => initialSkills[s] = true);

                set({
                    step: 1,
                    name: '',
                    username: get().username || '', // Keep username if logged in? User said "all character info should be blank", usually keeps user session.
                    role: defaultClass,
                    race: defaultRace,
                    subrace: null,
                    background: defaultBackground,
                    alignment: defaultAlignment,
                    level: 1,
                    xp: 0,
                    pointBuyMode: true,
                    sheetData: {
                        stats: { Strength: 10, Dexterity: 10, Constitution: 10, Intelligence: 10, Wisdom: 10, Charisma: 10 },
                        skills: initialSkills,
                        savingThrows: {} as Record<Stat, boolean>,
                        hpMax: 10, // Should technically be calc from class, but simplified reset is fine
                        hpCurrent: 10,
                        ac: 10,
                        initiative: 0,
                        speed: 30, // Human speed
                        attacks: [],
                        equipment: [],
                        spells: [],
                        feats: [],
                        features: '',
                    },
                    backstory: '',
                    error: null,
                    activeCharacterId: null,
                    editingId: null,
                    currentCampaignId: null,
                });
            },
        }),
        {
            name: 'character-storage',
            partialize: (state) => ({
                username: state.username,
                profile: state.profile,
                activeCharacterId: state.activeCharacterId,
                // Persist drafts?
                name: state.name,
                role: state.role,
                race: state.race,
                subrace: state.subrace,
                background: state.background,
                alignment: state.alignment,
                level: state.level,
                sheetData: state.sheetData,
                backstory: state.backstory,
                pointBuyMode: state.pointBuyMode
            }),
            migrate: (persistedState: any, version: number) => {
                if (version === 0) {
                    // Check if equipment is a string
                    if (typeof persistedState.sheetData?.equipment === 'string') {
                        persistedState.sheetData.equipment = [];
                    }
                    if (!persistedState.sheetData?.spells) persistedState.sheetData.spells = [];
                    if (!persistedState.sheetData?.feats) persistedState.sheetData.feats = [];
                }
                return persistedState as CharacterState;
            },
            version: 1,
        }
    )
);
