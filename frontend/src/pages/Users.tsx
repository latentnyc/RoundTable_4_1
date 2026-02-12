import { useEffect, useState } from 'react';
import { usersApi, Profile } from '@/lib/api';
import { useAuthStore } from '@/store/authStore';
import { useNavigate } from 'react-router-dom';
import { Shield, ShieldOff, User, Trash2 } from 'lucide-react';

export default function UsersPage() {
    const { profile } = useAuthStore();
    const navigate = useNavigate();
    const [users, setUsers] = useState<Profile[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [userToDelete, setUserToDelete] = useState<Profile | null>(null);

    useEffect(() => {
        if (!profile?.is_admin) {
            navigate('/');
            return;
        }
        loadUsers();
    }, [profile, navigate]);

    const loadUsers = async () => {
        try {
            setLoading(true);
            const list = await usersApi.list();
            setUsers(list);
        } catch (e: unknown) {
            console.error("Failed to load users", e);
            setError("Failed to load users");
        } finally {
            setLoading(false);
        }
    };

    const toggleAdmin = async (user: Profile) => {
        const newStatus = !user.is_admin;
        if (user.id === profile?.id && !newStatus) {
            if (!confirm("You are about to remove your own admin privileges. Continue?")) return;
        }

        try {
            // Optimistic update
            setUsers(curr => curr.map(u => u.id === user.id ? { ...u, is_admin: newStatus } : u));

            await usersApi.update(user.id, { is_admin: newStatus });
        } catch (e: unknown) {
            console.error("Failed to update user", e);
            // Revert
            setUsers(curr => curr.map(u => u.id === user.id ? { ...u, is_admin: !newStatus } : u));
            alert("Failed to update user role");
        }
    };

    const toggleStatus = async (user: Profile, newStatus: string) => {
        const oldStatus = user.status || 'interested';

        try {
            // Optimistic update
            setUsers(curr => curr.map(u => u.id === user.id ? { ...u, status: newStatus } : u));

            await usersApi.update(user.id, { status: newStatus });
        } catch (e: unknown) {
            console.error("Failed to update user status", e);
            // Revert
            setUsers(curr => curr.map(u => u.id === user.id ? { ...u, status: oldStatus } : u));
            alert("Failed to update status");
        }
    };



    const confirmDelete = async () => {
        if (!userToDelete) return;

        try {
            await usersApi.delete(userToDelete.id);
            setUsers(curr => curr.filter(u => u.id !== userToDelete.id));

            if (userToDelete.id === profile?.id) {
                navigate('/');
                window.location.reload();
            }
            setUserToDelete(null);
        } catch (e: unknown) {
            console.error("Failed to delete user", e);
            alert("Failed to delete user");
        }
    };

    if (!profile?.is_admin) return null;

    return (
        <div className="min-h-screen bg-neutral-950 text-white p-8">
            <div className="max-w-4xl mx-auto">
                <div className="flex justify-between items-center mb-8">
                    <h1 className="text-3xl font-bold">User Management</h1>
                    <button
                        onClick={() => navigate('/')}
                        className="text-neutral-400 hover:text-white"
                    >
                        Back to Home
                    </button>
                </div>

                {error && (
                    <div className="bg-red-500/10 border border-red-500/50 text-red-400 p-4 rounded-xl mb-6">
                        {error}
                    </div>
                )}

                <div className="bg-neutral-900 border border-neutral-800 rounded-xl overflow-hidden">
                    <table className="w-full text-left">
                        <thead className="bg-neutral-800 text-neutral-400">
                            <tr>
                                <th className="p-4 font-medium">Username</th>
                                <th className="p-4 font-medium">ID</th>
                                <th className="p-4 font-medium">Role</th>
                                <th className="p-4 font-medium text-right">Actions</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-neutral-800">
                            {users.map(user => (
                                <tr key={user.id} className="hover:bg-neutral-800/50">
                                    <td className="p-4 flex items-center gap-3">
                                        <div className="w-8 h-8 rounded-full bg-neutral-700 flex items-center justify-center">
                                            <User className="w-4 h-4 text-neutral-400" />
                                        </div>
                                        {user.username}
                                        {user.id === profile?.id && <span className="text-xs bg-purple-500/20 text-purple-400 px-2 py-0.5 rounded-full">You</span>}
                                    </td>
                                    <td className="p-4 font-mono text-sm text-neutral-500">{user.id}</td>
                                    <td className="p-4">
                                        <div className="flex flex-col gap-1">
                                            {user.is_admin ? (
                                                <span className="flex items-center gap-1 text-purple-400 text-sm font-medium">
                                                    <Shield className="w-4 h-4" /> Admin
                                                </span>
                                            ) : (
                                                <span className="text-neutral-500 text-sm">User</span>
                                            )}
                                            <span className={`text-xs px-2 py-0.5 rounded-full w-fit ${user.status === 'active'
                                                ? "bg-green-500/20 text-green-400"
                                                : "bg-yellow-500/20 text-yellow-400"
                                                }`}>
                                                {user.status || 'interested'}
                                            </span>
                                        </div>
                                    </td>
                                    <td className="p-4 text-right flex items-center justify-end gap-2">
                                        {/* Status Toggle */}
                                        {user.status !== 'active' ? (
                                            // Interested -> Active (Needs confirmation)
                                            <div className="flex items-center gap-2">
                                                <span className="text-xs text-neutral-500 hidden sm:inline">Approve access?</span>
                                                <button
                                                    onClick={() => {
                                                        if (confirm(`Promote ${user.username} to active User?`)) {
                                                            toggleStatus(user, 'active');
                                                        }
                                                    }}
                                                    className="p-2 rounded-lg bg-green-500/10 text-green-400 hover:bg-green-500/20 transition-colors"
                                                    title="Approve User"
                                                >
                                                    <User className="w-4 h-4" />
                                                </button>
                                            </div>
                                        ) : (
                                            // Active -> Interested (Demote)
                                            <button
                                                onClick={() => toggleStatus(user, 'interested')}
                                                className="p-2 rounded-lg bg-yellow-500/10 text-yellow-400 hover:bg-yellow-500/20 transition-colors"
                                                title="Revoke Access (Make Interested)"
                                            >
                                                <User className="w-4 h-4" />
                                            </button>
                                        )}

                                        <div className="w-px h-6 bg-neutral-800 mx-2" />

                                        <button
                                            onClick={() => toggleAdmin(user)}
                                            className={`p-2 rounded-lg transition-colors ${user.is_admin
                                                ? "bg-red-500/10 text-red-400 hover:bg-red-500/20"
                                                : "bg-purple-500/10 text-purple-400 hover:bg-purple-500/20"
                                                }`}
                                            title={user.is_admin ? "Remove Admin" : "Make Admin"}
                                        >
                                            {user.is_admin ? <ShieldOff className="w-4 h-4" /> : <Shield className="w-4 h-4" />}
                                        </button>
                                        <button
                                            onClick={() => setUserToDelete(user)}
                                            className="p-2 rounded-lg bg-red-500/10 text-red-400 hover:bg-red-500/20"
                                            title="Delete User"
                                        >
                                            <Trash2 className="w-4 h-4" />
                                        </button>
                                    </td>
                                </tr>
                            ))}
                            {!loading && users.length === 0 && (
                                <tr>
                                    <td colSpan={4} className="p-8 text-center text-neutral-500">
                                        No users found.
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* Confirmation Modal */}
            {userToDelete && (
                <div className="fixed inset-0 bg-black/80 flex items-center justify-center p-4 z-50 backdrop-blur-sm">
                    <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-6 max-w-md w-full shadow-2xl">
                        <div className="flex items-start gap-4 mb-6">
                            <div className="w-10 h-10 rounded-full bg-red-500/10 flex items-center justify-center shrink-0">
                                <Trash2 className="w-5 h-5 text-red-500" />
                            </div>
                            <div>
                                <h3 className="text-lg font-bold text-white mb-2">Delete User?</h3>
                                <p className="text-neutral-400">
                                    Are you sure you want to delete <span className="text-white font-medium">{userToDelete.username}</span>? This action cannot be undone.
                                </p>
                                {userToDelete.id === profile?.id && (
                                    <div className="mt-3 bg-red-500/10 border border-red-500/20 rounded-lg p-3">
                                        <p className="text-red-400 text-sm font-medium">
                                            Warning: You are deleting your own account. You will be logged out immediately.
                                        </p>
                                    </div>
                                )}
                            </div>
                        </div>
                        <div className="flex justify-end gap-3">
                            <button
                                onClick={() => setUserToDelete(null)}
                                className="px-4 py-2 rounded-lg bg-neutral-800 text-neutral-300 hover:bg-neutral-700 transition-colors"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={confirmDelete}
                                className="px-4 py-2 rounded-lg bg-red-600 text-white hover:bg-red-700 transition-colors font-medium"
                            >
                                Delete User
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
