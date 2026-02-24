import { useRef, useEffect, useState } from 'react';
import { useSocketStore, DebugLogItem } from '@/lib/socket';
import { useSocketContext } from '@/lib/SocketProvider';
import { useAuthStore } from '@/store/authStore';

interface DebugPanelProps {
    campaignId?: string;
}

export default function DebugPanel({ campaignId }: DebugPanelProps) {
    const { socket, isConnected } = useSocketContext();
    const debugLogs = useSocketStore(state => state.debugLogs);
    const lastPing = useSocketStore(state => state.lastPing);
    const { user, token } = useAuthStore();
    const scrollRef = useRef<HTMLDivElement>(null);

    // Initial Fetch
    useEffect(() => {
        if (!campaignId || !isConnected || !token) return;

        const SOCKET_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000';
        fetch(`${SOCKET_URL}/campaigns/${campaignId}/logs?limit=50`, {
            headers: { 'Authorization': `Bearer ${token}` }
        })
            .then(res => res.json())
            .then(logs => {
                const formattedLogs = logs.map((l: any) => ({
                    type: l.type,
                    content: l.content,
                    full_content: l.full_content,
                    timestamp: new Date(l.created_at).toLocaleTimeString(),
                    agent_name: l.content.startsWith('[') ? l.content.match(/\[(.*?)\]/)?.[1] : undefined
                })).reverse();
                useSocketStore.getState().setDebugLogs(formattedLogs);
            })
            .catch(e => console.error("Failed to fetch logs:", e));
    }, [campaignId, isConnected, token]);

    // Health Check State
    // const [healthStatus, setHealthStatus] = useState<'idle' | 'checking' | 'online' | 'offline' | 'error'>('idle'); // Removed in favor of direct prop usage
    // const [healthMessage, setHealthMessage] = useState<string>(''); // Replaced by lastPing
    const [showClearConfirm, setShowClearConfirm] = useState(false);

    const openLogPopup = () => {
        const url = campaignId ? `/logs?campaignId=${campaignId}` : '/logs';
        window.open(url, 'AI_Logs', 'width=800,height=600,scrollbars=yes,resizable=yes');
    };

    // Auto-ping every 5 seconds
    useEffect(() => {
        if (!isConnected || !socket) return;

        const measurePing = () => {
            const start = Date.now();
            socket.emit('test_connection', {}, () => {
                useSocketStore.getState().setPing(Date.now() - start);
            });
        };

        const interval = setInterval(measurePing, 5000);
        measurePing();

        return () => clearInterval(interval);
    }, [isConnected, socket]);

    // Derived status message
    const getStatusMessage = () => {
        if (!isConnected) return 'Disconnected';
        if (lastPing !== null) return `${lastPing}ms`;
        return 'Connected';
    };

    const getStatusColor = () => {
        if (!isConnected) return 'text-red-400';
        if (lastPing !== null && lastPing > 200) return 'text-yellow-400';
        return 'text-green-400';
    };

    // Auto-scroll to bottom
    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [debugLogs]);

    const getLogColor = (type: DebugLogItem['type'], agentName?: string) => {
        if (agentName && agentName !== 'System' && agentName !== 'Dungeon Master') {
            switch (type) {
                case 'llm_start': return 'text-purple-400';
                case 'llm_end': return 'text-purple-300';
                case 'tool_start': return 'text-fuchsia-400';
                case 'tool_end': return 'text-fuchsia-300';
                default: return 'text-purple-400';
            }
        }

        switch (type) {
            case 'llm_start': return 'text-blue-400';
            case 'llm_end': return 'text-emerald-400';
            case 'tool_start': return 'text-amber-400';
            case 'tool_end': return 'text-orange-400';
            default: return 'text-neutral-500';
        }
    };

    return (
        <div className="flex flex-col h-full bg-neutral-900/40 backdrop-blur-md rounded-xl border border-white/5 overflow-hidden">
            {/* Status / Health Check Display */}
            <div className="w-full px-3 py-2 border-b border-white/5 flex items-center justify-between transition-colors bg-white/[0.02]">
                <div className="flex items-center gap-2">
                    <span className={`
                        w-1.5 h-1.5 rounded-full
                        ${isConnected ? "bg-emerald-500/50 shadow-[0_0_8px_rgba(16,185,129,0.3)]" : "bg-red-500/50"}
                    `} />
                    <span className={`font-mono text-[10px] ${getStatusColor()} opacity-80`}>
                        {getStatusMessage()}
                    </span>
                </div>
                {(socket?.id || user?.uid) && (
                    <span className="text-neutral-600 text-[9px] font-mono truncate max-w-[120px]">
                        {socket?.id ? `ID: ${socket.id.slice(0, 6)}...` : `UID: ${user?.uid.slice(0, 6)}...`}
                    </span>
                )}
            </div>

            <div className="flex items-center justify-between px-3 py-2 border-b border-white/5 bg-transparent">
                <h3 className="text-[10px] font-semibold text-neutral-500 uppercase tracking-widest">
                    Live Logs
                </h3>

                <div className="flex items-center gap-3">
                    <button
                        onClick={openLogPopup}
                        className="text-[10px] text-neutral-600 hover:text-neutral-300 transition-colors uppercase tracking-wider flex items-center gap-1"
                        title="Open Full Console"
                    >
                        Expand
                    </button>

                    <div className="h-3 w-px bg-white/10"></div>

                    {showClearConfirm ? (
                        <div className="flex items-center gap-2">
                            <span className="text-[9px] text-red-400/80 font-medium">Reset?</span>
                            <button
                                onClick={() => {
                                    socket?.emit('clear_debug_logs');
                                    setShowClearConfirm(false);
                                }}
                                className="text-[9px] text-red-400 hover:text-red-300 transition-colors"
                            >
                                Y
                            </button>
                            <button
                                onClick={() => setShowClearConfirm(false)}
                                className="text-[9px] text-neutral-500 hover:text-neutral-300 transition-colors"
                            >
                                N
                            </button>
                        </div>
                    ) : (
                        <button
                            onClick={() => setShowClearConfirm(true)}
                            className="text-[10px] text-neutral-600 hover:text-neutral-400 transition-colors uppercase tracking-wider"
                            title="Clear Logs"
                        >
                            Clear
                        </button>
                    )}
                </div>
            </div>

            <div
                ref={scrollRef}
                className="flex-1 overflow-y-auto p-2 space-y-0.5 font-mono text-[10px]"
            >
                {debugLogs.length === 0 ? (
                    <div className="h-full flex flex-col items-center justify-center text-neutral-700 italic text-[10px] gap-2">
                        <span>Waiting for activity...</span>
                    </div>
                ) : (
                    debugLogs.map((log, idx) => (
                        <div key={idx} className={`px-2 py-1.5 rounded hover:bg-white/[0.02] transition-colors group ${getLogColor(log.type, log.agent_name)}`}>
                            <div className="flex justify-between items-baseline opacity-50 group-hover:opacity-100 transition-opacity mb-0.5">
                                <span className="uppercase font-bold text-[8px] tracking-wider text-neutral-600">
                                    {log.agent_name || log.type.replace('_', ' ')}
                                </span>
                                <span className="text-[8px] opacity-50">{log.timestamp.split(' ')[1]}</span>
                            </div>

                            <div className="text-neutral-400/90 leading-tight">
                                {typeof log.content === 'string' ? log.content : JSON.stringify(log.content)}
                            </div>

                            {/* Only show expander if there is significant content */}
                            {!!log.full_content && (
                                <details className="mt-1 opacity-40 hover:opacity-100 transition-opacity">
                                    <summary className="cursor-pointer text-[8px] flex items-center gap-1 select-none text-neutral-600 hover:text-neutral-400">
                                        <span>Show Payload</span>
                                    </summary>
                                    <pre className="mt-1 text-[9px] text-neutral-500 overflow-x-auto p-2 rounded bg-black/40 border border-white/5 mx-[-4px]">
                                        {typeof log.full_content === 'string'
                                            ? log.full_content
                                            : JSON.stringify(log.full_content, null, 2)}
                                    </pre>
                                </details>
                            )}
                        </div>
                    ))
                )}
            </div>
        </div >
    );
}
