import axios from 'axios';

// Create axios instance
const api = axios.create({
    baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
    headers: {
        'Content-Type': 'application/json',
    },
    timeout: 10000,
});




let tokenGetter: () => string | null = () => null;

export const setTokenGetter = (getter: () => string | null) => {
    tokenGetter = getter;
};

// Request Interceptor to add Token
api.interceptors.request.use((config) => {
    const token = tokenGetter();
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

// Response Interceptor for Errors
api.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response?.status === 401) {
            // Optional: Logout if 401?
            console.error("Unauthorized API Call");
        }
        return Promise.reject(error);
    }
);

export const authApi = {
    login: async () => {
        const response = await api.post('/auth/login');
        return response.data;
    },
    updateProfile: async (data: Partial<Profile>) => {
        const response = await api.put('/auth/profile', data);
        return response.data;
    }
};

export interface Profile {
    id: string;
    username: string;
    email?: string;
    is_admin?: boolean;
    status: string; // 'active' | 'interested'
    created_at?: string;
}

export const usersApi = {
    list: async (): Promise<Profile[]> => {
        const response = await api.get('/users/');
        return response.data;
    },
    update: async (id: string, data: Partial<Profile>): Promise<Profile> => {
        const response = await api.patch(`/users/${id}`, data);
        return response.data;
    },
    delete: async (id: string): Promise<void> => {
        await api.delete(`/users/${id}`);
    }
};

export interface Character {
    id: string;
    user_id?: string;
    campaign_id?: string;
    name: string;
    role: string; // Class
    level: number;
    race?: string;
    xp?: number;
    backstory?: string;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    sheet_data?: Record<string, any>;
    control_mode?: 'human' | 'ai' | 'disabled';
    is_ai?: boolean;
}

export interface Campaign {
    id: string;
    name: string;
    gm_id: string;
    status: string;
    created_at: string;
    api_key?: string;
    api_key_verified?: boolean;
    api_key_configured?: boolean;
    model?: string;
    system_prompt?: string;
    user_status?: string; // 'active', 'interested', 'banned', or undefined
    user_role?: string; // 'gm', 'player'
    total_input_tokens?: number;
    total_output_tokens?: number;
    query_count?: number;
    template_id?: string;
}

export interface ParticipantCharacter {
    id: string;
    name: string;
    race: string;
    class_name: string;
    level: number;
}

export interface CampaignParticipant {
    id: string;
    username: string;
    role: string;
    status: string;
    joined_at: string;
    characters: ParticipantCharacter[];
}

export const campaignApi = {
    list: async (): Promise<Campaign[]> => {
        const response = await api.get('/campaigns/');
        return response.data;
    },
    get: async (id: string): Promise<Campaign> => {
        const response = await api.get(`/campaigns/${id}`);
        return response.data;
    },
    listTemplates: async (): Promise<CampaignTemplate[]> => {
        const response = await api.get('/campaigns/templates');
        return response.data;
    },
    create: async (data: Partial<Campaign>): Promise<Campaign> => {
        const response = await api.post('/campaigns/', data);
        return response.data;
    },
    update: async (id: string, data: Partial<Campaign>): Promise<Campaign> => {
        const response = await api.patch(`/campaigns/${id}`, data);
        return response.data;
    },
    updateSettings: async (id: string, settings: Partial<Campaign>) => {
        const response = await api.put(`/campaigns/${id}/settings`, settings); // Using PUT for settings
        return response.data;
    },
    testKey: async (apiKey: string): Promise<{ models: string[] }> => {
        const response = await api.post(`/campaigns/test_key`, { api_key: apiKey, provider: "Gemini" });
        return response.data;
    },
    delete: async (id: string): Promise<void> => {
        await api.delete(`/campaigns/${id}`);
    },
    join: async (id: string): Promise<{ status: string, role: string }> => {
        const response = await api.post(`/campaigns/${id}/join`);
        return response.data;
    },
    getParticipants: async (id: string): Promise<CampaignParticipant[]> => {
        const response = await api.get(`/campaigns/${id}/participants`);
        return response.data;
    },
    updateParticipant: async (campaignId: string, userId: string, data: { role?: string, status?: string }) => {
        const response = await api.patch(`/campaigns/${campaignId}/participants/${userId}`, data);
        return response.data;
    }
};

export const characterApi = {
    create: async (data: Partial<Character>): Promise<Character> => {
        const response = await api.post('/characters/', data);
        return response.data;
    },
    list: async (userId: string, campaignId?: string): Promise<Character[]> => {
        const params: Record<string, string> = {};
        if (campaignId) params.campaign_id = campaignId;
        const response = await api.get(`/characters/user/${userId}`, { params });
        return response.data;
    },
    update: async (id: string, data: Partial<Character>): Promise<Character> => {
        const response = await api.patch(`/characters/${id}`, data);
        return response.data;
    },
    delete: async (id: string): Promise<void> => {
        await api.delete(`/characters/${id}`);
    }
};


export interface Item {
    id: string;
    name: string;
    type?: string;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    data: any;
}

export const itemsApi = {
    search: async (query: string): Promise<Item[]> => {
        const response = await api.get(`/items/search`, { params: { q: query } });
        return response.data;
    }
};

export const compendiumApi = {
    searchSpells: async (query: string): Promise<Item[]> => {
        const response = await api.get(`/compendium/spells`, { params: { q: query } });
        return response.data;
    },
    searchFeats: async (query: string): Promise<Item[]> => {
        const response = await api.get(`/compendium/feats`, { params: { q: query } });
        return response.data;
    },
    getRaces: async (): Promise<Item[]> => { // Renamed from searchRaces to match usage
        const response = await api.get(`/compendium/races`);
        return response.data;
    },
    getClasses: async (): Promise<Item[]> => {
        const response = await api.get(`/compendium/classes`);
        return response.data;
    },
    getAlignments: async (): Promise<Item[]> => {
        const response = await api.get(`/compendium/alignments`);
        return response.data;
    },
    getBackgrounds: async (): Promise<Item[]> => {
        const response = await api.get(`/compendium/backgrounds`);
        return response.data;
    }
};

export interface DatasetInfo {
    id: string;
    name: string;
    description: string;
    is_loaded: boolean;
}

export interface GameTemplate {
    filename: string;
    name: string;
    description: string;
    system_prompt: string;
}

export interface CampaignTemplate {
    id: string;
    name: string;
    description: string;
    genre: string;
}

export const settingsApi = {
    testKey: async (apiKey: string): Promise<{ models: string[] }> => {
        const response = await api.post(`/api/settings/test-key`, { api_key: apiKey, provider: "Gemini" });
        return response.data;
    },
    getDatasets: async (): Promise<DatasetInfo[]> => {
        const response = await api.get('/api/settings/datasets');
        return response.data;
    },
    loadDataset: async (id: string): Promise<void> => {
        const response = await api.post(`/api/settings/datasets/${id}/load`);
        return response.data;
    },
    getGameTemplates: async (): Promise<GameTemplate[]> => {
        const response = await api.get('/api/settings/game_templates');
        return response.data;
    }
};

export default api;
