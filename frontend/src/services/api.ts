import type { AudioStem } from '../types';

// In production, use the Render backend URL unless Vercel provides a different override.
const BACKEND_URL = import.meta.env.VITE_API_BASE_URL || (import.meta.env.PROD ? 'https://audio-mixer-g5ha.onrender.com' : 'http://localhost:8000');

const buildUrl = (path: string) => {
    if (!path) return BACKEND_URL || '/';
    if (/^https?:\/\//.test(path)) return path;

    const base = BACKEND_URL || '';
    if (!base) return path.startsWith('/') ? path : `/${path}`;

    return `${base}${path.startsWith('/') ? '' : '/'}${path}`;
};

export const ApiService = {
    /**
     * 1. Fetches all isolated track elements currently cached inside your backend's storage
     */
    async getAvailableStems(): Promise<AudioStem[]> {
        try {
            const response = await fetch(buildUrl('/api/stems'));
            if (!response.ok) throw new Error('Failed to synchronize stems pool.');

            const data = await response.json();

            // Map incoming database items to match our TypeScript timeline UI attributes
            return data.map((item: any) => ({
                id: item.id,
                songName: item.song_name,
                stemType: item.stem_type,
                duration: item.duration_seconds,
                fileUrl: buildUrl(`/stems/${item.filename}`),
                color: this.getStemColor(item.stem_type),
                bpm: Math.round(item.bpm), // 🚀 Map BPM safely
                key: item.key,            // 🚀 Map Key safely
                onsetOffsetSeconds: item.onset_offset_seconds ?? 0
            }));
        } catch (error) {
            console.error("API Error fetching isolated audio pieces:", error);
            return [];
        }
    },

    /**
     * 2. Sends the exact layout configuration layout back to Python to cook up the final WAV mix
     */
    async renderMashupMatrix(clips: any[]): Promise<{ success: boolean; downloadUrl?: string }> {
        try {
            const response = await fetch(buildUrl('/api/mix'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ clips })
            });

            if (!response.ok) throw new Error('Backend failed to render the timeline array matrix.');
            const data = await response.json();
            return {
                ...data,
                downloadUrl: data.downloadUrl ? buildUrl(data.downloadUrl) : undefined
            };
        } catch (error) {
            console.error("API Error compiling master mashup:", error);
            return { success: false };
        }
    },

    // Helper mapping UI themes to specific musical bands
    getStemColor(type: string): string {
        switch (type) {
            case 'vocals': return 'bg-pink-500/80 border-pink-400';
            case 'drums': return 'bg-cyan-500/80 border-cyan-400';
            case 'bass': return 'bg-emerald-500/80 border-emerald-400';
            default: return 'bg-purple-500/80 border-purple-400';
        }
    },

    async uploadAudioStem(file: File): Promise<{ success: boolean; message: string }> {
        const formData = new FormData();
        formData.append("file", file);

        const response = await fetch(buildUrl('/api/upload'), {
            method: "POST",
            body: formData, // FormData automatically handles multipart headers correctly
        });

        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.detail || "Failed to process audio stem upload.");
        }

        return response.json();
    },

    async uploadFullSong(file: File): Promise<{ success: boolean; message: string }> {
        const formData = new FormData();
        formData.append("file", file);

        const response = await fetch(buildUrl('/api/upload/song'), {
            method: "POST",
            body: formData,
        });

        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.detail || "Failed to split audio into stems.");
        }

        return response.json();
    },

    async deleteCachedStems(songName?: string): Promise<{ success: boolean; message: string }> {
        const params = songName ? `?songName=${encodeURIComponent(songName)}` : '';
        const response = await fetch(buildUrl(`/api/stems${params}`), {
            method: 'DELETE',
        });

        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.detail || 'Failed to delete cached stems.');
        }

        return response.json();
    }
};