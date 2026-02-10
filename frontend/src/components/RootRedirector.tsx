import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/store/authStore';

export default function RootRedirector() {
    const { user, isLoading } = useAuthStore();
    const navigate = useNavigate();

    useEffect(() => {
        if (isLoading) return;

        if (user) {
            navigate('/campaign_start', { replace: true });
        } else {
            navigate('/login', { replace: true });
        }
    }, [user, isLoading, navigate]);

    return (
        <div className="min-h-screen bg-black text-white flex items-center justify-center">
            <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-purple-500"></div>
        </div>
    );
}
