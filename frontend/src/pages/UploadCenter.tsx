import React from 'react';
import { Upload, Music } from 'lucide-react';

export default function UploadCenter() {
  return (
    <div className="flex flex-col items-center justify-center h-full max-w-xl mx-auto text-center p-8">
      <div className="p-6 bg-purple-600/10 rounded-full border border-purple-500/20 text-purple-400 mb-6">
        <Upload className="w-10 h-10" />
      </div>
      <h2 className="text-2xl font-bold mb-2">Upload Track Deck</h2>
      <p className="text-neutral-400 text-sm mb-6">
        Drop any MP3, WAV, or FLAC audio file here. Our local backend AI will automatically isolate the vocals, drums, bassline, and synthesizers into separate timeline blocks.
      </p>
      
      <div className="w-full border-2 border-dashed border-neutral-800 hover:border-purple-500/50 rounded-2xl p-12 bg-neutral-900/20 cursor-pointer transition flex flex-col items-center gap-3">
        <Music className="text-neutral-600 w-8 h-8" />
        <span className="text-sm font-medium text-neutral-300">Drag & drop files here, or browse local media</span>
        <span className="text-xs text-neutral-500">Max file size: 50MB</span>
      </div>
    </div>
  );
}