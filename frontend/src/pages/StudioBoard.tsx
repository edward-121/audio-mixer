import React, { useState, useRef, useEffect, useMemo } from 'react';
import type { AudioStem, TimelineClip } from '../types';
import { ApiService } from '../services/api';
import { Play, Square, Layers, Sparkles, Loader2, Trash2, RotateCcw, Plus, Volume2, VolumeOff } from 'lucide-react';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
const DEFAULT_LANES = ['🎤 Vocals', '🥁 Drums', '🎸 Bassline', '🎹 Melodies / Other'];
const PIXELS_PER_SECOND = 30;

type StemType = AudioStem['stemType'];

type GroupedStemSet = {
  songName: string;
  stemsByType: Partial<Record<StemType, AudioStem>>;
  firstStem?: AudioStem;
};

const STEM_BUTTONS: Array<{ key: StemType; label: string; laneIndex: number }> = [
  { key: 'vocals', label: 'Vocals', laneIndex: 0 },
  { key: 'drums', label: 'Drums', laneIndex: 1 },
  { key: 'bass', label: 'Bass', laneIndex: 2 },
  { key: 'other', label: 'Other', laneIndex: 3 },
];

const KEY_OPTIONS = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B', 'Cm', 'Dm', 'Em', 'Fm', 'Gm', 'Am', 'Bm'];

export default function StudioBoard() {
  const [stemsPool, setStemsPool] = useState<AudioStem[]>([]);
  const [clips, setClips] = useState<TimelineClip[]>([]);
  const [lanes, setLanes] = useState<string[]>(DEFAULT_LANES);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [currentTime, setCurrentTime] = useState(0);
  const [isUploading, setIsUploading] = useState(false);
  const [isDraggingPlayhead, setIsDraggingPlayhead] = useState(false);
  const [alignmentMode, setAlignmentMode] = useState<'off' | 'snap' | 'beat'>('off');
  const [dragPreview, setDragPreview] = useState<{ laneIndex: number; startTime: number; clipId: string } | null>(null);
  const [isExportingMashup, setIsExportingMashup] = useState(false);
  const [waveforms, setWaveforms] = useState<Record<string, number[]>>({});

  const timelineRef = useRef<HTMLDivElement>(null);
  const playheadRef = useRef<HTMLDivElement | null>(null);
  const laneRefs = useRef<Array<HTMLDivElement | null>>([]);
  const activeAudioPlayersRef = useRef<{ audio: HTMLAudioElement; timeoutIds: number[] }[]>([]);
  const animationFrameRef = useRef<number | null>(null);
  const startTimeRef = useRef<number>(0);
  const currentTimeRef = useRef<number>(0);
  const trimClipRef = useRef<{
    importedDuration: number;
    id: string;
    mode: 'start' | 'end';
    startX: number;
    originalStartTime: number;
    originalDuration: number;
    originalAudioStartOffset: number;
  } | null>(null);

  // ⚡ HIGH-PERFORMANCE DRAG REFERENCES
  const draggingDataRef = useRef<{
    id: string;
    startX: number;
    startY: number;
    originalStartTime: number;
    originalLaneIndex: number;
    domElement: HTMLElement;
    currentComputedStartTime: number;
    currentLaneIndex: number;
  } | null>(null);

  const groupedStems = useMemo<GroupedStemSet[]>(() => {
    const groups = new Map<string, GroupedStemSet>();

    stemsPool.forEach((stem) => {
      const songKey = stem.songName.trim() || 'Untitled Track';
      const existing = groups.get(songKey);

      if (existing) {
        existing.stemsByType[stem.stemType] = stem;
        if (!existing.firstStem) existing.firstStem = stem;
      } else {
        groups.set(songKey, {
          songName: songKey,
          stemsByType: { [stem.stemType]: stem },
          firstStem: stem,
        });
      }
    });

    return Array.from(groups.values());
  }, [stemsPool]);

  useEffect(() => {
    const eventSource = new EventSource(`${API_BASE_URL}/api/stems/events`);

    eventSource.onmessage = async (event) => {
      if (event.data === "STEMS_UPDATED") {
        console.log("SSE Event received! Refreshing stem metadata...");

        // Call your existing function that fetches stems and sets React state
        const freshStems = await ApiService.getAvailableStems();
        setStemsPool(freshStems);
      }
    };

    eventSource.onerror = (error) => {
      console.error("SSE Connection Error:", error);
      eventSource.close();
    };

    return () => {
      eventSource.close();
    };
  }, []);

  useEffect(() => {
    async function loadRealAudioStems() {
      setIsLoading(true);
      const activeStems = await ApiService.getAvailableStems();
      setStemsPool(activeStems);
      setIsLoading(false);
    }
    loadRealAudioStems();
  }, []);

  // Generate lightweight waveform peak previews for each stem (used in clip thumbnails)
  useEffect(() => {
    if (!stemsPool || stemsPool.length === 0) return;

    const ac = new (window.AudioContext || (window as any).webkitAudioContext)();

    const generatePeaks = async (stem: AudioStem) => {
      try {
        if (waveforms[stem.id]) return; // already generated
        const resp = await fetch(stem.fileUrl);
        const ab = await resp.arrayBuffer();
        const audioBuffer = await ac.decodeAudioData(ab.slice(0));
        const channelData = audioBuffer.getChannelData(0);
        const samples = 96; // number of bars in preview
        const blockSize = Math.floor(channelData.length / samples) || 1;
        const peaks: number[] = [];
        for (let i = 0; i < samples; i++) {
          let start = i * blockSize;
          let end = Math.min(start + blockSize, channelData.length);
          let max = 0;
          for (let j = start; j < end; j++) {
            const v = Math.abs(channelData[j]);
            if (v > max) max = v;
          }
          peaks.push(Number(max.toFixed(3)));
        }
        setWaveforms(prev => ({ ...prev, [stem.id]: peaks }));
      } catch (err) {
        // ignore decode errors
      }
    };

    stemsPool.forEach(s => {
      generatePeaks(s);
    });

    return () => {
      try { ac.close(); } catch { }
    };
  }, [stemsPool]);

  const handleFileDropUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    const targetFile = files[0];
    setIsUploading(true);

    try {
      const result = await ApiService.uploadAudioStem(targetFile);
      if (result.success) {
        // 🚀 RE-FETCH INSTANTLY: This pulls the fresh track straight into the pool!
        const activeStems = await ApiService.getAvailableStems();
        setStemsPool(activeStems);
      }
    } catch (error: any) {
      alert(error.message || "An unexpected error occurred during audio processing.");
    } finally {
      setIsUploading(false);
    }
  };

  useEffect(() => {
    return () => {
      if (animationFrameRef.current) cancelAnimationFrame(animationFrameRef.current);
    };
  }, []);

  const addClipToTimeline = (stem: AudioStem, laneIndex: number) => {
    const newClip: TimelineClip = {
      id: Math.random().toString(),
      stem,
      startTime: 0,
      laneIndex,
      duration: stem.duration,
      keySignature: stem.key,
      audioStartOffset: stem.onsetOffsetSeconds ?? 0,
      muted: false,
    };
    setClips(prev => [...prev, newClip]);
  };

  const removeClipFromTimeline = (clipId: string) => {
    if (isPlaying) handleStopPreview();
    setClips(prev => prev.filter(clip => clip.id !== clipId));
  };

  const toggleMute = (clipId: string) => {
    setClips(prev => prev.map(c => c.id === clipId ? { ...c, muted: !c.muted } : c));
  };

  const handleAddNewCustomLane = () => {
    const laneName = prompt("Enter a custom name for your new mixer track row lane:", `🎛️ Track Layer ${lanes.length + 1}`);
    if (laneName && laneName.trim() !== "") {
      setLanes([...lanes, laneName.trim()]);
    }
  };

  const clearTimelineBoard = () => {
    if (isPlaying) handleStopPreview();
    if (window.confirm("Are you sure you want to clear all tracks from the mixing board?")) {
      setClips([]);
      setLanes(DEFAULT_LANES);
    }
  };

  const handleRemoveLane = (laneIndex: number) => {
    if (window.confirm("Remove this timeline lane and its clips?")) {
      setLanes(prev => prev.filter((_, idx) => idx !== laneIndex));
      setClips(prev => prev
        .filter(clip => clip.laneIndex !== laneIndex)
        .map(clip => clip.laneIndex > laneIndex ? { ...clip, laneIndex: clip.laneIndex - 1 } : clip));
    }
  };

  const handleDeleteStemGroup = async (songName: string) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/stems/group/${encodeURIComponent(songName)}`, {
        method: "DELETE",
      });

      if (response.ok) {
        console.log(`Successfully deleted stem group: ${songName}`);

        const updatedStems = await ApiService.getAvailableStems();
        setStemsPool(updatedStems);
      } else {
        console.error("Failed to delete stem group from backend.");
      }
    } catch (error) {
      console.error("Error executing delete:", error);
    }
  };

  const handleClearAllStems = async () => {
    if (!window.confirm("Clear all cached stems from the studio?")) return;

    const result = await ApiService.deleteCachedStems();
    if (result.success) {
      const activeStems = await ApiService.getAvailableStems();
      setStemsPool(activeStems);
      setClips([]);
    }
  };

  const handleKeyChange = (clipId: string, nextKey: string) => {
    setClips(prev => prev.map(clip => clip.id === clipId ? { ...clip, keySignature: nextKey } : clip));
  };

  // --- AUDIO PREVIEW ENGINE ---
  const syncCurrentTime = (nextTime: number) => {
    currentTimeRef.current = nextTime;
    setCurrentTime(nextTime);
    if (playheadRef.current) {
      playheadRef.current.style.transform = `translateX(${nextTime * PIXELS_PER_SECOND}px)`;
    }
  };

  const beatLength = useMemo(() => {
    const allBpms = clips.map((clip) => clip.stem.bpm).filter(Boolean) as number[];
    const averageBpm = allBpms.length ? allBpms.reduce((sum, b) => sum + b, 0) / allBpms.length : 120;
    return averageBpm > 0 ? 60 / averageBpm : 0.5;
  }, [clips]);

  const snapTime = (time: number, audioStartOffset: number = 0) => {
    if (alignmentMode === 'snap') {
      const subdivision = Math.max(beatLength / 4, 0.1);
      const aligned = Math.round((time + audioStartOffset) / subdivision) * subdivision;
      return Number(Math.max(0, aligned - audioStartOffset).toFixed(2));
    }

    if (alignmentMode === 'beat') {
      const aligned = Math.round((time + audioStartOffset) / beatLength) * beatLength;
      return Number(Math.max(0, aligned - audioStartOffset).toFixed(2));
    }

    return Number(time.toFixed(3));
  };

  const downloadBlob = async (blob: Blob, filename: string) => {
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  };

  const updatePlayhead = (timestamp: number) => {
    if (!startTimeRef.current) startTimeRef.current = timestamp;
    const elapsedSeconds = Math.min(240, (timestamp - startTimeRef.current) / 1000);
    syncCurrentTime(elapsedSeconds);

    if (elapsedSeconds < 240) {
      animationFrameRef.current = requestAnimationFrame(updatePlayhead);
    } else {
      handleStopPreview();
    }
  };

  const handleStopPreview = () => {
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = null;
    }
    activeAudioPlayersRef.current.forEach(({ audio, timeoutIds }) => {
      timeoutIds.forEach(clearTimeout);
      audio.pause();
      audio.currentTime = 0;
    });
    activeAudioPlayersRef.current = [];
    setIsPlaying(false);
    startTimeRef.current = 0;
  };

  const handleTogglePreview = () => {
    if (isPlaying) {
      handleStopPreview();
      return;
    }

    const playbackStartTime = currentTimeRef.current;

    setIsPlaying(true);
    startTimeRef.current = performance.now() - playbackStartTime * 1000;
    animationFrameRef.current = requestAnimationFrame(updatePlayhead);

    clips.forEach((clip) => {
      if (clip.muted) return; // respect mute per clip
      const audio = new Audio(clip.stem.fileUrl);
      const clipDurationMs = (clip.duration ?? clip.stem.duration) * 1000;
      const audioStartOffset = clip.audioStartOffset ?? 0;
      const startDelayMs = Math.max(0, (clip.startTime - playbackStartTime) * 1000);
      const playbackOffsetSeconds = Math.max(0, playbackStartTime - clip.startTime);
      const remainingClipDurationMs = Math.max(0, clipDurationMs - playbackOffsetSeconds * 1000);
      const timeoutIds: number[] = [];

      if (remainingClipDurationMs <= 0) return;

      timeoutIds.push(window.setTimeout(() => {
        audio.currentTime = audioStartOffset + playbackOffsetSeconds;
        audio.play().catch(err => console.log("Playback blocked:", err));
      }, startDelayMs));

      timeoutIds.push(window.setTimeout(() => {
        audio.pause();
        audio.currentTime = 0;
      }, startDelayMs + remainingClipDurationMs));

      activeAudioPlayersRef.current.push({ audio, timeoutIds });
    });
  };

  const getLaneIndexFromClientY = (clientY: number) => {
    for (let idx = 0; idx < laneRefs.current.length; idx += 1) {
      const laneElement = laneRefs.current[idx];
      if (!laneElement) continue;
      const rect = laneElement.getBoundingClientRect();
      if (clientY >= rect.top && clientY <= rect.bottom) {
        return idx;
      }
    }
    return null;
  };

  const handlePointerDown = (e: React.PointerEvent, clip: TimelineClip) => {
    if (isPlaying) handleStopPreview();
    e.stopPropagation();

    const targetElement = e.currentTarget as HTMLElement;
    targetElement.setPointerCapture(e.pointerId);

    draggingDataRef.current = {
      id: clip.id,
      startX: e.clientX,
      startY: e.clientY,
      originalStartTime: clip.startTime,
      originalLaneIndex: clip.laneIndex,
      domElement: targetElement,
      currentComputedStartTime: clip.startTime,
      currentLaneIndex: clip.laneIndex,
    };
  };

  const handlePointerMove = (e: React.PointerEvent) => {
    if (!draggingDataRef.current) return;
    e.preventDefault();

    const data = draggingDataRef.current;
    const deltaX = e.clientX - data.startX;
    const deltaSeconds = deltaX / PIXELS_PER_SECOND;
    const newStartTime = Math.max(0, data.originalStartTime + deltaSeconds);
    const clip = clips.find((c) => c.id === data.id);
    const audioOffset = clip?.audioStartOffset ?? 0;
    const snappedStartTime = snapTime(newStartTime, audioOffset);
    const laneIndex = getLaneIndexFromClientY(e.clientY);

    data.currentComputedStartTime = snappedStartTime;
    data.currentLaneIndex = laneIndex ?? data.originalLaneIndex;

    data.domElement.style.transform = `translateX(${deltaX}px)`;
    setDragPreview({ laneIndex: data.currentLaneIndex, startTime: snappedStartTime, clipId: data.id });

    const labelNode = data.domElement.querySelector('.clip-time-label');
    if (labelNode) {
      labelNode.textContent = `${newStartTime.toFixed(1)}s`;
    }
  };

  const handlePointerUp = (e: React.PointerEvent) => {
    if (!draggingDataRef.current) return;
    const data = draggingDataRef.current;

    try {
      (e.currentTarget as HTMLElement).releasePointerCapture(e.pointerId);
    } catch {
      // ignore pointer capture release issues
    }

    const finalTime = data.currentComputedStartTime;
    const finalLaneIndex = data.currentLaneIndex;

    data.domElement.style.transform = 'none';
    setDragPreview(null);

    setClips(prev => prev.map(c => c.id === data.id ? { ...c, startTime: finalTime, laneIndex: finalLaneIndex } : c));

    draggingDataRef.current = null;
  };

  const handleClipTrimPointerDown = (e: React.PointerEvent, clip: TimelineClip, mode: 'start' | 'end') => {
    e.stopPropagation();
    e.preventDefault();
    trimClipRef.current = {
      id: clip.id,
      mode,
      startX: e.clientX,
      originalStartTime: clip.startTime,
      originalDuration: clip.duration ?? clip.stem.duration,
      importedDuration: clip.stem.duration,
      originalAudioStartOffset: clip.audioStartOffset ?? 0,
    };
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
  };

  const handleClipTrimPointerMove = (e: React.PointerEvent) => {
    if (!trimClipRef.current) return;
    const deltaSeconds = (e.clientX - trimClipRef.current.startX) / PIXELS_PER_SECOND;

    setClips(prev => prev.map((clip) => {
      if (clip.id !== trimClipRef.current?.id) return clip;

      const importedDuration = trimClipRef.current.importedDuration;
      const origOffset = trimClipRef.current.originalAudioStartOffset;
      const origStart = trimClipRef.current.originalStartTime;
      const origDuration = trimClipRef.current.originalDuration;

      if (trimClipRef.current?.mode === 'start') {
        const maxAllowedOffset = origOffset + origDuration - 0.5;
        const nextOffset = Math.min(Math.max(origOffset + deltaSeconds, 0), maxAllowedOffset);

        const realDelta = nextOffset - origOffset;
        const nextStartTime = origStart + realDelta;
        const nextDuration = origDuration - realDelta;

        return {
          ...clip,
          startTime: Number(nextStartTime.toFixed(2)),
          audioStartOffset: Number(nextOffset.toFixed(2)),
          duration: Number(nextDuration.toFixed(2))
        };
      }

      const maxAllowedDuration = importedDuration - origOffset;
      const nextDuration = Math.max(0.5, Math.min(maxAllowedDuration, origDuration + deltaSeconds));

      return {
        ...clip,
        duration: Number(nextDuration.toFixed(2))
      };
    }));
  };

  const handleClipTrimPointerUp = () => {
    trimClipRef.current = null;
  };

  const handlePlayheadPointerDown = (e: React.PointerEvent) => {
    e.stopPropagation();
    e.currentTarget.setPointerCapture(e.pointerId);
    setIsDraggingPlayhead(true);
    if (isPlaying) handleStopPreview();
    updatePlayheadFromClientX(e.clientX);
  };

  const handlePlayheadPointerMove = (e: React.PointerEvent) => {
    if (!isDraggingPlayhead) return;
    updatePlayheadFromClientX(e.clientX);
  };

  const handlePlayheadPointerUp = (e: React.PointerEvent) => {
    if (!isDraggingPlayhead) return;
    e.stopPropagation();
    setIsDraggingPlayhead(false);
    updatePlayheadFromClientX(e.clientX);
  };

  const updatePlayheadFromClientX = (clientX: number) => {
    const rect = timelineRef.current?.getBoundingClientRect();
    if (!rect) return;

    const relativeX = clientX - rect.left - 176;
    const nextTime = Math.max(0, Math.min(240, relativeX / PIXELS_PER_SECOND));
    syncCurrentTime(nextTime);
    startTimeRef.current = performance.now() - nextTime * 1000;
  };

  const handleRenderMasterMix = async () => {
    if (clips.length === 0) return alert("Add some clips to your timeline grid layout first!");

    const layoutMatrix = clips.map(c => ({
      filename: c.stem.fileUrl.split('/').pop(),
      stem_type: c.stem.stemType,
      start_offset_seconds: Number(c.startTime.toFixed(2)),
      audio_start_offset_seconds: Number((c.audioStartOffset ?? 0).toFixed(3)),
      duration_seconds: Number((c.duration ?? c.stem.duration).toFixed(2)),
      key_signature: c.keySignature ?? c.stem.key,
    }));

    setIsExportingMashup(true);
    try {
      const result = await ApiService.renderMashupMatrix(layoutMatrix);
      if (!result.success || !result.downloadUrl) {
        throw new Error('Mashup render failed. Please try again.');
      }

      const downloadResponse = await fetch(result.downloadUrl);
      if (!downloadResponse.ok) {
        throw new Error('Unable to download the rendered master mashup.');
      }

      const blob = await downloadResponse.blob();
      const filename = result.downloadUrl.split('/').pop() ?? 'master_mashup_mix.wav';
      await downloadBlob(blob, filename);
      alert('Mashup render complete! Your browser save dialog should now let you choose a folder.');
    } catch (error: any) {
      alert(error?.message || 'Failed to render and download master mix.');
    } finally {
      setIsExportingMashup(false);
    }
  };

  const formatTimeLabel = (totalSeconds: number) => {
    const mins = Math.floor(totalSeconds / 60);
    const secs = Math.floor(totalSeconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const smartMatchKey = useMemo(() => {
    const keyValues = clips
      .map((clip) => clip.keySignature ?? clip.stem.key)
      .filter(Boolean) as string[];

    if (keyValues.length === 0) {
      const poolKeys = stemsPool
        .map((stem) => stem.key)
        .filter(Boolean) as string[];
      if (poolKeys.length === 0) return '—';
      return poolKeys[0];
    }

    const frequencyMap = keyValues.reduce<Record<string, number>>((acc, key) => {
      acc[key] = (acc[key] ?? 0) + 1;
      return acc;
    }, {});

    return Object.entries(frequencyMap).sort((a, b) => b[1] - a[1])[0][0];
  }, [clips, stemsPool]);

  return (
    <div className="flex flex-col h-full w-full bg-neutral-950 text-white select-none">
      <header className="flex items-center justify-between px-6 py-4 bg-neutral-900 border-b border-neutral-800">
        <div className="flex items-center gap-2">
          <Layers className="text-purple-500 w-6 h-6" />
          <h1 className="text-lg font-bold tracking-tight">Audio Mixer Studio</h1>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 text-xs font-mono bg-neutral-900 border border-neutral-800 px-3 py-1.5 rounded text-neutral-400">
            <span className="text-[10px] uppercase font-bold tracking-wider text-neutral-500 mr-1">Project Target:</span>
            <span className="text-purple-400 font-bold">
              {clips.length > 0
                ? (clips.reduce((sum, c) => sum + c.stem.bpm, 0) / clips.length).toFixed(1)
                : "---"}{" "}
              BPM
            </span>
            <span className="text-neutral-600">|</span>
            <span className="text-emerald-400 font-bold">{smartMatchKey}</span>
          </div>

          <span className="text-xs font-mono text-neutral-400 bg-neutral-950 px-3 py-1.5 rounded border border-neutral-800">
            Playhead: {currentTime.toFixed(2)}s
          </span>

          <button
            onClick={handleTogglePreview}
            className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm transition font-medium border ${isPlaying ? 'bg-red-950/40 border-red-800 text-red-400 hover:bg-red-900/60' : 'bg-neutral-800 border-neutral-700 hover:bg-neutral-700 text-white'
              }`}
          >
            {isPlaying ? (
              <> <Square className="w-4 h-4 fill-red-400" /> Stop Preview </>
            ) : (
              <> <Play className="w-4 h-4 fill-white" /> Preview Layout </>
            )}
          </button>

          <div className="flex items-center gap-2 rounded-xl border border-neutral-800 bg-neutral-900/80 px-2 py-1 text-[11px] text-neutral-300">
            <span className="uppercase tracking-[0.24em] text-neutral-500">Align</span>
            {(['off', 'snap', 'beat'] as const).map((mode) => (
              <button
                key={mode}
                onClick={() => setAlignmentMode(mode)}
                className={`rounded-full px-3 py-1 transition ${alignmentMode === mode ? 'bg-purple-600 text-white' : 'bg-neutral-800 text-neutral-400 hover:bg-neutral-700'}`}
              >
                {mode === 'off' ? 'Off' : mode === 'snap' ? 'Auto Snap' : 'Beat Align'}
              </button>
            ))}
          </div>

          <button
            onClick={clearTimelineBoard}
            className="flex items-center gap-2 bg-neutral-800 hover:bg-neutral-700 border border-neutral-700 px-3 py-2 rounded-md text-sm text-neutral-300 font-medium transition"
          >
            <RotateCcw className="w-4 h-4" /> Reset Board
          </button>

          <button
            onClick={handleRenderMasterMix}
            disabled={isExportingMashup}
            className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium shadow-lg transition ${isExportingMashup ? 'bg-purple-700/50 text-neutral-200 cursor-not-allowed' : 'bg-purple-600 hover:bg-purple-700 text-white'}`}
          >
            <Sparkles className="w-4 h-4" /> {isExportingMashup ? 'Exporting...' : 'Render Master Mashup'}
          </button>
        </div>
      </header>

      <main className="flex flex-1 overflow-hidden">
        <aside className="w-72 bg-neutral-900/50 p-4 border-r border-neutral-900 flex flex-col gap-4">
          <div className="flex items-center justify-between gap-2">
            <div>
              <h3 className="text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-2">Available Stems</h3>
              <p className="text-xs text-neutral-500 mb-4">Click a track stem below to drop it onto its designated mixing row lane.</p>
            </div>
            <button
              onClick={handleClearAllStems}
              className="rounded border border-neutral-800 px-2 py-1 text-[10px] uppercase tracking-wide text-neutral-400 hover:border-red-700 hover:text-red-400"
            >
              Clear
            </button>
          </div>

          <div className="relative border border-dashed border-neutral-800 hover:border-purple-500/50 bg-neutral-950/40 rounded-lg p-4 transition text-center group cursor-pointer">
            <input
              type="file"
              accept=".mp3,.wav,.ogg"
              onChange={handleFileDropUpload}
              disabled={isUploading}
              className="absolute inset-0 opacity-0 cursor-pointer z-10 disabled:cursor-not-allowed"
            />
            {isUploading ? (
              <div className="flex flex-col items-center justify-center gap-1.5 py-1">
                <Loader2 className="w-4 h-4 animate-spin text-purple-500" />
                <span className="text-[11px] text-neutral-400 font-medium">Analyzing audio matrix specs...</span>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center gap-1 py-1">
                <Plus className="w-4 h-4 text-neutral-500 group-hover:text-purple-400 transition" />
                <span className="text-[11px] text-neutral-400 group-hover:text-neutral-200 font-medium transition">
                  Import New Audio Stem Track
                </span>
                <span className="text-[9px] text-neutral-600 font-mono uppercase tracking-tight">
                  Supports: WAV, MP3, OGG
                </span>
              </div>
            )}
          </div>

          <hr className="border-neutral-900 my-1" />

          {isLoading ? (
            <div className="flex-1 flex flex-col items-center justify-center text-neutral-500 gap-2">
              <Loader2 className="w-6 h-6 animate-spin text-purple-500" />
              <span className="text-xs">Connecting to local storage...</span>
            </div>
          ) : (
            <div className="flex flex-col gap-2 overflow-y-auto pr-1">
              {groupedStems.length === 0 ? (
                <p className="text-xs text-neutral-600 text-center py-8">
                  No stems discovered in cache. Head to the Upload center to drop a song track!
                </p>
              ) : (
                groupedStems.map((group) => {
                  const primaryStem = group.firstStem;

                  return (
                    <div key={group.songName} className="p-3 bg-neutral-900 border border-neutral-800 rounded-lg flex flex-col gap-2">
                      <div className="flex justify-between items-start">
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center justify-between gap-2">
                            <h4 className="font-medium text-sm truncate pr-1">{group.songName}</h4>

                            <div className="flex items-center gap-2 flex-shrink-0">
                              {primaryStem && (
                                <span className="text-xs text-neutral-500 font-mono">
                                  {formatTimeLabel(primaryStem.duration)}
                                </span>
                              )}
                              <button
                                onClick={() => handleDeleteStemGroup(group.songName)}
                                className="text-neutral-500 hover:text-red-400 transition"
                                title="Delete cached stem group"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                            </div>
                          </div>

                          <div className="flex items-center gap-2 mt-0.5">
                            <span className="text-[10px] uppercase font-mono text-neutral-400">multi-stem</span>
                            {primaryStem && (
                              <>
                                <span className="text-[10px] font-mono text-purple-400 bg-purple-950/30 px-1 rounded border border-purple-900/30">
                                  {primaryStem.bpm} BPM
                                </span>
                                <span className="text-[10px] font-mono text-emerald-400 bg-emerald-950/30 px-1 rounded border border-emerald-900/30">
                                  {primaryStem.key}
                                </span>
                              </>
                            )}
                          </div>
                        </div>
                      </div>

                      <div className="grid grid-cols-2 gap-1">
                        {STEM_BUTTONS.map(({ key, label, laneIndex }) => {
                          const stem = group.stemsByType[key];
                          if (!stem) return null;

                          return (
                            <button
                              key={key}
                              onClick={() => addClipToTimeline(stem, laneIndex)}
                              className="text-[10px] bg-neutral-800 hover:bg-purple-950/60 text-neutral-300 py-1 px-1 rounded border border-neutral-700 truncate font-medium"
                            >
                              + {label}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          )}
        </aside>

        <section className="flex-1 bg-neutral-950 overflow-x-auto overflow-y-auto p-6 relative" ref={timelineRef}>
          <div className="relative flex flex-col min-h-full pb-16" style={{ width: '7200px' }}>
            <div className="flex border-b border-neutral-900 pb-2 mb-4 font-mono text-xs text-neutral-500 relative h-6 ml-44">
              {[0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150, 160, 170, 180, 200, 220, 240].map(sec => (
                <span key={sec} className="absolute" style={{ left: `${sec * PIXELS_PER_SECOND}px` }}>
                  {formatTimeLabel(sec)}
                </span>
              ))}
            </div>

            {dragPreview && alignmentMode !== 'off' && (
              <div className="pointer-events-none absolute inset-0 z-20">
                <div
                  className="absolute top-4 h-[calc(100%-3rem)] w-0.5 bg-purple-500/60"
                  style={{ left: `${176 + dragPreview.startTime * PIXELS_PER_SECOND}px` }}
                />
                <div
                  className="absolute left-0 right-0 top-4 flex justify-center"
                  style={{ transform: `translateX(${dragPreview.startTime * PIXELS_PER_SECOND}px)` }}
                >
                  <span className="rounded-full bg-purple-600/90 px-2 py-1 text-[10px] uppercase tracking-[0.24em] text-white shadow-lg">
                    {alignmentMode === 'snap' ? 'Snap Target' : 'Beat Target'} {dragPreview.startTime.toFixed(2)}s
                  </span>
                </div>
              </div>
            )}

            <div
              ref={playheadRef}
              onPointerDown={handlePlayheadPointerDown}
              onPointerMove={handlePlayheadPointerMove}
              onPointerUp={handlePlayheadPointerUp}
              className="absolute top-8 bottom-16 w-[2px] bg-purple-500 shadow-[0_0_12px_#a855f7] z-30 ml-44 cursor-col-resize"
              style={{ transform: `translateX(${currentTime * PIXELS_PER_SECOND}px)` }}
            />

            <div className="flex flex-col gap-4">
              {lanes.map((laneTitle, laneIdx) => (
                <div key={laneIdx} ref={(node) => { laneRefs.current[laneIdx] = node; }} className="h-24 bg-neutral-900/10 border border-neutral-900/40 rounded-xl relative flex items-center shadow-inner">
                  <div className="absolute left-0 top-0 bottom-0 w-44 bg-neutral-900/95 backdrop-blur-md px-4 flex items-center justify-between border-r border-neutral-800 text-xs font-bold tracking-wide text-neutral-300 z-40 shadow-lg">
                    <span className="truncate pr-2">{laneTitle}</span>
                    <button
                      onClick={() => handleRemoveLane(laneIdx)}
                      className="text-neutral-500 hover:text-red-400 transition"
                      title="Delete lane"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>

                  <div className="absolute inset-0 left-44 h-full z-10">
                    {clips
                      .filter(c => c.laneIndex === laneIdx)
                      .map(clip => (
                        <div
                          key={clip.id}
                          onPointerDown={(e) => handlePointerDown(e, clip)}
                          onPointerMove={handlePointerMove}
                          onPointerUp={handlePointerUp}
                          onContextMenu={(e) => {
                            e.preventDefault();
                            removeClipFromTimeline(clip.id);
                          }}
                          className={`absolute h-16 top-4 rounded-lg border p-3 flex flex-col justify-between cursor-grab active:cursor-grabbing shadow-md group select-none touch-none will-change-transform ${clip.stem.color} ${dragPreview?.clipId === clip.id ? 'border-purple-400 ring-2 ring-purple-500/40 shadow-[0_0_0_1px_rgba(168,85,247,0.35)]' : ''}`}
                          style={{
                            left: `${clip.startTime * PIXELS_PER_SECOND}px`,
                            width: `${(clip.duration ?? clip.stem.duration) * PIXELS_PER_SECOND}px`,
                          }}
                        >
                          <div className="flex justify-between items-center gap-2">
                            <div className="flex flex-col min-w-0 flex-1">
                              <span className="font-bold text-xs truncate max-w-[140px]">{clip.stem.songName}</span>
                              <div className="flex items-center gap-1.5 text-[9px] font-mono opacity-70">
                                <span className="clip-time-label">{clip.startTime.toFixed(1)}s</span>
                                <span>•</span>
                                <span>{formatTimeLabel(clip.duration ?? clip.stem.duration)}</span>
                              </div>
                            </div>

                            <div className="flex items-center gap-1 flex-shrink-0">
                              <select
                                value={clip.keySignature ?? clip.stem.key}
                                onPointerDown={(e) => e.stopPropagation()}
                                onChange={(e) => handleKeyChange(clip.id, e.target.value)}
                                className="rounded border border-black/20 bg-black/30 px-1.5 py-0.5 text-[9px] text-neutral-100 outline-none"
                                title="Adjust key"
                              >
                                {KEY_OPTIONS.map(option => (
                                  <option key={option} value={option}>{option}</option>
                                ))}
                              </select>
                              <button
                                onPointerDown={(e) => e.stopPropagation()}
                                onClick={() => toggleMute(clip.id)}
                                className={`p-1 rounded-md bg-black/30 text-neutral-400 hover:bg-neutral-700 hover:text-white transition z-50 cursor-pointer ${clip.muted ? 'bg-yellow-700 text-black' : ''}`}
                                title={clip.muted ? 'Unmute track' : 'Mute track'}
                              >
                                {clip.muted ? <VolumeOff className="w-3.5 h-3.5" /> : <Volume2 className="w-3.5 h-3.5" />}
                              </button>
                              <button
                                onPointerDown={(e) => e.stopPropagation()}
                                onClick={() => removeClipFromTimeline(clip.id)}
                                className="p-1 rounded-md bg-black/30 text-neutral-400 hover:bg-red-600 hover:text-white transition z-50 cursor-pointer"
                                title="Delete track"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                            </div>
                          </div>

                          <div className="w-full h-3 rounded-sm overflow-hidden">
                            {waveforms[clip.stem.id] ? (
                              <div className="flex items-end gap-0.5 h-full">
                                {waveforms[clip.stem.id].map((p, i) => (
                                  <div key={i} style={{ width: `${100 / waveforms[clip.stem.id].length}%`, height: `${Math.max(3, p * 100)}%` }} className={`bg-white/80 ${clip.muted ? 'opacity-30' : ''}`}></div>
                                ))}
                              </div>
                            ) : (
                              <div className="w-full h-3 bg-black/20 rounded-sm flex items-center justify-around opacity-40 pointer-events-none">
                                {[...Array(20)].map((_, i) => (
                                  <div key={i} className="w-[1.5px] bg-white rounded-full" style={{ height: `${Math.abs(Math.sin(i * 0.4)) * 100}%` }}></div>
                                ))}
                              </div>
                            )}
                          </div>

                          <div
                            onPointerDown={(e) => handleClipTrimPointerDown(e, clip, 'start')}
                            onPointerMove={handleClipTrimPointerMove}
                            onPointerUp={handleClipTrimPointerUp}
                            className="absolute left-2 top-1/2 z-50 h-10 w-1 -translate-y-1/2 rounded-full bg-white/60 cursor-ew-resize"
                            title="Trim clip start"
                          />
                          <div
                            onPointerDown={(e) => handleClipTrimPointerDown(e, clip, 'end')}
                            onPointerMove={handleClipTrimPointerMove}
                            onPointerUp={handleClipTrimPointerUp}
                            className="absolute right-2 top-1/2 z-50 h-10 w-1 -translate-y-1/2 rounded-full bg-white/60 cursor-ew-resize"
                            title="Trim clip end"
                          />
                        </div>
                      ))}
                    {dragPreview?.laneIndex === laneIdx && draggingDataRef.current && draggingDataRef.current.id === dragPreview.clipId && (
                      <div
                        className="absolute h-16 top-4 rounded-lg border border-dashed border-white/30 bg-white/10 opacity-40 pointer-events-none"
                        style={{
                          left: `${dragPreview.startTime * PIXELS_PER_SECOND}px`,
                          width: `${(clips.find(c => c.id === dragPreview.clipId)?.duration ?? 0.5) * PIXELS_PER_SECOND}px`,
                        }}
                      />
                    )}
                  </div>
                </div>
              ))}

              <button
                onClick={handleAddNewCustomLane}
                className="w-44 h-12 mt-2 flex items-center justify-center gap-2 border border-dashed border-neutral-800 hover:border-purple-500/50 hover:bg-purple-950/10 text-neutral-400 hover:text-purple-400 rounded-xl transition text-xs font-semibold shadow-sm"
              >
                <Plus className="w-4 h-4" /> Add Custom Lane
              </button>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}