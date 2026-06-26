import os
os.environ["MUTAGEN_NO_WARNINGS"] = "1"

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List
import librosa
import soundfile as sf
import numpy as np
from mutagen import File as MutagenFile

app = FastAPI(title="Fortnite Festival Studio Backend AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CACHE_DIR = os.path.join(os.path.dirname(__file__), "stem_cache")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output_mixes")
os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

app.mount("/stems", StaticFiles(directory=CACHE_DIR), name="stems")
app.mount("/mixes", StaticFiles(directory=OUTPUT_DIR), name="mixes")

def get_audio_duration(file_path: str) -> int:
    try:
        audio = MutagenFile(file_path)
        if audio is not None and audio.info is not None:
            return int(audio.info.length)
    except Exception as e:
        print(f"⚠️ Mutagen error: {e}")
    return 180

class TimelineClipPayload(BaseModel):
    filename: str
    stem_type: str
    start_offset_seconds: float

class MixMatrixPayload(BaseModel):
    clips: List[TimelineClipPayload]

# Helper array for converting numerical pitch chroma keys to readable musical notation chords
PITCH_CLASSES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

def analyze_audio_properties(file_path: str):
    """
    Analyzes an audio file and extracts both its precise BPM 
    and estimated musical key signature.
    """
    try:
        y, sr = librosa.load(file_path, sr=22050)
        
        # 1. Calculate BPM matching your layout rule
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        bpm = float(librosa.feature.tempo(onset_envelope=onset_env, sr=sr)[0])
        if bpm <= 0: bpm = 120.0
            
        # 2. Key Estimation Math (Using chromagram profile analysis)
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
        chroma_avg = np.mean(chroma, axis=1)
        key_idx = int(np.argmax(chroma_avg))
        
        # Simple heuristic to guess major/minor based on peak placement energy splits
        # For a truly bulletproof analysis, full key-profile correlation (Krumhansl-Schmuckler) is ideal.
        is_minor = chroma_avg[(key_idx + 3) % 12] > chroma_avg[(key_idx + 4) % 12]
        mode_label = "m" if is_minor else ""
        
        estimated_key = f"{PITCH_CLASSES[key_idx]}{mode_label}"
        
        return round(bpm, 1), estimated_key
    except Exception as e:
        print(f"⚠️ Metadata analysis fallback on {os.path.basename(file_path)}: {e}")
        return 120.0, "C"

@app.get("/api/stems")
async def get_available_stems():
    stems = []
    supported_extensions = (".wav", ".mp3", ".ogg")
    files = [f for f in os.listdir(CACHE_DIR) if f.lower().endswith(supported_extensions)]
    
    for idx, filename in enumerate(files):
        file_path = os.path.join(CACHE_DIR, filename)
        
        # Pull real properties instantly
        bpm, key_signature = analyze_audio_properties(file_path)
        
        name_lower = filename.lower()
        if "vocal" in name_lower or "vox" in name_lower:
            stem_type = "vocals"
        elif "drum" in name_lower or "beat" in name_lower:
            stem_type = "drums"
        elif "bass" in name_lower:
            stem_type = "bass"
        else:
            stem_type = "other"
            
        song_display_name = filename.replace("_", " ").split(".")[0].title()

        stems.append({
            "id": f"real_{idx}",
            "song_name": song_display_name,
            "stem_type": stem_type,
            "duration_seconds": get_audio_duration(file_path),
            "filename": filename,
            "bpm": bpm,            # 🚀 Send to client
            "key": key_signature   # 🚀 Send to client
        })
    return stems

# 🎛️ YOUR ALIGNMENT LOGIC INTEGRATED HERE
def process_and_align_stem(file_path: str, target_bpm: float, start_offset: float, target_sr: int = 22050):
    """
    Loads a track, stretches it to match the target BPM using your Librosa formula,
    and returns the raw array padded with structural starting silence.
    """
    print(f"⏳ Processing stem: {os.path.basename(file_path)}")
    y, sr = librosa.load(file_path, sr=target_sr)
    
    # Run your clean native tempo detection formula
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    try:
        source_bpm = librosa.feature.tempo(onset_envelope=onset_env, sr=sr)[0]
        if source_bpm <= 0: source_bpm = 120.0
    except Exception:
        source_bpm = 120.0
        
    # Calculate stretch ratio matching your script
    stretch_ratio = target_bpm / source_bpm
    print(f"   ↳ Stretching track: {source_bpm:.1f} BPM -> {target_bpm:.1f} BPM (Ratio: {stretch_ratio:.2f})")
    
    # Dynamic time stretch
    y_stretched = librosa.effects.time_stretch(y, rate=stretch_ratio)
    
    # Calculate offset padding alignment
    silence_samples = int(start_offset * target_sr)
    if silence_samples > 0:
        y_aligned = np.concatenate([np.zeros(silence_samples, dtype=np.float32), y_stretched])
    else:
        y_aligned = y_stretched
        
    return y_aligned

@app.post("/api/mix")
async def render_mashup_matrix(payload: MixMatrixPayload):
    if not payload.clips:
        raise HTTPException(status_code=400, detail="Timeline grid layout matrix is empty.")
        
    TARGET_SR = 22050   # Universal processing sample rate
    
    # 🎯 STEP 1: DYNAMICALLY CALCULATE OPTIMAL BPM
    # Gather the true analyzed source BPM for every file on the timeline
    source_bpms = []
    valid_clips = []
    
    for clip in payload.clips:
        file_path = os.path.join(CACHE_DIR, clip.filename)
        if not os.path.exists(file_path):
            print(f"⚠️ Track missing from folder cache directory: {clip.filename}")
            continue
            
        valid_clips.append(clip)
        
        # Pull the accurate BPM for this file using our existing formula
        try:
            y, sr = librosa.load(file_path, sr=TARGET_SR)
            onset_env = librosa.onset.onset_strength(y=y, sr=sr)
            bpm = float(librosa.feature.tempo(onset_envelope=onset_env, sr=sr)[0])
            if bpm > 0:
                source_bpms.append(bpm)
        except Exception:
            pass

    # Fallback to 120 only if no clips could be parsed, otherwise use the optimal average
    TARGET_BPM = round(sum(source_bpms) / len(source_bpms), 1) if source_bpms else 120.0
    
    print(f"\n🚀 Starting Dynamic Master Mixdown Render...")
    print(f"📊 Analyzed track speeds: {[round(b, 1) for b in source_bpms]}")
    print(f"🎯 Calculated Optimal Project Target Tempo: {TARGET_BPM} BPM\n")
    
    processed_tracks = []
    max_length = 0
    
    # 2. Process and stretch each individual track to match the dynamic TARGET_BPM
    for clip in valid_clips:
        file_path = os.path.join(CACHE_DIR, clip.filename)
        
        y_aligned = process_and_align_stem(
            file_path=file_path,
            target_bpm=TARGET_BPM, # 🏎️ Uses the dynamic average instead of static 120!
            start_offset=clip.start_offset_seconds,
            target_sr=TARGET_SR
        )
        
        processed_tracks.append(y_aligned)
        if len(y_aligned) > max_length:
            max_length = len(y_aligned)
            
    if not processed_tracks:
        raise HTTPException(status_code=404, detail="No source audio files found to mix down.")
        
    # 3. Mash the arrays together into one master grid matrix
    master_mix = np.zeros(max_length, dtype=np.float32)
    for track in processed_tracks:
        master_mix[:len(track)] += track
        
    # 4. Normalize peaks to prevent clipping distortion
    max_peak = np.max(np.abs(master_mix))
    if max_peak > 1.0:
        master_mix /= max_peak
        print("🎚️ Master level normalized to safeguard against clipping distortion.")
        
    # 5. Write the finished mashup to disk
    output_filename = "master_mashup_mix.wav"
    output_path = os.path.join(OUTPUT_DIR, output_filename)
    
    sf.write(output_path, master_mix, TARGET_SR)
    print(f"✅ Render Complete! Master mix exported to: {output_path}\n")
    
    return {
        "success": True, 
        "message": f"Mashup compiled successfully at optimal {TARGET_BPM} BPM!",
        "downloadUrl": f"http://localhost:8000/mixes/{output_filename}"
    }