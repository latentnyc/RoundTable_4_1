import { create } from 'zustand';
import { User, signInWithPopup, signOut, onAuthStateChanged } from 'firebase/auth';
import { auth, googleProvider } from '@/lib/firebase';

import { Profile, authApi } from '@/lib/api';

interface AuthState {
    user: User | null;
    profile: Profile | null;
    token: string | null;
    isLoading: boolean;
    error: string | null;
    signIn: () => Promise<void>;
    signOut: () => Promise<void>;
    initialize: () => () => void; // Returns unsubscribe function
}

export const useAuthStore = create<AuthState>((set) => ({
    user: null,
    profile: null,
    token: null,
    isLoading: true,
    error: null,

    signIn: async () => {
        set({ isLoading: true, error: null });
        try {
            await signInWithPopup(auth, googleProvider);
            // State update handled by onAuthStateChanged
        } catch (error: any) {
            set({ error: error.message, isLoading: false });
        }
    },

    signOut: async () => {
        set({ isLoading: true });
        try {
            await signOut(auth);
            set({ user: null, profile: null, token: null, isLoading: false });
        } catch (error: any) {
            set({ error: error.message, isLoading: false });
        }
    },

    initialize: () => {
        const unsubscribe = onAuthStateChanged(auth, async (user) => {
            if (user) {
                // Force refresh to ensure we have a valid token for the socket
                const token = await user.getIdToken(true);
                // Set token immediately to allow API calls
                useAuthStore.getState().token = token;

                try {
                    // Update token in store first so interceptor picks it up
                    set({ user, token, isLoading: true });

                    // Fetch Profile from backend
                    const profile = await authApi.login();
                    set({ profile, isLoading: false });
                } catch (e) {
                    console.error("Failed to fetch profile", e);
                    set({ user, token, profile: null, isLoading: false, error: "Failed to login to backend" });
                }
            } else {
                set({ user: null, profile: null, token: null, isLoading: false });
            }
        });
        return unsubscribe;
    }
}));
