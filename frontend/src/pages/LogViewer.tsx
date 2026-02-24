import { useEffect, useRef } from 'react';
import { useSocketStore, DebugLogItem } from '@/lib/socket';
import { useSocketContext } from '@/lib/SocketProvider';
import { useSearchParams } from 'react-router-dom';
import { useAuthStore } from '@/store/authStore';

export default function LogViewer() {
    const debugLogs = useSocketStore(state => state.debugLogs);
    const { socket, isConnected } = useSocketContext();
    const { user } = useAuthStore();
    const [searchParams] = useSearchParams();
    const campaignId = searchParams.get('campaignId');
    const scrollRef = useRef<HTMLDivElement>(null);

    // Connect to socket on mount
    useEffect(() => {
        if (campaignId && user?.uid && socket && isConnected) {
            // Emitting get_logs once connected
            socket.emit('get_logs', { campaign_id: campaignId });
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [campaignId, user?.uid, socket, isConnected]);
    // We only want to trigger this once or when IDs change, not when `connect` changes reference (though it shouldn't)

    // Auto-scroll
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

    if (!campaignId) {
        return <div className="flex items-center justify-center h-screen bg-neutral-950 text-neutral-500 font-mono text-xs">No Campaign ID provided.</div>;
    }

    if (!isConnected) {
        return (
            <div className="flex items-center justify-center h-screen bg-neutral-950 text-neutral-500 font-mono text-xs gap-2">
                <span className="w-2 h-2 rounded-full bg-yellow-500 animate-pulse" />
                Connecting to Game Server...
            </div>
        );
    }

    return (
        <div className="flex flex-col h-screen w-screen bg-neutral-950 text-neutral-200 font-mono text-xs overflow-hidden">
            <div className="flex items-center justify-between p-3 border-b border-neutral-800 bg-neutral-900">
                <h3 className="font-bold flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                    AI Debug Logs
                </h3>
                <div className="flex items-center gap-2">
                    <span className="text-[10px] text-neutral-600 uppercase tracking-wider">{campaignId.slice(0, 8)}...</span>
                    <button
                        onClick={() => {
                            if (socket && campaignId) {
                                socket.emit('clear_logs', { campaign_id: campaignId });
                            }
                        }}
                        className="px-2 py-1 bg-red-900/30 text-red-400 rounded hover:bg-red-900/50 transition-colors"
                    >
                        Clear Logs
                    </button>
                </div>
            </div>

            <div
                ref={scrollRef}
                className="flex-1 overflow-y-auto p-4 space-y-3"
            >
                {debugLogs.length === 0 ? (
                    <div className="text-neutral-600 text-center mt-10 italic">
                        No active logs...
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
                            {!!log.full_content && (
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
