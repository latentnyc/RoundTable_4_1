
import { useEffect, useState, useRef } from 'react';
import { useSocketStore } from '@/lib/socket';
import { useAuthStore } from '@/store/authStore';
import { Send, User, Bot, Sparkles } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Character } from '@/lib/api';

interface ChatInterfaceProps {
    campaignId: string;
    characterId?: string;
}

export default function ChatInterface({ characterId }: ChatInterfaceProps) {
    const { profile } = useAuthStore();
    const { messages, sendMessage, clearChat } = useSocketStore();
    const [inputValue, setInputValue] = useState('');
    const [showClearConfirm, setShowClearConfirm] = useState(false);
    const bottomRef = useRef<HTMLDivElement>(null);


    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    const { user } = useAuthStore();

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

        sendMessage(inputValue, senderName, senderId);
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
                <h3 className="font-semibold text-neutral-200 flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-purple-400" />
                    Party Chat
                </h3>

                {showClearConfirm ? (
                    <div className="flex items-center gap-2">
                        <span className="text-[10px] text-red-400 font-bold uppercase">Are you sure?</span>
                        <button
                            onClick={() => {
                                clearChat();
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
                        return (
                            <div key={idx} className="flex justify-center my-4">
                                <span className="text-xs text-neutral-500 bg-neutral-800/50 px-3 py-1 rounded-full border border-neutral-800">
                                    {msg.content}
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
                                "flex flex-col max-w-[80%]",
                                isMe ? "items-end" : "items-start"
                            )}>
                                <span className="text-sm text-neutral-500 mb-1 px-1">
                                    {msg.sender_name} <span className="text-xs opacity-50">• {msg.timestamp}</span>
                                </span>
                                <div className={cn(
                                    "px-4 py-2 rounded-2xl text-sm leading-relaxed",
                                    isMe
                                        ? "bg-purple-600 text-white rounded-tr-sm"
                                        : (isDM || isAI)
                                            ? "bg-amber-900/30 border border-amber-800/50 text-amber-100 rounded-tl-sm italic"
                                            : "bg-neutral-800 text-neutral-200 rounded-tl-sm"
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
            <div className="p-4 bg-neutral-900/80 border-t border-neutral-800">
                <div className="relative">
                    <input
                        type="text"
                        value={inputValue}
                        onChange={(e) => setInputValue(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder="What do you do?"
                        className="w-full bg-neutral-950/50 border border-neutral-700 rounded-xl pl-4 pr-12 py-3 text-white focus:border-purple-500 focus:outline-none focus:ring-1 focus:ring-purple-500/50 transition-all placeholder:text-neutral-600"
                    />
                    <button
                        onClick={handleSend}
                        disabled={!inputValue.trim()}
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
        // 1. If it's a string, try to parse it as JSON
        let parsed = content;
        if (typeof content === 'string') {
            try {
                // If it looks like a JSON array/object, parse it
                if (content.trim().startsWith('{') || content.trim().startsWith('[')) {
                    parsed = JSON.parse(content);
                }
            } catch (e) {
                // Not JSON, just plain text
                return content;
            }
        }

        // 2. Handle Arrays (Rich Text)
        if (Array.isArray(parsed)) {
            return parsed.map((block: any, i: number) => {
                if (typeof block === 'string') return <span key={i}>{block}</span>;
                if (block.type === 'text') return <span key={i}>{block.text}</span>;
                return null;
            });
        }

        // 3. Handle Single Object
        if (typeof parsed === 'object' && parsed !== null) {
            if (parsed.text) return parsed.text;
            // Fallback for unknown objects
            return JSON.stringify(parsed);
        }

        // 4. Fallback (Plain Value)
        return String(parsed);

    } catch (e) {
        console.error("Error rendering message:", e);
        return String(content);
    }
};
