import React, { useState } from 'react';
import StudioBoard from './pages/StudioBoard';
import UploadCenter from './pages/UploadCenter';
import { Sliders, CloudUpload } from 'lucide-react';

type PageView = 'studio' | 'upload';

export default function App() {
  const [activePage, setActivePage] = useState<PageView>('studio');

  return (
    <div className="flex h-screen w-screen bg-neutral-950 text-white overflow-hidden">
      
      {/* Global Navigation Hub Sidebar */}
      <nav className="w-20 bg-neutral-900 border-r border-neutral-800 flex flex-col items-center py-6 gap-6 z-20">
        <div className="font-black text-purple-500 tracking-tighter text-xl mb-4">DJ</div>
        
        <button 
          onClick={() => setActivePage('studio')}
          className={`p-3 rounded-xl transition ${
            activePage === 'studio' ? 'bg-purple-600 text-white shadow-lg' : 'text-neutral-400 hover:bg-neutral-800 hover:text-white'
          }`}
          title="Mixer Studio Timeline"
        >
          <Sliders className="w-5 h-5" />
        </button>

        <button 
          onClick={() => setActivePage('upload')}
          className={`p-3 rounded-xl transition ${
            activePage === 'upload' ? 'bg-purple-600 text-white shadow-lg' : 'text-neutral-400 hover:bg-neutral-800 hover:text-white'
          }`}
          title="Upload Center"
        >
          <CloudUpload className="w-5 h-5" />
        </button>
      </nav>

      {/* Dynamic Main Workspace Window Viewport */}
      <div className="flex-1 h-full overflow-hidden">
        {activePage === 'studio' ? <StudioBoard /> : <UploadCenter />}
      </div>

    </div>
  );
}