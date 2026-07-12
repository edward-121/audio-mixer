import type { AudioStem } from '../types';

// Use the current Render backend directly in production to avoid CORS issues caused by older hosts.
const BACKEND_URL = import.meta.env.PROD ? 'https://audio-mixer-g5ha.onrender.com' : 'http://localhost:8000';

/**
 * 🆔 Retrieves or generates a unique persistent session ID for this browser.
 * This ensures the user stays locked into their private workspace folder.
 */
function getSessionId(): string {
    let sessionId = localStorage.getItem("studio_session_id");
    if (!sessionId) {
        sessionId = crypto.randomUUID(); // Generates a clean unique string (UUID v4)
        localStorage.setItem("studio_session_id", sessionId);
    }
    return sessionId;
}

const buildUrl = (path: string) => {
    if (!path) return BACKEND_URL || '/';
    if (/^https?:\/\//.test(path)) return path;

    const base = BACKEND_URL || '';
    if (!base) return path.startsWith('/') ? path : `/${path}`;

    return `${base}${path.startsWith('/') ? '' : '/'}${path}`;
};

export const ApiService = {
    /**
     * 🛡️ Helper method to generate unified network request headers.
     * Automatically injects the required X-Session-ID header on every call.
     */
    getHeaders(customHeaders: Record<string, string> = {}): Record<string, string> {
        return {
            "X-Session-ID": getSessionId(),
            ...customHeaders,
        };
    },

    /**
     * 1. Fetches all isolated track elements currently cached inside your backend's storage
     */
    async getAvailableStems(): Promise<AudioStem[]> {
        try {
            const response = await fetch(buildUrl('/api/stems'), {
                method: "GET",
                headers: this.getHeaders() // 🚀 Injected Session Header
            });
            if (!response.ok) throw new Error('Failed to synchronize stems pool.');

            const data = await response.json();
            const sessionId = getSessionId();

            // Map incoming database items to match our TypeScript timeline UI attributes
            return data.map((item: any) => ({
                id: item.id,
                songName: item.song_name,
                stemType: item.stem_type,
                duration: item.duration_seconds,
                // 🚀 FIX: Update the URL route so the audio player drills into your private folder path
                fileUrl: buildUrl(`/stems/${sessionId}/${item.filename}`),
                color: this.getStemColor(item.stem_type),
                bpm: Math.round(item.bpm), 
                key: item.key,            
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
                headers: this.getHeaders({ 'Content-Type': 'application/json' }), // 🚀 Injected Session Header
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
            headers: this.getHeaders(), // 🚀 Injected Session Header
            body: formData, 
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
            headers: this.getHeaders(), // 🚀 Injected Session Header
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
            headers: this.getHeaders(), // 🚀 Injected Session Header
        });

        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.detail || 'Failed to delete cached stems.');
        }

        return response.json();
    }
};