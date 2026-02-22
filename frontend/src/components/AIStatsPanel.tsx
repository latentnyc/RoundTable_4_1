import { useSocketStore } from '@/lib/socket';
import { Sparkles, Zap, Activity } from 'lucide-react';

export default function AIStatsPanel() {
    const { aiStats } = useSocketStore();

    if (!aiStats) return null;

    return (
        <div className="flex flex-col h-full bg-neutral-900/10 backdrop-blur-sm rounded-xl border border-white/5 overflow-y-auto overflow-x-hidden">
            <div className="flex items-center justify-between px-2 py-1.5 border-b border-white/5 bg-transparent">
                <h3 className="text-[10px] font-medium text-neutral-500 uppercase tracking-widest flex items-center gap-1.5">
                    <Sparkles className="w-2.5 h-2.5 text-amber-500/50" />
                    AI Statistics
                </h3>
            </div>

            <div className="p-2 space-y-2">
                {/* Main Stats Grid */}
                <div className="grid grid-cols-3 gap-1.5">
                    <div className="bg-white/5 p-1.5 rounded-lg border border-white/5">
                        <div className="text-[9px] text-neutral-600 uppercase font-bold mb-0.5 flex items-center gap-1 tracking-wider">
                            <Zap className="w-3 h-3 text-blue-500/50" /> Input
                        </div>
                        <div className="text-base font-semibold font-mono text-neutral-300">
                            {aiStats.inputTokens.toLocaleString()}
                        </div>
                    </div>
                    <div className="bg-white/5 p-1.5 rounded-lg border border-white/5">
                        <div className="text-[9px] text-neutral-600 uppercase font-bold mb-0.5 flex items-center gap-1 tracking-wider">
                            <Zap className="w-3 h-3 rotate-180 text-purple-500/50" /> Output
                        </div>
                        <div className="text-base font-semibold font-mono text-neutral-300">
                            {aiStats.outputTokens.toLocaleString()}
                        </div>
                    </div>
                    <div className="bg-white/5 p-1.5 rounded-lg border border-white/5">
                        <div className="text-[9px] text-neutral-600 uppercase font-bold mb-0.5 flex items-center gap-1 tracking-wider">
                            <Activity className="w-3 h-3 text-emerald-500/50" /> Queries
                        </div>
                        <div className="text-base font-semibold font-mono text-neutral-300">
                            {aiStats.queryCount.toLocaleString()}
                        </div>
                    </div>
                </div>

                {/* Last Request Details */}
                {aiStats.lastRequest && (
                    <div className="bg-white/5 rounded-lg border border-white/5 p-2">
                        <div className="text-[9px] text-neutral-600 uppercase font-bold mb-1.5 tracking-wider">Last Request</div>

                        <div className="space-y-1 text-[11px] font-mono">
                            <div className="flex justify-between items-center opacity-70">
                                <span className="text-neutral-500">Agent</span>
                                <span className="text-neutral-400 bg-white/5 px-1 rounded border border-white/5">{aiStats.lastRequest.agent}</span>
                            </div>
                            <div className="flex justify-between items-center opacity-70">
                                <span className="text-neutral-500">Model</span>
                                <span className="text-neutral-400 truncate max-w-[120px]">{aiStats.lastRequest.model}</span>
                            </div>
                            <div className="flex justify-between items-center opacity-70">
                                <span className="text-neutral-500">Tokens</span>
                                <span className="text-amber-500/70">{aiStats.lastRequest.tokens.toLocaleString()}</span>
                            </div>
                        </div>
                    </div>
                )}

                {aiStats.lastImageRequest && (
                    <div className="bg-white/5 rounded-lg border border-white/5 p-2 mt-0">
                        <div className="text-[9px] text-neutral-600 uppercase font-bold mb-1.5 tracking-wider">Last Image Gen</div>

                        <div className="space-y-1 text-[11px] font-mono">
                            <div className="flex justify-between items-center opacity-70">
                                <span className="text-neutral-500">Model</span>
                                <span className="text-neutral-400 truncate max-w-[120px]">{aiStats.lastImageRequest.model}</span>
                            </div>
                            <div className="flex justify-between items-center opacity-70">
                                <span className="text-neutral-500">Generated</span>
                                <span className="text-pink-500/70">{aiStats.imageCount?.toLocaleString() || 0}</span>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
