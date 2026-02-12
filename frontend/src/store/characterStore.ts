import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { characterApi, Character } from '@/lib/api';

interface CharacterState {
    // Selection State
    activeCharacterId: string | null;
    characters: Character[]; // Cache list?

    // UI State
    isLoading: boolean;
    error: string | null;

    // Actions
    loadCharacters: (campaignId: string) => Promise<void>;
    selectCharacter: (id: string) => void;
    deleteCharacter: (id: string) => Promise<void>;
    updateCharacter: (id: string, updates: Partial<Character>) => Promise<void>;

    // Legacy support for sheet viewer if needed, or we can just fetch on demand
    activeCharacter: Character | null;
}

export const useCharacterStore = create<CharacterState>()(
    persist(
        (set, get) => ({
            activeCharacterId: null,
            characters: [],
            isLoading: false,
            error: null,
            activeCharacter: null,

            loadCharacters: async (campaignId) => {
                set({ isLoading: true, error: null });
                try {
                    const chars = await characterApi.list(campaignId);
                    set({ characters: chars });
                } catch (err: any) {
                    set({ error: err.message });
                } finally {
                    set({ isLoading: false });
                }
            },

            selectCharacter: (id) => {
                const char = get().characters.find(c => c.id === id) || null;
                set({ activeCharacterId: id, activeCharacter: char });
            },

            deleteCharacter: async (id) => {
                set({ isLoading: true, error: null });
                try {
                    await characterApi.delete(id);
                    set(state => ({
                        characters: state.characters.filter(c => c.id !== id),
                        activeCharacterId: state.activeCharacterId === id ? null : state.activeCharacterId,
                        activeCharacter: state.activeCharacterId === id ? null : state.activeCharacter
                    }));
                } catch (err: any) {
                    set({ error: err.message });
                    throw err;
                } finally {
                    set({ isLoading: false });
                }
            },

            updateCharacter: async (id, updates) => {
                // Optimistic update
                set(state => ({
                    characters: state.characters.map(c => c.id === id ? { ...c, ...updates } : c),
                    activeCharacter: state.activeCharacter && state.activeCharacter.id === id ? { ...state.activeCharacter, ...updates } : state.activeCharacter
                }));

                try {
                    await characterApi.update(id, updates);
                } catch (err: any) {
                    set({ error: err.message });
                }
            }
        }),
        {
            name: 'character-storage-v2',
            partialize: (state) => ({
                activeCharacterId: state.activeCharacterId
            })
        }
    )
);
