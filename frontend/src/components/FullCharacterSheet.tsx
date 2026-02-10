import { Character } from '@/lib/api';
import { Shield, Sword, Brain, Heart, Zap, Eye, User, X } from 'lucide-react';

interface FullCharacterSheetProps {
    character: Character;
    onClose?: () => void;
}

export default function FullCharacterSheet({ character, onClose }: FullCharacterSheetProps) {
    return (
        <div className="w-full h-full bg-neutral-900 border border-neutral-800 rounded-xl overflow-hidden flex flex-col relative shadow-2xl">
            {/* Close Button */}
            {onClose && (
                <button
                    onClick={onClose}
                    className="absolute top-4 right-4 p-2 bg-neutral-950/50 hover:bg-neutral-800 rounded-full text-neutral-400 hover:text-white transition-colors z-10"
                    title="Close Character Sheet"
                >
                    <X className="w-5 h-5" />
                </button>
            )}

            {/* Header Banner */}
            <div className="h-48 bg-gradient-to-r from-neutral-900 via-purple-900/20 to-neutral-900 relative">
                <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,_var(--tw-gradient-stops))] from-purple-500/10 via-transparent to-transparent opacity-50" />

                <div className="absolute -bottom-12 left-8 flex items-end gap-6">
                    <div className="w-32 h-32 rounded-full bg-neutral-900 border-4 border-neutral-800 flex items-center justify-center shadow-xl">
                        <div className="w-28 h-28 rounded-full bg-gradient-to-br from-purple-900 to-indigo-900 flex items-center justify-center border border-purple-500/50">
                            <User className="w-16 h-16 text-purple-200" />
                        </div>
                    </div>
                    <div className="mb-4">
                        <h1 className="text-3xl font-bold text-white">{character.name}</h1>
                        <p className="text-purple-400 font-medium text-lg">{character.role} • Level {character.level}</p>
                    </div>
                </div>
            </div>

            {/* Content Area */}
            <div className="flex-1 overflow-y-auto p-8 pt-16 grid grid-cols-1 lg:grid-cols-3 gap-8">

                {/* Left Column: Stats & Vitals */}
                <div className="space-y-6">
                    <div className="bg-neutral-950/50 p-4 rounded-xl border border-neutral-800">
                        <h3 className="text-sm font-semibold text-neutral-500 uppercase tracking-wider mb-4 border-b border-neutral-800 pb-2">Ability Scores</h3>
                        <div className="space-y-2">
                            <StatRow label="Strength" value={character.sheet_data?.stats?.Strength || 10} icon={<Sword className="w-4 h-4" />} />
                            <StatRow label="Dexterity" value={character.sheet_data?.stats?.Dexterity || 10} icon={<Zap className="w-4 h-4" />} />
                            <StatRow label="Constitution" value={character.sheet_data?.stats?.Constitution || 10} icon={<Heart className="w-4 h-4" />} />
                            <StatRow label="Intelligence" value={character.sheet_data?.stats?.Intelligence || 10} icon={<Brain className="w-4 h-4" />} />
                            <StatRow label="Wisdom" value={character.sheet_data?.stats?.Wisdom || 10} icon={<Eye className="w-4 h-4" />} />
                            <StatRow label="Charisma" value={character.sheet_data?.stats?.Charisma || 10} icon={<Shield className="w-4 h-4" />} />
                        </div>
                    </div>

                    <div className="bg-neutral-950/50 p-4 rounded-xl border border-neutral-800">
                        <h3 className="text-sm font-semibold text-neutral-500 uppercase tracking-wider mb-4 border-b border-neutral-800 pb-2">Vitals</h3>
                        <div className="grid grid-cols-2 gap-4">
                            <div className="bg-neutral-900 p-3 rounded text-center border border-neutral-800">
                                <span className="text-xs text-neutral-500 uppercase">HP</span>
                                <div className="text-2xl font-bold text-green-500">
                                    {/* Placeholder logic for HP since it's not in the basic type yet */}
                                    {10 + (character.sheet_data?.stats?.Constitution ? Math.floor((character.sheet_data.stats.Constitution - 10) / 2) : 0)}
                                    <span className="text-sm text-neutral-600 font-normal"> / max</span>
                                </div>
                            </div>
                            <div className="bg-neutral-900 p-3 rounded text-center border border-neutral-800">
                                <span className="text-xs text-neutral-500 uppercase">AC</span>
                                <div className="text-2xl font-bold text-blue-500">
                                    {10 + (character.sheet_data?.stats?.Dexterity ? Math.floor((character.sheet_data.stats.Dexterity - 10) / 2) : 0)}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Center Column: Backstory & Info */}
                <div className="lg:col-span-2 space-y-6">
                    <div className="bg-neutral-950/50 p-6 rounded-xl border border-neutral-800">
                        <h3 className="text-sm font-semibold text-neutral-500 uppercase tracking-wider mb-4 border-b border-neutral-800 pb-2">Biography</h3>
                        {character.backstory ? (
                            <p className="text-neutral-300 leading-relaxed italic">
                                "{character.backstory}"
                            </p>
                        ) : (
                            <p className="text-neutral-600 italic">No backstory provided.</p>
                        )}
                    </div>

                    {/* Placeholder for Inventory or Skills */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div className="bg-neutral-950/50 p-6 rounded-xl border border-neutral-800 h-64 flex flex-col items-center justify-center text-neutral-600 gap-2">
                            <Shield className="w-8 h-8 opacity-20" />
                            <p>Equipment & Inventory</p>
                            <span className="text-xs text-neutral-700">(Coming Soon)</span>
                        </div>
                        <div className="bg-neutral-950/50 p-6 rounded-xl border border-neutral-800 h-64 flex flex-col items-center justify-center text-neutral-600 gap-2">
                            <Zap className="w-8 h-8 opacity-20" />
                            <p>Spells & Abilities</p>
                            <span className="text-xs text-neutral-700">(Coming Soon)</span>
                        </div>
                    </div>
                </div>

            </div>
        </div>
    );
}

function StatRow({ label, value, icon }: { label: string; value: number; icon: React.ReactNode }) {
    const mod = Math.floor((value - 10) / 2);
    const sign = mod >= 0 ? '+' : '';

    return (
        <div className="flex items-center justify-between p-2 hover:bg-neutral-900 rounded transition-colors group">
            <div className="flex items-center gap-3">
                <div className="p-1.5 bg-neutral-900 rounded text-neutral-500 group-hover:text-purple-400 transition-colors">
                    {icon}
                </div>
                <span className="text-neutral-400 font-medium">{label}</span>
            </div>
            <div className="flex items-baseline gap-2">
                <span className="text-lg font-bold text-white">{value}</span>
                <span className="text-xs text-neutral-500 font-mono bg-neutral-900 px-1.5 py-0.5 rounded">
                    {sign}{mod}
                </span>
            </div>
        </div>
    );
}
