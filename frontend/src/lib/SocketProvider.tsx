import React, { createContext, useContext, useEffect, useRef, ReactNode } from 'react';
import { io, Socket } from 'socket.io-client';
import { applyPatch } from 'fast-json-patch';
import { useAuthStore } from '../store/authStore';
import { useSocketStore } from './socket';

const SOCKET_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface SocketContextType {
    socket: Socket | null;
    connect: (campaignId: string) => Promise<void>;
    disconnect: () => void;
    isConnected: boolean;
    connectionError: string | null;
}

const SocketContext = createContext<SocketContextType>({
    socket: null,
    connect: async () => { },
    disconnect: () => { },
    isConnected: false,
    connectionError: null,
});

export const useSocketContext = () => useContext(SocketContext);

export const SocketProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
    const socketRef = useRef<Socket | null>(null);
    const [socketVal, setSocketVal] = React.useState<Socket | null>(null);
    const connectPromiseRef = useRef<Promise<void> | null>(null);

    const token = useAuthStore(state => state.token);
    const user = useAuthStore(state => state.user);
    // Extract actions from the Zustand store individually to avoid infinite loops from new object creation in selectors
    const setConnected = useSocketStore(state => state.setConnected);
    const setConnectionError = useSocketStore(state => state.setConnectionError);
    const setGameState = useSocketStore(state => state.setGameState);
    const setMessages = useSocketStore(state => state.setMessages);
    const addMessage = useSocketStore(state => state.addMessage);
    const setPing = useSocketStore(state => state.setPing);
    const setAiTyping = useSocketStore(state => state.setAiTyping);
    const setAiStats = useSocketStore(state => state.setAiStats);
    const addDebugLog = useSocketStore(state => state.addDebugLog);
    const setDebugLogs = useSocketStore(state => state.setDebugLogs);

    const isConnected = useSocketStore(state => state.isConnected);
    const connectionError = useSocketStore(state => state.connectionError);

    const disconnect = () => {
        if (socketRef.current) {
            socketRef.current.disconnect();
            socketRef.current = null;
            setSocketVal(null);
        }
        connectPromiseRef.current = null;
        setConnected(false);
        setGameState(null);
        setMessages([]);
        setAiTyping(false);
    };

    const connect = async (campaignId: string): Promise<void> => {
        if (connectPromiseRef.current) {
            return connectPromiseRef.current;
        }

        if (socketRef.current?.connected) {
            return Promise.resolve();
        }

        connectPromiseRef.current = new Promise((resolve, reject) => {
            try {
                const newSocket = io(SOCKET_URL, {
                    auth: { token },
                    query: { campaignId },
                    transports: ['websocket'],
                    reconnection: true,
                    reconnectionAttempts: 5,
                    reconnectionDelay: 1000,
                });

                socketRef.current = newSocket;
                setSocketVal(newSocket);

                newSocket.on('connect', () => {
                    setConnected(true);
                    setConnectionError(null);

                    if (user?.uid) {
                        newSocket.emit('join_campaign', {
                            user_id: user.uid,
                            campaign_id: campaignId
                        });
                    }

                    // Ping interval
                    const pingInterval = setInterval(() => {
                        const start = Date.now();
                        newSocket.emit('ping', () => {
                            const latency = Date.now() - start;
                            setPing(latency);
                        });
                    }, 5000);

                    newSocket.once('disconnect', () => clearInterval(pingInterval));
                    resolve();
                });

                newSocket.on('connect_error', (error) => {
                    console.error('❌ Socket connection error:', error.message);
                    setConnectionError(error.message);
                    setConnected(false);
                    connectPromiseRef.current = null;
                    reject(error);
                });

                newSocket.on('disconnect', () => {
                    setConnected(false);
                    connectPromiseRef.current = null;
                });

                // Bind State Event Handlers
                newSocket.on('game_state_update', (state) => {
                    useSocketStore.getState().setGameState(state);
                });

                newSocket.on('game_state_patch', (patch) => {
                    const state = useSocketStore.getState().gameState;
                    if (state) {
                        try {
                            // Fourth argument is 'mutateDocument'. We must set it to false so Zustand detects a new object reference.
                            const result = applyPatch(state, patch, false, false);
                            useSocketStore.getState().setGameState(result.newDocument);
                        } catch (e) {
                            console.error("Failed to apply game state patch:", e);
                        }
                    } else {
                        console.warn("Received patch but no base game state exists yet.");
                    }
                });

                newSocket.on('chat_history', (history) => {
                    setMessages(history);
                });

                newSocket.on('chat_message', (msg) => {
                    addMessage(msg);
                });

                newSocket.on('system_message', (msg) => {
                    addMessage({ ...msg, is_system: true, sender_name: 'System' });
                });

                newSocket.on('typing_indicator', ({ is_typing }) => {
                    setAiTyping(is_typing);
                });

                newSocket.on('ai_stats', (stats) => {
                    setAiStats(stats);
                });

                newSocket.on('error', (error) => {
                    console.error('❌ Socket error received:', error);
                    setConnectionError(error.message || 'Unknown socket error');
                });

                newSocket.on('debug_log', (log) => {
                    addDebugLog(log);
                });

                newSocket.on('debug_logs_cleared', () => {
                    setDebugLogs([]);
                });

            } catch (error: any) {
                console.error('❌ Failed to initialize socket:', error);
                setConnectionError(error.message);
                setConnected(false);
                connectPromiseRef.current = null;
                reject(error);
            }
        });

        return connectPromiseRef.current;
    };

    // Cleanup on unmount
    useEffect(() => {
        return () => {
            disconnect();
        };
    }, []);

    return (
        <SocketContext.Provider value={{ socket: socketVal, connect, disconnect, isConnected, connectionError }}>
            {children}
        </SocketContext.Provider>
    );
};
