import { useRef, useEffect, useState } from 'react';
import { useSocketStore, DebugLogItem } from '@/lib/socket';
import { useAuthStore } from '@/store/authStore';

export default function DebugPanel() {
    const { debugLogs, clearLogs, isConnected, socket, lastPing, measurePing } = useSocketStore();
    const { user } = useAuthStore();
    const scrollRef = useRef<HTMLDivElement>(null);

    // Health Check State
    // const [healthStatus, setHealthStatus] = useState<'idle' | 'checking' | 'online' | 'offline' | 'error'>('idle'); // Removed in favor of direct prop usage
    // const [healthMessage, setHealthMessage] = useState<string>(''); // Replaced by lastPing
    const [showClearConfirm, setShowClearConfirm] = useState(false);

    // Auto-ping every 5 seconds
    useEffect(() => {
        if (!isConnected) return;

        const interval = setInterval(() => {
            measurePing();
        }, 5000);

        // Initial measurement
        measurePing();

        return () => clearInterval(interval);
    }, [isConnected]);

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
        // Distinct color for AI Characters vs System/DM
        if (agentName && agentName !== 'System' && agentName !== 'Dungeon Master') {
            switch (type) {
                case 'llm_start': return 'text-purple-400 border-purple-900/30 bg-purple-900/10';
                case 'llm_end': return 'text-pink-400 border-pink-900/30 bg-pink-900/10';
                case 'tool_start': return 'text-fuchsia-400 border-fuchsia-900/30 bg-fuchsia-900/10';
                case 'tool_end': return 'text-rose-400 border-rose-900/30 bg-rose-900/10';
                default: return 'text-purple-400';
            }
        }

        switch (type) {
            case 'llm_start': return 'text-blue-400 border-blue-900/30 bg-blue-900/10';
            case 'llm_end': return 'text-green-400 border-green-900/30 bg-green-900/10';
            case 'tool_start': return 'text-yellow-400 border-yellow-900/30 bg-yellow-900/10';
            case 'tool_end': return 'text-orange-400 border-orange-900/30 bg-orange-900/10';
            default: return 'text-gray-400';
        }
    };

    return (
        <div className="flex flex-col h-full bg-neutral-900/50 rounded-lg border border-neutral-800 overflow-hidden">
            {/* Status / Health Check Button (Now a display) */}
            <div
                className={`
                    w-full px-3 py-2 text-[10px] font-mono border-b border-neutral-800 
                    flex items-center justify-between transition-colors bg-black/50
                `}
            >
                <div className="flex flex-col items-start gap-0.5">
                    <div className="flex items-center gap-2">
                        <span className={`
                            w-2 h-2 rounded-full 
                            ${isConnected ? "bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.5)]" : "bg-red-500"}
                        `} />
                        <span className={`font-bold ${getStatusColor()}`}>
                            {getStatusMessage()}
                        </span>
                    </div>
                    {(socket?.id || user?.uid) && (
                        <span className="text-neutral-600 text-[9px] truncate max-w-[200px]">
                            {socket?.id ? `Socket: ${socket.id}` : `UID: ${user?.uid}`}
                        </span>
                    )}
                </div>
            </div>

            <div className="flex items-center justify-between p-3 border-b border-neutral-800 bg-neutral-900">
                <h3 className="text-xs font-semibold text-neutral-400 uppercase tracking-wider flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                    AI Query Log
                </h3>

                {showClearConfirm ? (
                    <div className="flex items-center gap-2">
                        <span className="text-[10px] text-red-400 font-bold uppercase">Are you sure?</span>
                        <button
                            onClick={() => {
                                clearLogs();
                                setShowClearConfirm(false);
                            }}
                            className="text-[10px] bg-red-900/30 border border-red-900/50 text-red-400 px-2 py-0.5 rounded hover:bg-red-900/50 transition-colors"
                        >
                            Yes
                        </button>
                        <button
                            onClick={() => setShowClearConfirm(false)}
                            className="text-[10px] text-neutral-500 hover:text-neutral-300 transition-colors"
                        >
                            Cancel
                        </button>
                    </div>
                ) : (
                    <button
                        onClick={() => setShowClearConfirm(true)}
                        className="text-xs text-neutral-600 hover:text-white transition-colors"
                    >
                        Clear
                    </button>
                )}
            </div>

            <div
                ref={scrollRef}
                className="flex-1 overflow-y-auto p-4 space-y-3 font-mono text-xs"
            >
                {debugLogs.length === 0 ? (
                    <div className="text-neutral-600 text-center mt-10 italic">
                        No AI activity recorded yet...
                    </div>
                ) : (
                    debugLogs.map((log, idx) => (
                        <div key={idx} className={`p-3 rounded border ${getLogColor(log.type, log.agent_name)}`}>
                            <div className="flex justify-between items-start mb-1 opacity-75">
                                <span className="uppercase font-bold text-[10px] flex items-center gap-2">
                                    {log.agent_name && (
                                        <span className="px-1.5 py-0.5 rounded bg-black/30 text-[9px]">
                                            {log.agent_name}
                                        </span>
                                    )}
                                    {log.type.replace('_', ' ')}
                                </span>
                                <span className="text-[10px]">{log.timestamp}</span>
                            </div>
                            <div className="whitespace-pre-wrap break-words mb-2">
                                {log.content}
                            </div>
                            {/* Show full content as requested */}
                            {log.full_content && (
                                <details className="mt-2 text-[10px] bg-black/20 p-2 rounded">
                                    <summary className="cursor-pointer opacity-70 hover:opacity-100">Show Full Payload</summary>
                                    <pre className="mt-2 text-wrap break-all whitespace-pre-wrap overflow-x-auto">
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
        </div>
    );
}
