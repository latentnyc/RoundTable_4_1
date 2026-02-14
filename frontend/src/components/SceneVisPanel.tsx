import { useState, useEffect, useRef } from 'react';
import { Loader2, Image as ImageIcon } from 'lucide-react';
import { campaignApi } from '@/lib/api';

interface SceneVisPanelProps {
    campaignId: string;
    locationName?: string;
    description?: string;
}

export default function SceneVisPanel({ campaignId, locationName, description }: SceneVisPanelProps) {
    const [image, setImage] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const lastDescriptionRef = useRef<string | null>(null);

    useEffect(() => {
        const generate = async () => {
            // Avoid re-generating if description is same or empty
            if (!description || description === lastDescriptionRef.current) return;

            lastDescriptionRef.current = description;
            const promptToUse = description;

            setLoading(true);
            setError(null);
            // Don't clear image immediately to prevent flickering if you want,
            // but for now let's show loading to be clear it's updating.
            setImage(null);

            try {
                const result = await campaignApi.generateImage(campaignId, promptToUse);
                setImage(`data:image/png;base64,${result.image_base64}`);
            } catch (e: any) {
                console.error(e);
                setError("Failed to generate image.");
            } finally {
                setLoading(false);
            }
        };

        generate();
    }, [campaignId, description]);

    return (
        <div className="flex flex-col h-full bg-neutral-900/50 rounded-xl border border-neutral-800 overflow-hidden relative group">
            <div className="absolute top-2 left-2 z-10 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                <h3 className="text-[10px] font-semibold text-neutral-400 uppercase tracking-wider bg-black/60 px-2 py-1 rounded backdrop-blur-sm flex items-center gap-1">
                    <ImageIcon className="w-3 h-3" />
                    Scene Vis
                </h3>
            </div>

            <div className="flex-1 w-full h-full relative flex items-center justify-center bg-black/20">
                {image ? (
                    <img src={image} alt="Scene Visualization" className="w-full h-full object-cover" />
                ) : (
                    <div className="absolute inset-0 flex flex-col items-center justify-center text-neutral-600 space-y-2 select-none">
                        {loading ? (
                            <>
                                <Loader2 className="w-6 h-6 animate-spin text-indigo-500/50" />
                                <span className="text-xs uppercase tracking-widest opacity-50">Sketching...</span>
                            </>
                        ) : (
                            <>
                                <ImageIcon className="w-8 h-8 opacity-20" />
                                <span className="text-xs uppercase tracking-widest opacity-40">Awaiting Scene</span>
                            </>
                        )}
                    </div>
                )}
            </div>

            {error && <div className="absolute top-2 right-2 text-red-400 text-xs bg-black/80 px-2 py-1 rounded">{error}</div>}
        </div>
    );
}
