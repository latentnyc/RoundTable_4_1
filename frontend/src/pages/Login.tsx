import { useState } from 'react';
import { useAuthStore } from '@/store/authStore';
import { Sparkles, Shield } from 'lucide-react';
import { FcGoogle } from 'react-icons/fc';

export default function Login() {
    const { signIn, isLoading, error, profile } = useAuthStore();
    const [isLoginLoading, setIsLoginLoading] = useState(false);

    if (profile) {
        // Only redirect if we have a valid backend profile
        window.location.href = '/campaign_start';
        return null;
    }

    const handleLogin = async () => {
        setIsLoginLoading(true);
        try {
            await signIn();
        } catch (e) {
            console.error("Login failed", e);
        } finally {
            setIsLoginLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-black text-white flex flex-col items-center justify-center p-4 relative overflow-hidden">
            {/* Background Effects */}
            <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-purple-900/40 via-black to-black opacity-50" />

            <div className="max-w-md w-full relative z-10 glass-panel p-8 rounded-2xl border border-white/10 shadow-2xl backdrop-blur-xl">
                <div className="text-center mb-8">
                    <div className="w-16 h-16 bg-purple-600 rounded-2xl mx-auto mb-4 flex items-center justify-center shadow-lg shadow-purple-900/50">
                        <Sparkles className="w-8 h-8 text-white" />
                    </div>
                    <h1 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-purple-400">
                        RoundTable
                    </h1>
                    <p className="text-neutral-400 mt-2">
                        Immersive AI-Powered Tabletops
                    </p>
                </div>

                {error && (
                    <div className="mb-6 p-3 bg-red-900/30 border border-red-800 rounded-lg text-red-200 text-sm flex items-center gap-2">
                        <Shield className="w-4 h-4" />
                        {error}
                    </div>
                )}

                <div className="space-y-4">
                    <button
                        onClick={handleLogin}
                        disabled={isLoading || isLoginLoading}
                        className="w-full py-4 bg-white text-black rounded-xl font-bold hover:bg-neutral-200 transition-all flex items-center justify-center gap-3 disabled:opacity-50 disabled:cursor-not-allowed group shadow-lg hover:shadow-xl hover:scale-[1.02] active:scale-[0.98]"
                    >
                        {isLoading || isLoginLoading ? (
                            <div className="animate-spin rounded-full h-5 w-5 border-t-2 border-b-2 border-black" />
                        ) : (
                            <>
                                <FcGoogle className="w-6 h-6" />
                                <span>Sign in with Google</span>
                            </>
                        )}
                    </button>



                    <p className="text-center text-xs text-neutral-500 flex items-center justify-center gap-1.5">
                        <Shield className="w-3 h-3" />
                        Secure access via Google OAuth
                    </p>
                </div>

                <p className="mt-8 text-center text-xs text-neutral-600">
                    By entering, you agree to face the consequences of your rolls.
                </p>
            </div>
        </div>
    );
}
