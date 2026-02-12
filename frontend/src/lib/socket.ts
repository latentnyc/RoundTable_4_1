import { io, Socket } from 'socket.io-client';
import { create } from 'zustand';
import { useAuthStore } from '@/store/authStore';


import { Character } from '@/lib/api';

const SOCKET_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export interface Location {
    id: string;
    name: string;
    description: string;
    source_id?: string;
}

export interface Coordinates {
    q: number;
    r: number;
    s: number;
}

export interface Entity {
    id: string;
    name: string;
    is_ai: boolean;
    hp_current: number;
    hp_max: number;
    ac: number;
    initiative: number;
    speed: number;
    position: Coordinates;
    inventory: string[];
    status_effects: string[];
}

export interface Player extends Entity {
    role: string;
    control_mode: string;
    race: string;
    level: number;
    xp: number;
    user_id?: string;
    sheet_data: Record<string, unknown>;
}

export interface Enemy extends Entity {
    type: string;
}

export interface NPC extends Entity {
    role: string;
    data: Record<string, unknown>;
}

export interface LogEntry {
    tick: number;
    actor_id: string;
    action: string;
    target_id?: string;
    result: string;
    timestamp: string;
}

export interface GameState {
    session_id: string;
    turn_index: number;
    phase: 'combat' | 'exploration' | 'social';
    active_entity_id: string | null;
    location: Location;
    party: Character[]; // Mapping Player to Character for frontend ease
    enemies: Enemy[];
    npcs: NPC[];
    combat_log: LogEntry[];
}


interface SocketState {
    socket: Socket | null;
    isConnected: boolean;
    messages: ChatMessage[];
    gameState: GameState | null;
    connect: (campaignId: string, userId: string, characterId?: string) => Promise<void>;
    disconnect: () => void;
    sendMessage: (content: string, senderName?: string, senderId?: string) => void;
    debugLogs: DebugLogItem[];
    clearLogs: () => void;
    clearChat: () => void;
    // Ping / Latency
    lastPing: number | null;
    measurePing: () => Promise<void>;
    // Internal state to track connection promise
    connectingPromise: Promise<void> | null;
    // AI Stats
    aiStats: AIStats;
    setInitialStats: (totalTokens: number, inputTokens: number, outputTokens: number, queryCount: number) => void;
}

export interface ChatMessage {
    sender_id: string;
    sender_name: string;
    content: string;
    timestamp: string;
    is_system?: boolean;
}

export interface DebugLogItem {
    type: 'llm_start' | 'llm_end' | 'tool_start' | 'tool_end';
    content: string;
    agent_name?: string;
    full_content: unknown;
    timestamp: string;
}

export interface AIStats {
    totalTokens: number;
    inputTokens: number;
    outputTokens: number;
    queryCount: number;
    lastRequest?: {
        tokens: number;
        model: string;
        agent: string;
    };
}

export const useSocketStore = create<SocketState>((set, get) => ({
    socket: null,
    isConnected: false,
    messages: [],
    gameState: null,
    debugLogs: [],
    connectingPromise: null,
    lastPing: null,
    aiStats: {
        totalTokens: 0,
        inputTokens: 0,
        outputTokens: 0,
        queryCount: 0
    },

    connect: async (campaignId, userId, characterId) => {
        const { socket, connectingPromise } = get();

        // Use the token directly from the store (source of truth)
        const { token } = useAuthStore.getState();

        // If already connected, check if tokens matched
        if (socket) {
            // @ts-expect-error - auth property exists on socket.io client options
            const currentToken = socket.auth?.token;
            if (socket.connected && currentToken === token) {

                return;
            }

            if (currentToken !== token) {

                socket.disconnect();
                set({ socket: null, isConnected: false });
            } else if (connectingPromise) {

                await connectingPromise;
                return;
            }
        }

        const connectLogic = async () => {
            // Use the token directly from the store (source of truth)
            // This allows us to use dev tokens or handle token refresh via the store
            const { token } = useAuthStore.getState();

            if (!token) {
                console.error("No auth token found, cannot connect to socket.");
                set({ connectingPromise: null });
                return;
            }


            const newSocket = io(SOCKET_URL, {
                // transports: ['polling'], // Default is ['polling', 'websocket']
                auth: { token },
                reconnection: true,
                reconnectionAttempts: 5,
            });

            newSocket.on('connect', () => {

                set({ isConnected: true, connectingPromise: null });

                // Join Campaign Room

                newSocket.emit('join_campaign', {
                    user_id: userId,
                    campaign_id: campaignId,
                    character_id: characterId
                });
            });

            newSocket.on('connect_error', (err) => {
                console.error('Socket connection error:', err);
                set({ connectingPromise: null });
            });

            newSocket.on('disconnect', () => {

                set({ isConnected: false, lastPing: null });
            });

            newSocket.on('chat_message', (msg: ChatMessage) => {

                set((state) => {
                    // Deduplicate messages based on timestamp and content + sender
                    const exists = state.messages.some(m =>
                        m.timestamp === msg.timestamp &&
                        m.content === msg.content &&
                        m.sender_id === msg.sender_id
                    );
                    if (exists) return state;
                    return { messages: [...state.messages, msg] };
                });
            });

            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            newSocket.on('ai_stats', (data: any) => {

                if (data.type === 'usage' || data.type === 'update') {
                    // Usage is incremental (legacy/other providers), Update is absolute (from DB)
                    // If we get an absolute update, use it.
                    if (data.type === 'update' && typeof data.total_tokens === 'number') {
                        set((state) => ({
                            aiStats: {
                                totalTokens: data.total_tokens,
                                inputTokens: data.input_tokens || 0,
                                outputTokens: data.output_tokens || 0,
                                queryCount: data.query_count || (state.aiStats.queryCount + 1),
                                lastRequest: data.last_request ? {
                                    tokens: data.last_request.tokens,
                                    model: data.last_request.model,
                                    agent: data.last_request.agent
                                } : state.aiStats.lastRequest
                            }
                        }));
                    } else if (data.type === 'usage') {
                        // Fallback for incremental
                        set((state) => ({
                            aiStats: {
                                totalTokens: state.aiStats.totalTokens + (data.total_tokens || 0),
                                inputTokens: state.aiStats.inputTokens + (data.input_tokens || 0),
                                outputTokens: state.aiStats.outputTokens + (data.output_tokens || 0),
                                queryCount: state.aiStats.queryCount + 1,
                                lastRequest: {
                                    tokens: data.total_tokens || 0,
                                    model: data.model || 'unknown',
                                    agent: data.agent_name || 'unknown'
                                }
                            }
                        }));
                    }
                }
            });

            newSocket.on('system_message', (msg: { content: string }) => {

                set((state) => {
                    const newMsg = {
                        sender_id: 'system',
                        sender_name: 'System',
                        content: msg.content,
                        timestamp: new Date().toLocaleTimeString(),
                        is_system: true
                    };
                    const exists = state.messages.some(m =>
                        m.content === newMsg.content &&
                        m.is_system
                    );
                    if (exists) return state;
                    return { messages: [...state.messages, newMsg] };
                });
            });

            newSocket.on('game_state_update', (state: GameState) => {

                set({ gameState: state });
            });

            newSocket.on('debug_log', (log: DebugLogItem) => {

                set((state) => ({ debugLogs: [...state.debugLogs, log] }));
            });

            newSocket.on('chat_history', (history: ChatMessage[]) => {

                set({ messages: history });
            });

            newSocket.on('chat_cleared', () => {

                set({ messages: [] });
            });

            newSocket.on('debug_logs_cleared', () => {

                set({ debugLogs: [] });
            });

            set({ socket: newSocket });
        };

        const promise = connectLogic().catch(err => {
            console.error("Fatal socket error:", err);
            set({ connectingPromise: null });
        });

        set({ connectingPromise: promise });
        await promise;
    },

    disconnect: () => {
        const { socket } = get();
        if (socket) {

            socket.disconnect();
            set({ socket: null, isConnected: false, lastPing: null });
        }
    },

    sendMessage: (content, senderName, senderId) => {
        const { socket } = get();
        if (socket) {

            const apiKey = localStorage.getItem('gemini_api_key');
            const model = localStorage.getItem('selected_model');

            socket.emit('chat_message', {
                content,
                sender_name: senderName,
                sender_id: senderId,
                api_key: apiKey,
                model_name: model
            });
        } else {
            console.warn('Cannot send message: Socket not connected');
        }
    },

    clearLogs: () => {
        const { socket } = get();
        if (socket) {

            socket.emit('clear_debug_logs');
            // Optimistically clear local? No, wait for server event 'debug_logs_cleared'
            // But for responsiveness we might want to?
            // The requirement says "trigger backend call". The server will broadcast.
        }
    },

    clearChat: () => {
        const { socket } = get();
        if (socket) {

            socket.emit('clear_chat');
        }
    },

    measurePing: async () => {
        const { socket, isConnected } = get();
        if (!socket || !isConnected) {
            set({ lastPing: null });
            return;
        }

        const start = Date.now();
        // Use test_connection as ping
        try {
            // We wrap emit in a promise
            await new Promise<void>((resolve) => {
                socket.emit('test_connection', {}, () => {
                    const latency = Date.now() - start;
                    set({ lastPing: latency });
                    resolve();
                });

                // Timeout fallback?
                setTimeout(() => resolve(), 2000);
            });
        } catch (e) {
            console.error("Ping failed", e);
        }
    },

    setInitialStats: (totalTokens, inputTokens, outputTokens, queryCount) => {
        set((state) => ({
            aiStats: {
                ...state.aiStats,
                totalTokens,
                inputTokens,
                outputTokens,
                queryCount
            }
        }));
    }
}));
