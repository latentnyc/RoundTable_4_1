import { useEffect, useState } from 'react';
import api from '@/lib/api';
import { useSocketStore } from '@/lib/socket';

interface Command {
    name: string;
    description: string;
    usage: string;
    aliases: string[];
}

interface SuggestionItem {
    text: string;           // The text to insert/replace
    displayText: string;    // What the user sees (e.g. "@attack" or "Goblin 1")
    description: string;    // Help text
    isArgument: boolean;    // Are we suggesting a command or an argument?
}

interface CommandSuggestionsProps {
    inputValue: string;
    onSelect: (selectedText: string, isArgument: boolean) => void;
}

export default function CommandSuggestions({ inputValue, onSelect }: CommandSuggestionsProps) {
    const [commands, setCommands] = useState<Command[]>([]);
    const [filtered, setFiltered] = useState<SuggestionItem[]>([]);
    const [selectedIndex, setSelectedIndex] = useState(0);

    const gameState = useSocketStore(state => state.gameState);


    useEffect(() => {
        api.get('/game/commands').then(res => {
            setCommands(res.data);
        }).catch(err => console.error("Failed to fetch commands:", err));
    }, []);

    useEffect(() => {
        if (!inputValue.trim().startsWith('@')) {
            setFiltered([]);
            return;
        }

        const parts = inputValue.trimStart().split(' ');
        const baseCmd = parts[0].substring(1).toLowerCase(); // remove '@'

        let suggestions: SuggestionItem[] = [];

        // 1. If user is still typing the base command (no spaces yet)
        if (parts.length === 1) {
            const matches = commands.filter(c =>
                c.name.toLowerCase().startsWith(baseCmd) ||
                c.aliases.some(a => a.toLowerCase().startsWith(baseCmd))
            );

            suggestions = matches.map(c => ({
                text: c.name,
                displayText: `@${c.name}`,
                description: c.description,
                isArgument: false
            }));
        }
        // 2. If user is typing an argument (has a space)
        else {
            const argQuery = parts.slice(1).join(' ').toLowerCase();

            if (baseCmd === 'attack' || baseCmd === 'cast') {
                // Suggest living enemies and hostile NPCs
                const targets: { name: string, desc: string }[] = [];

                if (gameState?.enemies) {
                    gameState.enemies.filter(e => e.hp_current > 0).forEach(e => {
                        targets.push({ name: e.name, desc: 'Enemy' });
                    });
                }
                if (gameState?.npcs) {
                    gameState.npcs.filter(n => n.hp_current > 0 && n.data?.hostile).forEach(n => {
                        targets.push({ name: n.name, desc: 'Hostile NPC' });
                    });
                }

                // Also if they want to cast on allies (for cast specifically)
                if (baseCmd === 'cast' && gameState?.party) {
                    gameState.party.filter(p => p.hp_current > 0).forEach(p => {
                        targets.push({ name: p.name, desc: 'Ally' });
                    });
                }

                const matches = targets.filter(t => t.name.toLowerCase().startsWith(argQuery) || t.name.toLowerCase().includes(argQuery));

                suggestions = matches.map(t => ({
                    text: t.name,
                    displayText: t.name,
                    description: t.desc,
                    isArgument: true
                }));
            }
            else if (baseCmd === 'open' || baseCmd === 'close' || baseCmd === 'examine' || baseCmd === 'look') {
                // Suggest interactables and vessels
                const targets: { name: string, desc: string }[] = [];

                if (gameState?.location?.interactables) {
                    gameState.location.interactables.forEach(i => {
                        // For open/close, maybe only suggest if state matches, but keeping it simple for now
                        targets.push({ name: i.name || i.id, desc: i.type || 'Object' });
                    });
                }
                if (gameState?.vessels) {
                    gameState.vessels.forEach(v => {
                        targets.push({ name: v.name, desc: 'Container' });
                    });
                }

                const matches = targets.filter(t => t.name.toLowerCase().startsWith(argQuery) || t.name.toLowerCase().includes(argQuery));

                suggestions = matches.map(t => ({
                    text: t.name,
                    displayText: t.name,
                    description: t.desc,
                    isArgument: true
                }));
            }
        }

        setFiltered(suggestions);
        setSelectedIndex(0);
    }, [inputValue, commands, gameState]);

    if (filtered.length === 0) return null;

    return (
        <div className="absolute bottom-full left-0 w-full mb-2 bg-neutral-900 border border-neutral-700 rounded-lg shadow-xl overflow-hidden z-[100]">
            <div className="text-xs font-bold text-neutral-500 px-3 py-2 bg-neutral-950/50 border-b border-neutral-800">
                {filtered[0]?.isArgument ? 'SUGGESTED TARGETS' : 'COMMANDS'}
            </div>
            <div className="max-h-60 overflow-y-auto">
                {filtered.map((item, idx) => (
                    <button
                        key={item.text + idx}
                        className={`w-full text-left px-3 py-2 text-sm flex items-center justify-between hover:bg-neutral-800 transition-colors ${idx === selectedIndex ? 'bg-purple-900/30 text-purple-200' : 'text-neutral-300'}`}
                        onClick={() => onSelect(item.text, item.isArgument)}
                    >
                        <span className="font-mono font-bold">{item.displayText}</span>
                        <span className="text-xs text-neutral-500 truncate ml-2">{item.description}</span>
                    </button>
                ))}
            </div>
        </div>
    );
}
