import React from 'react';
import { useAuthStore } from '@/store/authStore';
import { Navigate, useLocation } from 'react-router-dom';
import { LogOut } from 'lucide-react';

export default function AuthGuard({ children }: { children: React.ReactNode }) {
    const { user, profile, isLoading, signOut } = useAuthStore();
    const location = useLocation();

    if (isLoading) {
        return (
            <div className="min-h-screen bg-black text-white flex items-center justify-center">
                <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-purple-500"></div>
            </div>
        );
    }

    if (!user) {
        // Redirect to login page but preserve the intended destination
        return <Navigate to="/login" state={{ from: location }} replace />;
    }

    // Check for 'interested' status
    if (profile && profile.status === 'interested') {
        return (
            <div className="min-h-screen bg-neutral-950 text-white flex flex-col items-center justify-center p-4">
                <div className="max-w-md text-center space-y-6">
                    <div className="w-16 h-16 bg-yellow-500/10 rounded-full flex items-center justify-center mx-auto">
                        <span className="text-3xl">⏳</span>
                    </div>
                    <h1 className="text-2xl font-bold">Access Under Review</h1>
                    <p className="text-neutral-400">
                        Hello <span className="text-white font-medium">{profile.username}</span>, your account has been created and is currently marked as <span className="text-yellow-400">Interested</span>.
                    </p>
                    <p className="text-neutral-400">
                        An administrator needs to approve your access before you can join the campaign. Please check back later!
                    </p>

                    <button
                        onClick={() => signOut()}
                        className="flex items-center gap-2 mx-auto px-4 py-2 bg-neutral-800 hover:bg-neutral-700 rounded-lg transition-colors text-sm text-neutral-300"
                    >
                        <LogOut className="w-4 h-4" />
                        Sign Out
                    </button>
                </div>
            </div>
        );
    }

    return <>{children}</>;
}
