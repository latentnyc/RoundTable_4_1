
import { useEffect, useState, useRef } from 'react';
import { useSocketStore } from '@/lib/socket';
import { useSocketContext } from '@/lib/SocketProvider';
import { useAuthStore } from '@/store/authStore';
import { Send, User, Bot, Sparkles, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Character } from '@/lib/api';
import CommandSuggestions from './CommandSuggestions';

interface ChatInterfaceProps {
    campaignId: string;
    characterId?: string;
}

export default function ChatInterface({ characterId }: ChatInterfaceProps) {
    const { profile, user } = useAuthStore();
    const messages = useSocketStore(state => state.messages);
    const { socket } = useSocketContext();
    const [inputValue, setInputValue] = useState('');
    const [showClearConfirm, setShowClearConfirm] = useState(false);
    const bottomRef = useRef<HTMLDivElement>(null);
    const [isDmTyping, setIsDmTyping] = useState(false);

    useEffect(() => {
        if (!socket) return;

        const handleCommandRejected = (data: { content: string, reason: string }) => {
            setInputValue(data.content);
            console.warn("Command rejected:", data.reason);
        };

        const handleTyping = (data: { sender_id: string, is_typing: boolean }) => {
            if (data.sender_id === 'dm') {
                setIsDmTyping(data.is_typing);
            }
        };

        socket.on('command_rejected', handleCommandRejected);
        socket.on('typing_indicator', handleTyping);

        return () => {
            socket.off('command_rejected', handleCommandRejected);
            socket.off('typing_indicator', handleTyping);
        };
    }, [socket]);


    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    // ...

    const handleSend = () => {
        if (!inputValue.trim()) return;

        // Find active character
        const party = (useSocketStore.getState().gameState?.party || []) as Character[];
        // Priority: Passed characterId prop -> Active Store Character -> First Character owned by user -> User Profile

        let senderName = profile?.username || 'Player';
        let senderId = profile?.id; // Default to user ID if no character

        // We need to know WHICH character the user is "acting" as.
        // The `characterId` prop is passed from GameInterface.
        // If it's set, we use it.
        if (characterId) {
            const char = party.find(p => p.id === characterId);
            if (char) {
                senderName = char.name;
                senderId = char.id;
            }
        } else {
            // Try to find ANY character owned by user?
            // Use profile.id OR user.uid (firebase auth)
            const userId = profile?.id || user?.uid;

            if (userId) {
                const myChar = party.find(p => p.user_id === userId);
                if (myChar) {
                    senderName = myChar.name;
                    senderId = myChar.id; // Send Char ID so backend knows it's a character acting
                }
            }
        }

        if (socket && inputValue.trim()) {
            const apiKey = localStorage.getItem('gemini_api_key');
            const model = localStorage.getItem('selected_model');

            socket.emit('chat_message', {
                content: inputValue,
                sender_name: senderName,
                sender_id: senderId,
                api_key: apiKey,
                model_name: model
            });
        }

        setInputValue('');
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    return (
        <div className="flex flex-col h-full bg-neutral-900/50 backdrop-blur rounded-xl border border-neutral-800 overflow-hidden">
            {/* Header */}
            <div className="p-3 border-b border-neutral-800 flex justify-between items-center bg-neutral-900/80">
                <div className="flex items-center gap-3">
                    <h3 className="font-semibold text-neutral-200 flex items-center gap-2">
                        <Sparkles className="w-4 h-4 text-purple-400" />
                        Party Chat
                    </h3>
                    {isDmTyping && (
                        <div className="flex items-center gap-1.5 text-amber-400 bg-amber-900/40 px-2 py-0.5 rounded-full shadow-inner border border-amber-500/30 overflow-hidden">
                            <Loader2 className="w-3 h-3 animate-spin" />
                            <span className="text-[10px] font-bold tracking-wider uppercase text-amber-200">DM Narrating</span>
                        </div>
                    )}
                </div>

                {showClearConfirm ? (
                    <div className="flex items-center gap-2">
                        <span className="text-[10px] text-red-400 font-bold uppercase">Are you sure?</span>
                        <button
                            onClick={() => {
                                socket?.emit('clear_chat');
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
            {/* Messages Area */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {messages.length === 0 && (
                    <div className="text-center text-neutral-500 mt-10">
                        <p>The chronicle begins here...</p>
                    </div>
                )}

                {messages.map((msg, idx) => {
                    // Find the character associated with this message
                    const party = (useSocketStore.getState().gameState?.party || []) as Character[];
                    const isSystem = msg.is_system;
                    const isDM = msg.sender_id === 'dm';

                    // Is this ME? (My ID directly OR a character I own)
                    const isMyCharacter = party.some(p => p.id === msg.sender_id && p.user_id === profile?.id);
                    const isMe = msg.sender_id === profile?.id || isMyCharacter;

                    // Determine if the sender is an AI character
                    // We check if the sender_id matches an AI character in the party
                    const senderChar = party.find(p => p.id === msg.sender_id);
                    const isAI = senderChar?.is_ai || senderChar?.control_mode === 'ai';

                    if (isSystem) {
                        const isTurnAnnouncement = msg.content.includes("It is now") && msg.content.includes("turn!");
                        const displayContent = msg.content.replace(/\*\*/g, '');
                        return (
                            <div key={idx} className="flex justify-center my-4">
                                <span className={cn(
                                    "px-3 py-1 rounded-full border shadow-sm",
                                    isTurnAnnouncement
                                        ? "text-sm text-orange-200 bg-orange-950/60 border-orange-800/50 font-semibold tracking-wide"
                                        : "text-xs text-neutral-500 bg-neutral-800/50 border-neutral-800"
                                )}>
                                    {displayContent}
                                </span>
                            </div>
                        );
                    }

                    return (
                        <div key={idx} className={cn("flex gap-3", isMe ? "flex-row-reverse" : "flex-row")}>
                            {/* Avatar */}
                            <div className={cn(
                                "w-8 h-8 rounded-full flex items-center justify-center shrink-0",
                                isMe && !isAI ? "bg-purple-900 text-purple-200" : (isDM || isAI) ? "bg-amber-900 text-amber-200" : "bg-neutral-800 text-neutral-400"
                            )}>
                                {isDM || isAI ? <Bot className="w-5 h-5" /> : <User className="w-5 h-5" />}
                            </div>

                            {/* Bubble */}
                            <div className={cn(
                                "flex flex-col max-w-[95%]",
                                isMe ? "items-end" : "items-start"
                            )}>
                                <span className="text-base font-semibold text-neutral-300 mb-1 px-1 flex items-center gap-2">
                                    {msg.sender_name} <span className="text-xs font-normal opacity-50">{msg.timestamp}</span>
                                </span>
                                <div className={cn(
                                    "px-5 py-3 rounded-2xl text-base leading-relaxed shadow-md",
                                    isMe
                                        ? "bg-purple-600 text-white rounded-tr-sm"
                                        : (isDM || isAI)
                                            ? "bg-amber-900/40 border border-amber-500/30 text-amber-50 rounded-tl-sm italic shadow-amber-900/20"
                                            : "bg-neutral-800 text-neutral-100 rounded-tl-sm"
                                )}>
                                    {renderMessageContent(msg.content)}
                                </div>
                            </div>
                        </div>
                    );
                })}
                <div ref={bottomRef} />
            </div>

            {/* Input Area */}
            <div className="p-4 bg-neutral-900/80 border-t border-neutral-800 relative">

                {/* Command Suggestions Popup */}
                <CommandSuggestions
                    inputValue={inputValue}
                    onSelect={(selectedText, isArgument) => {
                        if (isArgument) {
                            // If user selected an argument (like "Goblin 1"), replace the partial argument
                            const parts = inputValue.trimStart().split(' ');
                            const baseCmd = parts[0]; // e.g., "@attack"
                            // If baseCmd already had a space typed after it, keep it and append the selected text.
                            // If they selected a multi-word target, best to wrap it in quotes? Only if your backend handles quotes.
                            // The backend uses `target_name = action_params.get("raw_text")` basically.
                            // Let's just append the exact name.
                            setInputValue(`${baseCmd} ${selectedText} `);
                        } else {
                            // Selected a base command
                            setInputValue(`@${selectedText} `);
                        }
                    }}
                />

                <div className="relative">
                    <input
                        type="text"
                        value={inputValue}
                        onChange={(e) => setInputValue(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder={isDmTyping ? "The DM is busy narrating..." : "What do you do? (Type @ for commands)"}
                        className={cn(
                            "w-full bg-neutral-950/50 border rounded-xl pl-4 pr-12 py-3 text-white transition-all focus:outline-none focus:ring-1",
                            (isDmTyping && inputValue.startsWith('@'))
                                ? "border-amber-500/50 focus:border-amber-500 focus:ring-amber-500/50 placeholder:text-amber-700/50"
                                : "border-neutral-700 focus:border-purple-500 focus:ring-purple-500/50 placeholder:text-neutral-600"
                        )}
                    />
                    <button
                        onClick={handleSend}
                        disabled={!inputValue.trim() || (isDmTyping && inputValue.startsWith('@'))}
                        className="absolute right-2 top-1/2 -translate-y-1/2 p-2 bg-purple-600 hover:bg-purple-500 text-white rounded-lg transition-colors disabled:opacity-50 disabled:bg-transparent disabled:text-neutral-600"
                    >
                        <Send className="w-4 h-4" />
                    </button>
                </div>
            </div>
        </div>
    );
}

// Helper to render complex message content
const renderMessageContent = (content: any) => {
    try {
        if (!content) return "";
        if (typeof content !== 'string') return String(content);

        // 1. Check if it *might* be JSON
        const trimmed = content.trim();
        if ((trimmed.startsWith('{') && trimmed.endsWith('}')) ||
            (trimmed.startsWith('[') && trimmed.endsWith(']'))) {
            try {
                const parsed = JSON.parse(trimmed);

                // 2. Handle Arrays (Rich Text)
                if (Array.isArray(parsed)) {
                    return parsed.map((block: any, i: number) => {
                        if (typeof block === 'string') return <span key={i}>{block}</span>;
                        if (block?.type === 'text') return <span key={i}>{block.text}</span>;
                        return null;
                    });
                }

                // 3. Handle Single Object
                if (typeof parsed === 'object' && parsed !== null) {
                    return parsed.text || JSON.stringify(parsed);
                }

                return String(parsed);
            } catch {
                // Not JSON, fall through
            }
        }

        // 4. Default: Plain Text
        return content;

    } catch (e) {
        console.error("Error rendering message:", e);
        return String(content);
    }
};
