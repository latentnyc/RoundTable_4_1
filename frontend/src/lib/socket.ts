import { io, Socket } from 'socket.io-client';
import { create } from 'zustand';
import { useAuthStore } from '@/store/authStore';

const SOCKET_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface SocketState {
    socket: Socket | null;
    isConnected: boolean;
    messages: ChatMessage[];
    gameState: any | null; // Placeholder for GameState type
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
    full_content: any;
    timestamp: string;
    agent_name?: string;
}

export const useSocketStore = create<SocketState>((set, get) => ({
    socket: null,
    isConnected: false,
    messages: [],
    gameState: null,
    debugLogs: [],
    connectingPromise: null,
    lastPing: null,

    connect: async (campaignId, userId, characterId) => {
        const { socket, connectingPromise } = get();

        // Use the token directly from the store (source of truth)
        const { token } = useAuthStore.getState();

        // If already connected, check if tokens matched
        if (socket) {
            // @ts-ignore - auth property exists on socket.io client options
            const currentToken = socket.auth?.token;
            if (socket.connected && currentToken === token) {
                console.log('Socket already connected with same token');
                return;
            }

            if (currentToken !== token) {
                console.log('Token changed, recreating socket...');
                socket.disconnect();
                set({ socket: null, isConnected: false });
            } else if (connectingPromise) {
                console.log('Socket connection already in progress, awaiting...');
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

            console.log(`Connecting to socket at ${SOCKET_URL} with token: ${token.substring(0, 10)}...`);
            const newSocket = io(SOCKET_URL, {
                // transports: ['polling'], // Default is ['polling', 'websocket']
                auth: { token },
                reconnection: true,
                reconnectionAttempts: 5,
            });

            newSocket.on('connect', () => {
                console.log('Socket connected:', newSocket.id);
                set({ isConnected: true, connectingPromise: null });

                // Join Campaign Room
                console.log(`Joining campaign: ${campaignId} as user: ${userId} with char: ${characterId}`);
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
                console.log('Socket disconnected');
                set({ isConnected: false, lastPing: null });
            });

            newSocket.on('chat_message', (msg: ChatMessage) => {
                console.log('Received chat message:', msg);
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

            newSocket.on('system_message', (msg: { content: string }) => {
                console.log('Received system message:', msg);
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

            newSocket.on('game_state_update', (state: any) => {
                console.log('Received game state update:', state);
                set({ gameState: state });
            });

            newSocket.on('debug_log', (log: DebugLogItem) => {
                console.log('Received debug log:', log);
                set((state) => ({ debugLogs: [...state.debugLogs, log] }));
            });

            newSocket.on('chat_history', (history: any[]) => {
                console.log('Received chat history:', history);
                set({ messages: history });
            });

            newSocket.on('chat_cleared', () => {
                console.log('Chat cleared by server');
                set({ messages: [] });
            });

            newSocket.on('debug_logs_cleared', () => {
                console.log('Debug logs cleared by server');
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
            console.log('Disconnecting socket...');
            socket.disconnect();
            set({ socket: null, isConnected: false, lastPing: null });
        }
    },

    sendMessage: (content, senderName, senderId) => {
        const { socket } = get();
        if (socket) {
            console.log('Sending message:', content, senderName);
            const apiKey = localStorage.getItem('gemini_api_key');
            const model = localStorage.getItem('selected_model') || 'gemini-2.0-flash';

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
            console.log('Requesting to clear debug logs...');
            socket.emit('clear_debug_logs');
            // Optimistically clear local? No, wait for server event 'debug_logs_cleared'
            // But for responsiveness we might want to? 
            // The requirement says "trigger backend call". The server will broadcast.
        }
    },

    clearChat: () => {
        const { socket } = get();
        if (socket) {
            console.log('Requesting to clear chat...');
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
    }
}));
