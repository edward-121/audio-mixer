export interface AudioStem {
  id: string;
  songName: string;
  stemType: 'vocals' | 'drums' | 'bass' | 'other';
  duration: number; // in seconds
  color: string;
  fileUrl: string; // 🚀 ADD THIS LINE HERE
}

export interface TimelineClip {
  id: string;
  stem: AudioStem;
  startTime: number;  // Position in seconds on the timeline
  laneIndex: number;  // Horizontal track lane row (0 = Vocals, 1 = Drums, etc.)
}