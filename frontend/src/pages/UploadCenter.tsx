import React, { useState, useRef } from 'react';
import { ApiService } from '../services/api';
import { Upload, Loader2, CheckCircle, AlertCircle, Music } from 'lucide-react';

export default function UploadCenter() {
  const [isProcessing, setIsProcessing] = useState(false);
  const [status, setStatus] = useState<{ type: 'idle' | 'success' | 'error'; message: string }>({
    type: 'idle',
    message: ''
  });
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const processUpload = async (file: File) => {
    // Basic format safety verification on the frontend client side
    const ext = file.name.split('.').pop()?.toLowerCase();
    if (ext !== 'mp3' && ext !== 'wav' && ext !== 'ogg') {
      setStatus({
        type: 'error',
        message: 'Unsupported format. Please select a valid standard .mp3, .wav, or .ogg file.'
      });
      return;
    }

    setIsProcessing(true);
    setStatus({ type: 'idle', message: '' });

    try {
      await ApiService.uploadFullSong(file);
      setStatus({
        type: 'success',
        message: `✨ "${file.name}" successfully split! Demucs extracted Vocals, Drums, Bass, and Melodies into your stem cache.`
      });
    } catch (err: any) {
      setStatus({
        type: 'error',
        message: err.message || 'The local Demucs AI processing failed to parse this file structure.'
      });
    } finally {
      setIsProcessing(false);
    }
  };

  // Drag and Drop event piping handlers
  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      processUpload(e.dataTransfer.files[0]);
    }
  };

  const handleFileSelectionChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      processUpload(e.target.files[0]);
    }
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-full w-full bg-neutral-950 p-6 text-white select-none">
      <div className="w-full max-w-2xl bg-neutral-900 border border-neutral-800 rounded-2xl p-8 shadow-2xl flex flex-col gap-6">
        
        <div className="text-center">
          <div className="inline-flex p-3 bg-purple-950/40 rounded-xl border border-purple-900/40 text-purple-400 mb-3">
            <Music className="w-6 h-6" />
          </div>
          <h2 className="text-xl font-bold tracking-tight">AI Multi-Stem Splitter Center</h2>
          <p className="text-sm text-neutral-400 mt-1">
            Drop any complete master song below. The local machine will break it down into 4 isolated audio mixdown layers.
          </p>
        </div>

        {/* 📥 DRAG AND DROP ZONE CANVAS ELEMENT */}
        <div
          onDragEnter={handleDrag}
          onDragOver={handleDrag}
          onDragLeave={handleDrag}
          onDrop={handleDrop}
          onClick={() => !isProcessing && fileInputRef.current?.click()}
          className={`relative border-2 border-dashed rounded-xl p-12 transition-all text-center flex flex-col items-center justify-center gap-3 group ${
            isProcessing ? 'border-purple-600 bg-purple-950/5 cursor-not-allowed' : 
            dragActive ? 'border-purple-500 bg-purple-950/10 scale-[0.99]' : 
            'border-neutral-800 hover:border-neutral-700 bg-neutral-950/30 cursor-pointer'
          }`}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".mp3,.wav,.ogg"
            onChange={handleFileSelectionChange}
            disabled={isProcessing}
            className="hidden"
          />

          {isProcessing ? (
            <div className="flex flex-col items-center gap-4 py-4 animate-fade-in">
              <Loader2 className="w-10 h-10 animate-spin text-purple-500" />
              <div className="flex flex-col gap-1">
                <span className="text-sm font-semibold tracking-wide text-neutral-200">
                  Demucs Neural Network Processing Active...
                </span>
                <span className="text-xs text-neutral-500 font-mono">
                  This can take 30-90 seconds depending on GPU availability.
                </span>
              </div>
              <div className="flex gap-2 mt-2">
                <span className="text-[10px] uppercase font-mono px-2 py-0.5 bg-neutral-800 border border-neutral-700 text-neutral-400 rounded">Vocals</span>
                <span className="text-[10px] uppercase font-mono px-2 py-0.5 bg-neutral-800 border border-neutral-700 text-neutral-400 rounded">Drums</span>
                <span className="text-[10px] uppercase font-mono px-2 py-0.5 bg-neutral-800 border border-neutral-700 text-neutral-400 rounded">Bass</span>
                <span className="text-[10px] uppercase font-mono px-2 py-0.5 bg-neutral-800 border border-neutral-700 text-neutral-400 rounded">Other</span>
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-2 py-4">
              <Upload className="w-8 h-8 text-neutral-500 group-hover:text-purple-400 transition-colors" />
              <span className="text-sm text-neutral-300 font-medium mt-2">
                Drag & drop full track file here, or <span className="text-purple-400 underline decoration-purple-400/30">browse local files</span>
              </span>
              <span className="text-xs text-neutral-600 font-mono mt-1 uppercase tracking-wider">
                Supported: WAV, MP3
              </span>
            </div>
          )}
        </div>

        {/* 🎛️ STATUS NOTIFICATION POPUPS */}
        {status.type !== 'idle' && (
          <div className={`flex items-start gap-3 p-4 rounded-xl border text-sm animate-fade-in ${
            status.type === 'success' 
              ? 'bg-emerald-950/20 border-emerald-900/50 text-emerald-400' 
              : 'bg-red-950/20 border-red-900/50 text-red-400'
          }`}>
            {status.type === 'success' ? (
              <CheckCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
            ) : (
              <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
            )}
            <div className="flex-1">
              <p className="font-medium leading-relaxed">{status.message}</p>
            </div>
          </div>
        )}
        
      </div>
    </div>
  );
}