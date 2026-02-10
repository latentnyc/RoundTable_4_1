import axios from 'axios';

// Create axios instance
const api = axios.create({
    baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
    headers: {
        'Content-Type': 'application/json',
    },
});

console.log("API URL Configured:", api.defaults.baseURL); // Debugging


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
    updateProfile: async (data: any) => {
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
    name: string;
    role: string; // Class
    level: number;
    race?: string;
    xp?: number;
    backstory?: string;
    sheet_data?: any;
    control_mode?: string;
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
    create: async (data: any): Promise<Campaign> => {
        const response = await api.post('/campaigns/', data);
        return response.data;
    },
    update: async (id: string, data: Partial<Campaign>): Promise<Campaign> => {
        const response = await api.patch(`/campaigns/${id}`, data);
        return response.data;
    },
    updateSettings: async (id: string, settings: any) => {
        const response = await api.put(`/campaigns/${id}/settings`, settings); // Using PUT for settings
        return response.data;
    },
    testKey: async (apiKey: string): Promise<{ models: string[] }> => {
        const response = await api.post(`/campaigns/test_key`, { api_key: apiKey, provider: "Gemini" });
        return response.data;
    },
    delete: async (id: string): Promise<void> => {
        await api.delete(`/campaigns/${id}`);
    }
};

export const characterApi = {
    create: async (data: any): Promise<Character> => {
        const response = await api.post('/characters/', data);
        return response.data;
    },
    list: async (userId: string, campaignId?: string): Promise<Character[]> => {
        const params: any = {};
        if (campaignId) params.campaign_id = campaignId;
        const response = await api.get(`/characters/user/${userId}`, { params });
        return response.data;
    },
    update: async (id: string, data: any): Promise<Character> => {
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
        await api.post(`/api/settings/datasets/${id}/load`);
    }
};

export default api;
