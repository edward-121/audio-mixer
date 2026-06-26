export interface AudioStem {
  id: string;
  songName: string;
  stemType: 'vocals' | 'drums' | 'bass' | 'other';
  duration: number;
  fileUrl: string;
  color: string;
  bpm: number;       
  key: string;       
}

export interface TimelineClip {
  id: string;
  stem: AudioStem;
  startTime: number;  // Position in seconds on the timeline
  laneIndex: number;  // Horizontal track lane row (0 = Vocals, 1 = Drums, etc.)
}