import os
from mutagen import File as MutagenFile

os.environ["MUTAGEN_NO_WARNINGS"] = "1" # Silence extra media tag warnings

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List
import wave
import contextlib

app = FastAPI(title="Fortnite Festival Studio Backend AI")

# 🔓 ALLOW CORS: This lets your frontend at localhost:5173 talk to localhost:8000 safely
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CACHE_DIR = os.path.join(os.path.dirname(__file__), "stem_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# 🎧 Mount the stem cache directory as static files so the browser can stream the audio directly
app.mount("/stems", StaticFiles(directory=CACHE_DIR), name="stems")


# Helper function to extract length of audio file automatically
def get_audio_duration(file_path: str) -> int:
    """
    Dynamically opens ANY audio format (MP3, WAV, OGG, FLAC) 
    and extracts its exact runtime down to the second.
    """
    try:
        audio = MutagenFile(file_path)
        if audio is not None and audio.info is not None:
            return int(audio.info.length) # Returns precise total seconds
    except Exception as e:
        print(f"⚠️ Mutagen metrics exception reading {os.path.basename(file_path)}: {e}")
    
    return 180 # 🎯 CHANGED: Set default fallback to 3 mins (180s) instead of 15s if everything fails


# Models for reading the frontend incoming matrix setup
class TimelineClipPayload(BaseModel):
    filename: str
    stem_type: str
    start_offset_seconds: float

class MixMatrixPayload(BaseModel):
    clips: List[TimelineClipPayload]


@app.get("/api/stems")
async def get_available_stems():
    """
    Scans the stem_cache directory and returns real files formatted for your frontend UI
    """
    stems = []
    supported_extensions = (".wav", ".mp3", ".ogg")
    
    # Read files inside the local folder
    files = [f for f in os.listdir(CACHE_DIR) if f.lower().endswith(supported_extensions)]
    
    for idx, filename in enumerate(files):
        file_path = os.path.join(CACHE_DIR, filename)
        
        # Simple string heuristics to deduce item categorization groups
        name_lower = filename.lower()
        if "vocal" in name_lower or "vox" in name_lower:
            stem_type = "vocals"
        elif "drum" in name_lower or "beat" in name_lower:
            stem_type = "drums"
        elif "bass" in name_lower:
            stem_type = "bass"
        else:
            stem_type = "other"
            
        # Clean up presentation text name
        song_display_name = filename.replace("_", " ").split(".")[0].title()

        stems.append({
            "id": f"real_{idx}",
            "song_name": song_display_name,
            "stem_type": stem_type,
            "duration_seconds": get_audio_duration(file_path),
            "filename": filename
        })
        
    return stems


@app.post("/api/mix")
async def render_mashup_matrix(payload: MixMatrixPayload):
    """
    Receives the layout data showing exactly when and where the user dropped their audio clips.
    """
    print("\n🎛️ --- RECEIVED TIMELINE LAYOUT ARRAY MATRIX FROM FRONTEND ---")
    for clip in payload.clips:
        print(f"🎵 File: {clip.filename:<25} | Type: {clip.stem_type:<8} | Trigger Delay: {clip.start_offset_seconds}s")
    print("-------------------------------------------------------------\n")
    
    # This is exactly where you will eventually import your audio engineering scripts 
    # (like pydub or AudioSegment) to overlay and stitch the tracks together.
    
    return {"success": True, "message": "Timeline data parsed successfully!"}