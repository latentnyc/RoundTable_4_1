import { Character } from '@/lib/api';
import { User, Bot } from 'lucide-react';

interface PartyMemberProps {
    character: Character;
    onClick?: () => void;
    isActive?: boolean;
}

export default function PartyMember({ character, onClick, isActive }: PartyMemberProps) {
    const isAI = character.is_ai || character.control_mode === 'ai';

    return (
        <div
            onClick={onClick}
            className={`flex flex-col gap-3 text-neutral-200 border-b border-neutral-800 pb-4 mb-4 last:border-0 last:mb-0 last:pb-0 cursor-pointer transition-colors p-2 rounded-lg ${isActive ? 'bg-neutral-800/50 border-purple-500/30' : 'hover:bg-neutral-800/30'}`}
        >
            {/* Header / Portrait - Compact Horizontal */}
            <div className="flex items-center gap-3">
                <div className={`w-12 h-12 shrink-0 rounded-full bg-gradient-to-br ${isAI ? 'from-amber-900 to-orange-900 border-amber-500/50' : 'from-purple-900 to-indigo-900 border-purple-500/50'} flex items-center justify-center border ${isActive ? (isAI ? 'border-amber-500 shadow-[0_0_15px_rgba(245,158,11,0.4)]' : 'border-purple-500 shadow-[0_0_15px_rgba(168,85,247,0.4)]') : (isAI ? 'shadow-[0_0_10px_rgba(245,158,11,0.3)]' : 'shadow-[0_0_10px_rgba(168,85,247,0.3)]')} transition-all`}>
                    {isAI ? <Bot className="w-6 h-6 text-amber-200" /> : <User className="w-6 h-6 text-purple-200" />}
                </div>
                <div className="min-w-0">
                    <h2 className={`text-sm font-bold truncate ${isActive ? (isAI ? 'text-amber-300' : 'text-purple-300') : 'text-white'}`}>{character.name}</h2>
                    <p className={`text-xs font-medium truncate ${isAI ? 'text-amber-400' : 'text-purple-400'}`}>{character.role} • Lvl {character.level}</p>
                </div>
            </div>

            {/* Stats Grid - Cleaner & Compact */}
            <div className="grid grid-cols-3 gap-2">
                <StatBox label="STR" value={character.sheet_data?.stats?.Strength || 10} />
                <StatBox label="DEX" value={character.sheet_data?.stats?.Dexterity || 10} />
                <StatBox label="CON" value={character.sheet_data?.stats?.Constitution || 10} />
                <StatBox label="INT" value={character.sheet_data?.stats?.Intelligence || 10} />
                <StatBox label="WIS" value={character.sheet_data?.stats?.Wisdom || 10} />
                <StatBox label="CHA" value={character.sheet_data?.stats?.Charisma || 10} />
            </div>

            {/* Backstory - Collapsible detail or just very subtle */}
            {character.backstory && (
                <div className="mt-1">
                    <p className="text-[10px] text-neutral-500 line-clamp-2 italic leading-tight">
                        "{character.backstory}"
                    </p>
                </div>
            )}
        </div>
    );
}

function StatBox({ label, value }: { label: string; value: number }) {
    const mod = Math.floor((value - 10) / 2);
    const sign = mod >= 0 ? '+' : '';

    return (
        <div className="bg-neutral-900/50 border border-neutral-800/50 p-1.5 rounded flex flex-col items-center justify-center text-center">
            <span className="text-[10px] font-bold text-neutral-500 uppercase leading-none mb-0.5">{label}</span>
            <div className="flex items-end gap-0.5 leading-none">
                <span className="text-xs font-bold text-white">{value}</span>
                <span className="text-[8px] text-neutral-600">({sign}{mod})</span>
            </div>
        </div>
    );
}
