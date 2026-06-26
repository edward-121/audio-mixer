import type { AudioStem } from '../types';

// The local development endpoint where your FastAPI / Flask server runs
const BACKEND_URL = 'http://localhost:8000';

export const ApiService = {
  /**
   * 1. Fetches all isolated track elements currently cached inside your backend's storage
   */
  async getAvailableStems(): Promise<AudioStem[]> {
    try {
      const response = await fetch(`${BACKEND_URL}/api/stems`);
      if (!response.ok) throw new Error('Failed to synchronize stems pool.');
      
      const data = await response.json();
      
      // Map incoming database items to match our TypeScript timeline UI attributes
      return data.map((item: any) => ({
        id: item.id,
        songName: item.song_name,
        stemType: item.stem_type, // 'vocals', 'drums', 'bass', 'other'
        duration: item.duration_seconds,
        fileUrl: `${BACKEND_URL}/stems/${item.filename}`, // Serves the direct audio stream link
        color: this.getStemColor(item.stem_type)
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
      const response = await fetch(`${BACKEND_URL}/api/mix`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ clips })
      });
      
      if (!response.ok) throw new Error('Backend failed to render the timeline array matrix.');
      return await response.json();
    } catch (error) {
      console.error("API Error compiling master mashup:", error);
      return { success: false };
    }
  },

  // Helper mapping UI themes to specific musical bands
  getStemColor(type: string): string {
    switch(type) {
      case 'vocals': return 'bg-pink-500/80 border-pink-400';
      case 'drums': return 'bg-cyan-500/80 border-cyan-400';
      case 'bass': return 'bg-emerald-500/80 border-emerald-400';
      default: return 'bg-purple-500/80 border-purple-400';
    }
  }
};