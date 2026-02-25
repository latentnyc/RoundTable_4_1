import { create } from 'zustand';
import { Stat, Skill, RACES, CLASSES } from '@/lib/srd-data';
import { Item, characterApi, Character, compendiumApi } from '@/lib/api';
import { calculateRemainingPoints, getPointBuyCost, validateStat, getInitialSkillState } from '@/lib/rules/characterRules';
import { CLASS_LOADOUTS } from '@/lib/rules/classLoadouts';
import { useAuthStore } from '@/store/authStore';
import { useCampaignStore } from '@/store/campaignStore';
import { useCharacterStore } from '@/store/characterStore';

interface CreateCharacterState {
    // Wizard State
    step: number;
    isLoading: boolean;
    error: string | null;
    isSaving: boolean;
    isDirty: boolean;
    editingId: string | null;

    // Form Data
    name: string;
    username: string; // Login ID, read-only mostly
    role: string;
    race: string;
    subrace: string | null;
    background: string | null;
    alignment: string;

    // Mechanics
    pointBuyMode: boolean;
    stats: Record<Stat, number>;
    skills: Record<Skill, boolean>;

    // Vitals (Editable)
    hpMax: number;
    hpCurrent: number;
    ac: number;
    initiative: number;
    speed: number;

    // Inventory & extras
    equipment: Item[];
    inventory: (string | Item)[];
    currency: Record<string, number>;
    spells: Item[];
    feats: Item[];
    features: string; // Custom notes
    backstory: string;

    // Derived values helper (not stored state, but calculated)
    // hp, ac, speed etc. are calculated from class/race/stats

    // Actions
    setDirty: (val: boolean) => void;
    setField: (field: keyof CreateCharacterState, value: any) => void;
    setStat: (stat: Stat, value: number) => void;
    toggleSkill: (skill: Skill) => void;
    addEquipment: (item: Item) => void;
    removeEquipment: (itemId: string) => void;
    addSpell: (spell: Item) => void;
    removeSpell: (spellId: string) => void;
    addFeat: (feat: Item) => void;
    removeFeat: (featId: string) => void;

    resetForm: () => void;
    randomize: () => void;
    getPointsRemaining: () => number;

    loadCharacter: (char: Character) => void;
    submitCharacter: () => Promise<void>;
}

// Extracted helper for payload generation
const buildCharacterPayload = (state: CreateCharacterState, currentSheetData: any) => {
    return {
        ...currentSheetData,
        stats: state.stats,
        skills: state.skills,
        savingThrows: {}, // Future implementation: logic for calculating saving throws based on class/stats
        hpMax: state.hpMax,
        hpCurrent: state.hpCurrent,
        ac: state.ac,
        initiative: state.initiative,
        speed: state.speed,
        attacks: currentSheetData.attacks || [],
        equipment: state.equipment,
        inventory: state.inventory,
        currency: state.currency,
        spells: state.spells,
        feats: state.feats,
        features: state.features,
        subrace: state.subrace,
        background: state.background,
        alignment: state.alignment
    };
};

export const useCreateCharacterStore = create<CreateCharacterState>((set, get) => ({
    step: 1,
    isLoading: false,
    error: null,
    isSaving: false,
    isDirty: false,
    editingId: null,

    name: '',
    username: '',
    role: 'Fighter',
    race: 'Human',
    subrace: null,
    background: 'Acolyte',
    alignment: 'True Neutral',

    pointBuyMode: true,
    stats: { Strength: 10, Dexterity: 10, Constitution: 10, Intelligence: 10, Wisdom: 10, Charisma: 10 },
    skills: getInitialSkillState('Acolyte'),

    hpMax: 10,
    hpCurrent: 10,
    ac: 10,
    initiative: 0,
    speed: 30,

    equipment: [],
    inventory: [],
    currency: { pp: 0, gp: 0, sp: 0, cp: 0 },
    spells: [],
    feats: [],
    features: '',
    backstory: '',

    setDirty: (isDirty) => set({ isDirty }),

    setField: (field, value) => set((state) => {
        const updates: any = { [field]: value };

        // Side effects
        if (field === 'background') {
            const newSkills = getInitialSkillState(value as string);
            return { ...state, background: value as string, skills: newSkills };
        }

        if (field === 'role') {
            const loadout = CLASS_LOADOUTS[value as string];
            if (loadout) {
                const spellsPlaceholder = (loadout.spells || []).map(spl => {
                    if (typeof spl === 'string') {
                        return {
                            id: spl,
                            name: spl.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
                            type: 'Spell',
                            data: { desc: 'Details loading...' }
                        } as Item;
                    }
                    return spl;
                });

                // Fetch real spell data asynchronously and update store when done
                if (loadout.spells && loadout.spells.length > 0) {
                    Promise.all(loadout.spells.map(async (spl) => {
                        if (typeof spl === 'string') {
                            try {
                                return await compendiumApi.getSpell(spl);
                            } catch (e) {
                                return {
                                    id: spl,
                                    name: spl.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
                                    type: 'Spell',
                                    data: { desc: 'Details unavailable.' }
                                } as Item;
                            }
                        }
                        return spl;
                    })).then(loadedSpells => {
                        // Ensure the store only updates if the role is still the one we fetched for
                        if (get().role === value) {
                            set({ spells: loadedSpells });
                        }
                    });
                }

                return {
                    ...state,
                    role: value as string,
                    stats: { ...loadout.stats },
                    equipment: [...loadout.equipment],
                    inventory: [...loadout.inventory],
                    spells: spellsPlaceholder,
                    isDirty: true
                };
            }
        }

        if (field === 'race') {
            // Reset subrace when race changes
            const raceData = RACES[value as string];
            return {
                ...state,
                race: value as string,
                subrace: null,
                speed: raceData?.speed || 30,
                isDirty: true
            };
        }

        return { ...state, ...updates, isDirty: true };
    }),

    setStat: (stat, value) => set((state) => {
        if (state.pointBuyMode) {
            if (!validateStat(value)) return state;

            const currentCost = getPointBuyCost(state.stats[stat]);
            const newCost = getPointBuyCost(value);
            const diff = newCost - currentCost;
            const remaining = calculateRemainingPoints(state.stats);

            if (remaining - diff < 0) return state; // Cannot afford
        }
        return {
            ...state,
            stats: { ...state.stats, [stat]: value }
        };
    }),

    toggleSkill: (skill) => set((state) => {
        // Prevent toggling background skills off?
        // Logic handled in UI (disabled checkbox)
        const current = state.skills[skill] || false;
        return {
            ...state,
            skills: { ...state.skills, [skill]: !current },
            isDirty: true
        };
    }),

    addEquipment: (item) => set((state) => ({ equipment: [...state.equipment, item], isDirty: true })),
    removeEquipment: (id) => set((state) => ({ equipment: state.equipment.filter(i => i.id !== id), isDirty: true })),

    addSpell: (spell) => set((state) => ({ spells: [...state.spells, spell], isDirty: true })),
    removeSpell: (id) => set((state) => ({ spells: state.spells.filter(s => s.id !== id), isDirty: true })),

    addFeat: (feat) => set((state) => ({ feats: [...state.feats, feat], isDirty: true })),
    removeFeat: (id) => set((state) => ({ feats: state.feats.filter(f => f.id !== id), isDirty: true })),

    resetForm: () => set({
        step: 1,
        name: '',
        role: 'Fighter',
        race: 'Human',
        subrace: null,
        background: 'Acolyte',
        alignment: 'True Neutral',
        pointBuyMode: true,
        stats: { Strength: 10, Dexterity: 10, Constitution: 10, Intelligence: 10, Wisdom: 10, Charisma: 10 },
        skills: getInitialSkillState('Acolyte'),
        hpMax: 10,
        hpCurrent: 10,
        ac: 10,
        initiative: 0,
        speed: 30,
        equipment: [],
        inventory: [],
        currency: { pp: 0, gp: 0, sp: 0, cp: 0 },
        spells: [],
        feats: [],
        features: '',
        backstory: '',
        error: null,
        isDirty: false,
        editingId: null
    }),

    randomize: () => {
        const raceKeys = Object.keys(RACES);
        const classKeys = Object.keys(CLASSES);
        const randomRace = raceKeys[Math.floor(Math.random() * raceKeys.length)];
        const randomClass = classKeys[Math.floor(Math.random() * classKeys.length)];

        const speed = RACES[randomRace]?.speed || 30;
        const loadout = CLASS_LOADOUTS[randomClass];

        const spellsPlaceholder = loadout ? (loadout.spells || []).map(spl => {
            if (typeof spl === 'string') {
                return {
                    id: spl,
                    name: spl.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
                    type: 'Spell',
                    data: { desc: 'Details loading...' }
                } as Item;
            }
            return spl as Item;
        }) : [];

        if (loadout && loadout.spells && loadout.spells.length > 0) {
            Promise.all(loadout.spells.map(async (spl) => {
                if (typeof spl === 'string') {
                    try {
                        return await compendiumApi.getSpell(spl);
                    } catch (e) {
                        return {
                            id: spl,
                            name: spl.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
                            type: 'Spell',
                            data: { desc: 'Details unavailable.' }
                        } as Item;
                    }
                }
                return spl as Item;
            })).then(loadedSpells => {
                if (get().role === randomClass) {
                    set({ spells: loadedSpells });
                }
            });
        }

        set({
            race: randomRace,
            role: randomClass,
            stats: loadout ? { ...loadout.stats } : { Strength: 10, Dexterity: 10, Constitution: 10, Intelligence: 10, Wisdom: 10, Charisma: 10 },
            equipment: loadout ? [...loadout.equipment] : [],
            inventory: loadout ? [...loadout.inventory] : [],
            spells: spellsPlaceholder,
            pointBuyMode: true,
            speed,
            isDirty: true
        });
    },

    getPointsRemaining: () => {
        return calculateRemainingPoints(get().stats);
    },

    loadCharacter: (char) => {
        const sheet = char.sheet_data || {};
        set({
            editingId: char.id,
            name: char.name,
            role: char.role,
            race: char.race,
            subrace: sheet.subrace || null,
            background: sheet.background || null,
            alignment: sheet.alignment || 'True Neutral',
            stats: sheet.stats || { Strength: 10, Dexterity: 10, Constitution: 10, Intelligence: 10, Wisdom: 10, Charisma: 10 },
            skills: sheet.skills || getInitialSkillState(sheet.background || 'Acolyte'), // Ensure skills are initialized
            hpMax: sheet.hpMax || 10,
            hpCurrent: sheet.hpCurrent || 10,
            ac: sheet.ac || 10,
            initiative: sheet.initiative || 0,
            speed: sheet.speed || 30,
            equipment: sheet.equipment || [],
            inventory: sheet.inventory || [],
            currency: sheet.currency || { pp: 0, gp: 0, sp: 0, cp: 0 },
            spells: sheet.spells || [],
            feats: sheet.feats || [],
            features: sheet.features || '',
            backstory: char.backstory || '',
            isDirty: false
        });
    },

    submitCharacter: async () => {
        const state = get();
        set({ isSaving: true, error: null });

        try {
            const profile = useAuthStore.getState().profile;
            if (!profile) throw new Error("User not authenticated");

            const campaignId = useCampaignStore.getState().selectedCampaignId;
            if (!campaignId) throw new Error("No campaign context");

            const currentSheetData = state.editingId ? (useCharacterStore.getState().characters.find(c => c.id === state.editingId)?.sheet_data || {}) : {};

            // Construct Sheet Data
            const finalSheet = buildCharacterPayload(state, currentSheetData);

            if (state.editingId) {
                await characterApi.update(state.editingId, {
                    name: state.name,
                    role: state.role,
                    race: state.race,
                    sheet_data: finalSheet,
                    backstory: state.backstory
                });
            } else {
                await characterApi.create({
                    user_id: profile.id,
                    campaign_id: campaignId,
                    name: state.name,
                    role: state.role,
                    race: state.race,
                    level: 1,
                    xp: 0,
                    sheet_data: finalSheet,
                    backstory: state.backstory
                });
            }

            set({ isDirty: false });

        } catch (err: any) {
            console.error(err);
            set({ error: err.message || (get().editingId ? "Failed to update character" : "Failed to create character") });
            throw err;
        } finally {
            set({ isSaving: false });
        }
    }
}));
