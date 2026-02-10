import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface CampaignState {
    selectedCampaignId: string | null;
    setSelectedCampaignId: (id: string | null) => void;
}

export const useCampaignStore = create<CampaignState>()(
    persist(
        (set) => ({
            selectedCampaignId: null,
            setSelectedCampaignId: (id) => set({ selectedCampaignId: id }),
        }),
        {
            name: 'campaign-storage', // unique name
        }
    )
);
