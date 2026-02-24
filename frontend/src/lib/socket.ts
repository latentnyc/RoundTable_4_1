import { create } from 'zustand';

// Socket Context now handles connectivity.
// This Zustand store acts entirely as a reactive data sink.


export interface Interactable {
    id: string;
    name: string;
    type: string;
    state: string;
    locked: boolean;
    key_id: string;
    position?: Coordinates;
    target_location_id?: string;
}

export interface Location {
    id: string;
    name: string;
    description: string;
    source_id?: string;
    walkable_hexes?: Coordinates[];
    interactables?: Interactable[];
    party_locations?: { party_id: string, position: Coordinates }[];
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

// Reconciling with API Character
export interface Player extends Entity {
    role: string;
    control_mode: string; // 'human' | 'ai' | 'disabled'
    race: string;
    level: number;
    xp: number;
    user_id?: string;
    campaign_id?: string;
    backstory?: string;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    sheet_data: Record<string, any>;
}

export interface Enemy extends Entity {
    type: string;
    identified?: boolean;
    data?: Record<string, any>;
}

export interface NPC extends Entity {
    role: string;
    data: Record<string, unknown>;
    identified?: boolean;
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
    discovered_locations?: Location[];
    party: Player[]; // Mapping Player to Character for frontend ease
    enemies: Enemy[];
    npcs: NPC[];
    turn_order: string[];
    combat_log: LogEntry[];
    vessels?: any[];
}


interface SocketState {
    isConnected: boolean;
    connectionError: string | null;
    messages: ChatMessage[];
    gameState: GameState | null;
    debugLogs: DebugLogItem[];
    lastPing: number | null;
    aiStats: AIStats;
    isTyping: boolean;

    // Setters for context provider
    setConnected: (connected: boolean) => void;
    setConnectionError: (error: string | null) => void;
    setMessages: (messages: ChatMessage[]) => void;
    addMessage: (msg: ChatMessage) => void;
    setGameState: (state: GameState | null) => void;
    setDebugLogs: (logs: DebugLogItem[]) => void;
    addDebugLog: (log: DebugLogItem) => void;
    setPing: (ping: number | null) => void;
    setAiTyping: (isTyping: boolean) => void;
    setAiStats: (stats: AIStats) => void;

    // UI Helpers that don't need socket
    setInitialStats: (totalTokens: number, inputTokens: number, outputTokens: number, queryCount: number, imageCount: number) => void;
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
    imageCount: number;
    lastRequest?: {
        tokens: number;
        model: string;
        agent: string;
    };
    lastImageRequest?: {
        model: string;
    };
}

export const useSocketStore = create<SocketState>((set) => ({
    isConnected: false,
    connectionError: null,
    messages: [],
    gameState: null,
    debugLogs: [],
    lastPing: null,
    aiStats: {
        totalTokens: 0,
        inputTokens: 0,
        outputTokens: 0,
        queryCount: 0,
        imageCount: 0
    },
    isTyping: false,

    setConnected: (connected) => set({ isConnected: connected }),
    setConnectionError: (error) => set({ connectionError: error }),
    setMessages: (messages) => set({ messages }),
    addMessage: (msg: ChatMessage) => set((state) => {
        // Deduplicate messages based on timestamp and content + sender
        const exists = state.messages.some(m =>
            m.timestamp === msg.timestamp &&
            m.content === msg.content &&
            m.sender_id === msg.sender_id
        );
        if (exists) return state;
        return {
            messages: [...state.messages, msg],
            isTyping: false // Failsafe
        };
    }),

    setGameState: (state) => set({ gameState: state }),
    setDebugLogs: (logs) => set({ debugLogs: logs }),
    addDebugLog: (log: DebugLogItem) => set((state) => {
        let typing = state.isTyping;
        if (log.type === 'llm_start') typing = true;
        if (log.type === 'llm_end') typing = false;

        return {
            debugLogs: [...state.debugLogs, log],
            isTyping: typing
        };
    }),
    setPing: (ping) => set({ lastPing: ping }),
    setAiTyping: (isTyping) => set({ isTyping }),

    setAiStats: (data: any) => set((state) => {
        if (data.type === 'update' && typeof data.total_tokens === 'number') {
            return {
                aiStats: {
                    totalTokens: data.total_tokens,
                    inputTokens: data.input_tokens || 0,
                    outputTokens: data.output_tokens || 0,
                    queryCount: data.query_count || (state.aiStats.queryCount + 1),
                    imageCount: data.image_count || state.aiStats.imageCount,
                    lastRequest: data.last_request ? {
                        tokens: data.last_request.tokens,
                        model: data.last_request.model,
                        agent: data.last_request.agent
                    } : state.aiStats.lastRequest,
                    lastImageRequest: data.last_image_request ? {
                        model: data.last_image_request.model
                    } : state.aiStats.lastImageRequest
                }
            };
        } else if (data.type === 'usage') {
            const isImage = data.is_image === true;
            return {
                aiStats: {
                    totalTokens: state.aiStats.totalTokens + (data.total_tokens || 0),
                    inputTokens: state.aiStats.inputTokens + (data.input_tokens || 0),
                    outputTokens: state.aiStats.outputTokens + (data.output_tokens || 0),
                    queryCount: state.aiStats.queryCount + (isImage ? 0 : 1),
                    imageCount: state.aiStats.imageCount + (isImage ? 1 : 0),
                    lastRequest: !isImage ? {
                        tokens: data.total_tokens || 0,
                        model: data.model || 'unknown',
                        agent: data.agent_name || 'unknown'
                    } : state.aiStats.lastRequest,
                    lastImageRequest: isImage ? {
                        model: data.model || 'unknown'
                    } : state.aiStats.lastImageRequest
                }
            };
        }
        return state;
    }),

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
