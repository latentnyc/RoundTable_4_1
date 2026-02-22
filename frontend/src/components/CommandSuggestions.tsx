import { useEffect, useState } from 'react';
import api from '@/lib/api';

interface Command {
    name: string;
    description: string;
    usage: string;
    aliases: string[];
}

interface CommandSuggestionsProps {
    inputValue: string;
    onSelect: (command: string) => void;
}

export default function CommandSuggestions({ inputValue, onSelect }: CommandSuggestionsProps) {
    const [commands, setCommands] = useState<Command[]>([]);
    const [filtered, setFiltered] = useState<Command[]>([]);
    const [selectedIndex, setSelectedIndex] = useState(0);

    useEffect(() => {
        // Fetch commands on mount
        api.get('/game/commands').then(res => {
            setCommands(res.data);
        }).catch(err => console.error("Failed to fetch commands:", err));
    }, []);

    useEffect(() => {
        // Filter based on input
        if (!inputValue.startsWith('@')) {
            setFiltered([]);
            return;
        }

        const query = inputValue.substring(1).toLowerCase();
        const matches = commands.filter(c =>
            c.name.toLowerCase().startsWith(query) ||
            c.aliases.some(a => a.toLowerCase().startsWith(query))
        );
        setFiltered(matches);
        setSelectedIndex(0);
    }, [inputValue, commands]);

    // Keyboard navigation listener attached to window or handled by parent?
    // Usually better handled by parent input onKeyDown.
    // But we can expose a ref or similar.
    // For simplicity, let's assume parent handles Up/Down/Enter and calls a method here?
    // Actually, parent controls render, so parent should handle keydown and pass index?
    // Let's keep it simple: Parent handles KeyDown and we just render.
    // BUT, we need to communicate the "Selected Command" back to parent on Enter.

    // Changing approach: This component just RENDERS the list.
    // The Filtering logic should probably be here, but the SELECTION state needs coordination.

    if (filtered.length === 0) return null;

    return (
        <div className="absolute bottom-full left-0 w-full mb-2 bg-neutral-900 border border-neutral-700 rounded-lg shadow-xl overflow-hidden z-50">
            <div className="text-xs font-bold text-neutral-500 px-3 py-2 bg-neutral-950/50 border-b border-neutral-800">
                COMMANDS
            </div>
            <div className="max-h-60 overflow-y-auto">
                {filtered.map((cmd, idx) => (
                    <button
                        key={cmd.name}
                        className={`w-full text-left px-3 py-2 text-sm flex items-center justify-between hover:bg-neutral-800 transition-colors ${idx === selectedIndex ? 'bg-purple-900/30 text-purple-200' : 'text-neutral-300'}`}
                        onClick={() => onSelect(cmd.name)}
                    >
                        <span className="font-mono font-bold">@{cmd.name}</span>
                        <span className="text-xs text-neutral-500 truncate ml-2">{cmd.description}</span>
                    </button>
                ))}
            </div>
        </div>
    );
}
