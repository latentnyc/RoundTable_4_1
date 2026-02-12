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
        } catch (error: unknown) {
            set({ error: (error as Error).message, isLoading: false });
        }
    },

    signOut: async () => {
        set({ isLoading: true });
        try {
            await signOut(auth);
            set({ user: null, profile: null, token: null, isLoading: false });
        } catch (error: unknown) {
            set({ error: (error as Error).message, isLoading: false });
        }
    },

    initialize: () => {


        // Safety timeout to prevent infinite loading if Firebase/Emulator is unreachable
        const timeoutId = setTimeout(() => {
            console.warn("⏰ Auth timeout trigger!");
            const state = useAuthStore.getState();
            if (state.isLoading) {
                set({
                    isLoading: false,
                    error: "Authentication service connection timed out. If running locally, please ensure Firebase Emulators are running."
                });
            }
        }, 5000);

        const unsubscribe = onAuthStateChanged(auth, async (user) => {
            // State update handled by onAuthStateChanged
            clearTimeout(timeoutId);
            if (user) {
                try {

                    // Force refresh to ensure we have a valid token for the socket
                    const token = await user.getIdToken(true);


                    // Set token immediately to allow API calls
                    useAuthStore.getState().token = token;
                    set({ token });

                    // Update token in store first so interceptor picks it up
                    set({ user, isLoading: true });

                    // Fetch Profile from backend

                    const profile = await authApi.login();

                    set({ profile, isLoading: false });
                } catch (e: any) {
                    console.error("❌ Failed to fetch profile/token", e);
                    set({ user: null, token: null, profile: null, isLoading: false, error: e.message || "Failed to finalize login" });
                }
            } else {

                set({ user: null, profile: null, token: null, isLoading: false });
            }
        });

        return () => {
            clearTimeout(timeoutId);
            unsubscribe();
        };
    }
}));
