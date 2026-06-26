import React, { useState, useRef, useEffect } from 'react';
import type { AudioStem, TimelineClip } from '../types';
import { ApiService } from '../services/api';
import { Play, Square, Layers, Sparkles, Loader2, Trash2, RotateCcw, Plus } from 'lucide-react';

const DEFAULT_LANES = ['🎤 Vocals', '🥁 Drums', '🎸 Bassline', '🎹 Melodies / Other'];
const PIXELS_PER_SECOND = 30;

export default function StudioBoard() {
  const [stemsPool, setStemsPool] = useState<AudioStem[]>([]);
  const [clips, setClips] = useState<TimelineClip[]>([]);
  const [lanes, setLanes] = useState<string[]>(DEFAULT_LANES);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [currentTime, setCurrentTime] = useState(0);

  const timelineRef = useRef<HTMLDivElement>(null);
  const activeAudioPlayersRef = useRef<{ audio: HTMLAudioElement; timeoutId: number }[]>([]);
  const animationFrameRef = useRef<number | null>(null);
  const startTimeRef = useRef<number>(0);

  // ⚡ HIGH-PERFORMANCE DRAG REFERENCES
  const draggingDataRef = useRef<{
    id: string;
    startX: number;
    originalStartTime: number;
    domElement: HTMLElement;
    currentComputedStartTime: number;
  } | null>(null);

  useEffect(() => {
    async function loadRealAudioStems() {
      setIsLoading(true);
      const activeStems = await ApiService.getAvailableStems();
      setStemsPool(activeStems);
      setIsLoading(false);
    }
    loadRealAudioStems();
  }, []);

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
    };
    setClips([...clips, newClip]);
  };

  const removeClipFromTimeline = (clipId: string) => {
    if (isPlaying) handleStopPreview();
    setClips(prev => prev.filter(clip => clip.id !== clipId));
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

  // --- AUDIO PREVIEW ENGINE ---
  const updatePlayhead = (timestamp: number) => {
    if (!startTimeRef.current) startTimeRef.current = timestamp;
    const elapsedSeconds = (timestamp - startTimeRef.current) / 1000;
    setCurrentTime(elapsedSeconds);

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
    activeAudioPlayersRef.current.forEach(({ audio, timeoutId }) => {
      clearTimeout(timeoutId);
      audio.pause();
      audio.currentTime = 0;
    });
    activeAudioPlayersRef.current = [];
    setIsPlaying(false);
    setCurrentTime(0);
    startTimeRef.current = 0;
  };

  const handleTogglePreview = () => {
    if (isPlaying) {
      handleStopPreview();
      return;
    }

    setIsPlaying(true);
    startTimeRef.current = 0;
    animationFrameRef.current = requestAnimationFrame(updatePlayhead);

    clips.forEach((clip) => {
      const audio = new Audio(clip.stem.fileUrl);
      const startDelayMs = clip.startTime * 1000;

      const timeoutId = window.setTimeout(() => {
        audio.play().catch(err => console.log("Playback blocked:", err));
      }, startDelayMs);

      activeAudioPlayersRef.current.push({ audio, timeoutId });
    });
  };

  // --- 🏎️ GLOBAL CENTRALIZED CANVAS POINTER TRACKING SYSTEM ---
  const handlePointerDown = (e: React.PointerEvent, clip: TimelineClip) => {
    if (isPlaying) handleStopPreview();
    e.stopPropagation();

    const targetElement = e.currentTarget as HTMLElement;

    // ⚡ Tell the browser to lock ALL pointer events to this specific element globally
    targetElement.setPointerCapture(e.pointerId);

    draggingDataRef.current = {
      id: clip.id,
      startX: e.clientX,
      originalStartTime: clip.startTime,
      domElement: targetElement,
      currentComputedStartTime: clip.startTime
    };
  };

  const handlePointerMove = (e: React.PointerEvent) => {
    // If we aren't actively moving a specific target block, skip out instantly
    if (!draggingDataRef.current) return;
    e.preventDefault(); // Stop the browser from attempting to select text on screen

    const data = draggingDataRef.current;
    const deltaX = e.clientX - data.startX;
    const deltaSeconds = deltaX / PIXELS_PER_SECOND;
    const newStartTime = Math.max(0, data.originalStartTime + deltaSeconds);

    data.currentComputedStartTime = newStartTime;

    // Use hardware-accelerated CSS translation instead of modifying raw layout styles
    data.domElement.style.transform = `translateX(${deltaX}px)`;

    const labelNode = data.domElement.querySelector('.clip-time-label');
    if (labelNode) {
      labelNode.textContent = `Starts at: ${newStartTime.toFixed(1)}s`;
    }
  };

  const handlePointerUp = (e: React.PointerEvent) => {
    if (!draggingDataRef.current) return;
    const data = draggingDataRef.current;

    (e.target as HTMLElement).releasePointerCapture(e.pointerId);

    const finalTime = data.currentComputedStartTime;

    // 🧼 Clear out temporary hardware transformation offsets before committing
    data.domElement.style.transform = 'none';

    // Save position to state exactly once
    setClips(prev => prev.map(c => c.id === data.id ? { ...c, startTime: finalTime } : c));

    draggingDataRef.current = null;
  };

  const handleRenderMasterMix = async () => {
    if (clips.length === 0) return alert("Add some clips to your timeline grid layout first!");

    const layoutMatrix = clips.map(c => ({
      filename: c.stem.fileUrl.split('/').pop(),
      stem_type: c.stem.stemType,
      start_offset_seconds: parseFloat(c.startTime.toFixed(2))
    }));

    const result = await ApiService.renderMashupMatrix(layoutMatrix);
    if (result.success) {
      alert("Mashup Render complete! Your file has been perfectly beat-aligned.");
    }
  };

  const formatTimeLabel = (totalSeconds: number) => {
    const mins = Math.floor(totalSeconds / 60);
    const secs = Math.floor(totalSeconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className="flex flex-col h-full w-full bg-neutral-950 text-white select-none">
      <header className="flex items-center justify-between px-6 py-4 bg-neutral-900 border-b border-neutral-800">
        <div className="flex items-center gap-2">
          <Layers className="text-purple-500 w-6 h-6" />
          <h1 className="text-lg font-bold tracking-tight">Fortnite Festival Studio</h1>
        </div>
        <div className="flex items-center gap-3">
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

          <button
            onClick={clearTimelineBoard}
            className="flex items-center gap-2 bg-neutral-800 hover:bg-neutral-700 border border-neutral-700 px-3 py-2 rounded-md text-sm text-neutral-300 font-medium transition"
          >
            <RotateCcw className="w-4 h-4" /> Reset Board
          </button>

          <button
            onClick={handleRenderMasterMix}
            className="flex items-center gap-2 bg-purple-600 hover:bg-purple-700 px-4 py-2 rounded-md text-sm font-medium shadow-lg transition"
          >
            <Sparkles className="w-4 h-4" /> Render Master Mashup
          </button>
        </div>
      </header>

      <main className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        <aside className="w-72 bg-neutral-900/50 p-4 border-r border-neutral-900 flex flex-col gap-4">
          <div>
            <h3 className="text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-2">Available Stems</h3>
            <p className="text-xs text-neutral-500 mb-4">Click a track stem below to drop it onto its designated mixing row lane.</p>
          </div>

          {isLoading ? (
            <div className="flex-1 flex flex-col items-center justify-center text-neutral-500 gap-2">
              <Loader2 className="w-6 h-6 animate-spin text-purple-500" />
              <span className="text-xs">Connecting to local AI storage...</span>
            </div>
          ) : (
            <div className="flex flex-col gap-2 overflow-y-auto pr-1">
              {stemsPool.length === 0 ? (
                <p className="text-xs text-neutral-600 text-center py-8">No stems discovered in cache. Head to the Upload center to drop a song track!</p>
              ) : (
                stemsPool.map(stem => (
                  <div key={stem.id} className="p-3 bg-neutral-900 border border-neutral-800 rounded-lg flex flex-col gap-2">
                    <div className="flex justify-between items-start">
                      <div>
                        <h4 className="font-medium text-sm truncate max-w-[150px]">{stem.songName}</h4>
                        <span className="text-[10px] uppercase font-mono text-neutral-400">{stem.stemType}</span>
                      </div>
                      <span className="text-xs text-neutral-500 font-mono">{formatTimeLabel(stem.duration)}</span>
                    </div>

                    <div className="grid grid-cols-2 gap-1">
                      {lanes.slice(0, 4).map((lName, idx) => (
                        <button
                          key={idx}
                          onClick={() => addClipToTimeline(stem, idx)}
                          className="text-[10px] bg-neutral-800 hover:bg-purple-950/60 text-neutral-300 py-1 px-1 rounded border border-neutral-700 truncate"
                        >
                          + {lName.split(' ').pop()}
                        </button>
                      ))}
                    </div>
                  </div>
                ))
              )}
            </div>
          )}
        </aside>

        {/* Workspace Canvas */}
        <section className="flex-1 bg-neutral-950 overflow-x-auto overflow-y-auto p-6 relative" ref={timelineRef}>
          <div className="relative flex flex-col min-h-full pb-16" style={{ width: '7200px' }}>

            {/* Time Grid Markers */}
            <div className="flex border-b border-neutral-900 pb-2 mb-4 font-mono text-xs text-neutral-500 relative h-6 ml-44">
              {[0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150, 160, 170, 180, 200, 220, 240].map(sec => (
                <span key={sec} className="absolute" style={{ left: `${sec * PIXELS_PER_SECOND}px` }}>
                  {formatTimeLabel(sec)}
                </span>
              ))}
            </div>

            {/* Playhead Line */}
            <div
              className="absolute top-8 bottom-16 w-[2px] bg-purple-500 shadow-[0_0_12px_#a855f7] z-30 pointer-events-none ml-44 transition-transform duration-75"
              style={{ transform: `translateX(${currentTime * PIXELS_PER_SECOND}px)` }}
            />

            {/* Lanes Matrix */}
            <div className="flex flex-col gap-4">
              {lanes.map((laneTitle, laneIdx) => (
                <div key={laneIdx} className="h-24 bg-neutral-900/10 border border-neutral-900/40 rounded-xl relative flex items-center shadow-inner">

                  <div className="absolute left-0 top-0 bottom-0 w-44 bg-neutral-900/95 backdrop-blur-md px-4 flex items-center border-r border-neutral-800 text-xs font-bold tracking-wide text-neutral-300 z-40 shadow-lg">
                    {laneTitle}
                  </div>

                  <div className="absolute inset-0 left-44 h-full z-10">
                    {/* Find this mapped block container */}
                    {clips
                      .filter(c => c.laneIndex === laneIdx)
                      .map(clip => (
                        <div
                          key={clip.id}
                          onPointerDown={(e) => handlePointerDown(e, clip)}
                          onPointerMove={handlePointerMove}
                          onPointerUp={handlePointerUp}

                          // 🚀 VERIFY THESE TAILWIND CLASSES ARE PRESENT:
                          className={`absolute h-16 top-4 rounded-lg border p-3 flex flex-col justify-between cursor-grab active:cursor-grabbing shadow-md group select-none touch-none will-change-transform ${clip.stem.color}`}

                          style={{
                            left: `${clip.startTime * PIXELS_PER_SECOND}px`,
                            width: `${clip.stem.duration * PIXELS_PER_SECOND}px`,
                          }}
                        >
                          {/* ... keeping inner contents completely the same ... */}
                          <div className="flex justify-between items-center gap-2">
                            <div className="flex flex-col min-w-0">
                              <span className="font-bold text-xs truncate max-w-[140px]">{clip.stem.songName}</span>
                              {/* ⚡ Class clip-time-label allows zero-latency direct DOM updates */}
                              <span className="clip-time-label text-[9px] font-mono opacity-70">Starts at: {clip.startTime.toFixed(1)}s</span>
                            </div>

                            <button
                              onPointerDown={(e) => e.stopPropagation()}
                              onClick={() => removeClipFromTimeline(clip.id)}
                              className="p-1 rounded-md bg-black/30 text-neutral-400 hover:bg-red-600 hover:text-white transition z-50 cursor-pointer"
                              title="Delete track"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>

                          <div className="w-full h-3 bg-black/20 rounded-sm flex items-center justify-around opacity-40 pointer-events-none">
                            {[...Array(20)].map((_, i) => (
                              <div key={i} className="w-[1.5px] bg-white rounded-full" style={{ height: `${Math.abs(Math.sin(i * 0.4)) * 100}%` }}></div>
                            ))}
                          </div>
                        </div>
                      ))}
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