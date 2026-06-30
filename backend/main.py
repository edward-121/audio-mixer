import os
os.environ["MUTAGEN_NO_WARNINGS"] = "1"

from pathlib import Path
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List
import librosa
import soundfile as sf
import numpy as np
from mutagen import File as MutagenFile
import subprocess
import shutil


BASE_DIR = Path(__file__).resolve().parent

# 💾 The global cache folder where stems are imported and split
CACHE_DIR = os.path.join(BASE_DIR, "stem_cache")

# 🎚️ The output directory where finished master mashups are exported
OUTPUT_DIR = os.path.join(BASE_DIR, "output_mixes")

# 🛡️ Automatically create the physical folders on your machine if they don't exist yet
os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

app = FastAPI(title="Audio Mixer Backend AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def make_unique_cache_path(filename: str, cache_dir: str = CACHE_DIR) -> str:
    base_name, extension = os.path.splitext(filename)
    candidate_path = os.path.join(cache_dir, filename)
    counter = 1

    while os.path.exists(candidate_path):
        candidate_path = os.path.join(cache_dir, f"{base_name}_{counter}{extension}")
        counter += 1

    return candidate_path


def run_demucs_splitter(song_path, cache_dir=CACHE_DIR):
    """
    Your original Meta Demucs AI separation logic.
    Forced to match the app cache directory with flat file mapping.
    """
    # 🛡️ THE WINDOWS PYTHON FIX: Force the global audio backend to soundfile
    os.environ["TORCHAUDIO_BACKEND"] = "soundfile"

    try:
        import torchaudio
        # Force torchaudio to completely forget torchcodec exists
        if hasattr(torchaudio, "_torchcodec") or hasattr(torchaudio, "save_with_torchcodec"):
            print("🔧 [Patch] Redirecting torchaudio save mechanics to standard soundfile backends...")
            import torchaudio._soundfile as ta_sf
            torchaudio.save = ta_sf.save
    except Exception:
        pass

    base_filename = os.path.basename(song_path)
    song_name = os.path.splitext(base_filename)[0].replace(" ", "_")

    # Standard temporary folder where Demucs dumps output naturally
    demucs_output_dir = os.path.join("separated", "htdemucs", song_name)

    # Map out the exact flat file output targets your frontend sidebar looks for
    stem_types = ["vocals", "bass", "drums", "other"]
    final_flat_stems = {
        s_type: os.path.join(cache_dir, f"{song_name}_{s_type}.wav")
        for s_type in stem_types
    }

    # 📦 Caching Check: If vocals exist, assume the song was split previously
    if os.path.exists(final_flat_stems["vocals"]):
        print(f"📦 [Local AI] Found cached flat stems for '{song_name}'. Skipping computation!")
        return True

    print(f"\n🧠 [Local AI] Initializing Demucs Neural Network for '{song_name}'...")

    user_profile = os.environ.get("USERPROFILE", "C:\\Users\\default")
    demucs_path = os.path.join(user_profile, ".local", "bin", "demucs.exe")

    if not os.path.exists(demucs_path):
        demucs_path = os.path.join(os.environ.get("APPDATA", ""), "Python", "Scripts", "demucs.exe")

    if not os.path.exists(demucs_path):
        demucs_path = "demucs"

    command = [demucs_path, song_path]

    try:
        # Run Demucs CLI execution process
        subprocess.run(command, check=True)

        print(f"🚚 Flattening and moving files from '{demucs_output_dir}' straight to '{cache_dir}'...")

        for stem_name, destination_path in final_flat_stems.items():
            source_path = os.path.join(demucs_output_dir, f"{stem_name}.wav")
            if os.path.exists(source_path):
                # Move and rename to flat file format e.g. "MySong_vocals.wav"
                shutil.move(source_path, destination_path)
            else:
                print(f"⚠️ Warning: Could not find expected AI stem at {source_path}")

        # Clean out scratch build trees left by Demucs
        if os.path.exists("separated"):
            shutil.rmtree("separated")

        print("✨ Extraction and folder organization complete!")
        return True

    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"❌ Error: Local Demucs engine failed to run. Details: {e}")
        return False


@app.post("/api/upload/song")
async def upload_full_song(file: UploadFile = File(...)):
    """
    Upload a full song and split it into stems (vocals/bass/drums/other) via Demucs.
    """
    supported_extensions = (".wav", ".mp3", ".ogg")
    if not file.filename.lower().endswith(supported_extensions):
        raise HTTPException(status_code=400, detail="Unsupported audio file format.")

    clean_filename = file.filename.replace(" ", "_")
    temp_upload_path = os.path.join(CACHE_DIR, f"{clean_filename}")

    try:
        # 1. Write incoming song temporarily to disk
        with open(temp_upload_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)

        # 2. Trigger the Demucs splitting engine
        success = run_demucs_splitter(temp_upload_path)

        # 3. Always delete the temporary source file
        if os.path.exists(temp_upload_path):
            os.remove(temp_upload_path)

        if not success:
            raise HTTPException(status_code=500, detail="Demucs audio separation engine failed.")

        return {
            "success": True,
            "message": "Song successfully isolated into custom flat stems!"
        }
    except Exception as e:
        if os.path.exists(temp_upload_path):
            os.remove(temp_upload_path)
        raise HTTPException(status_code=500, detail=str(e))


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
    duration_seconds: float | None = None
    key_signature: str | None = None


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
        if bpm <= 0:
            bpm = 120.0

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


# 🚀 FIX: Notice we changed 'async def' to standard 'def'
# This tells FastAPI to handle the heavy audio calculations safely in a background thread.
@app.post("/api/upload")
def upload_audio_stem(file: UploadFile = File(...)):
    """
    Upload an already-isolated stem directly and analyze its BPM/key.
    """
    supported_extensions = (".wav", ".mp3", ".ogg")
    if not file.filename.lower().endswith(supported_extensions):
        raise HTTPException(
            status_code=400,
            detail="Unsupported audio format. Please drop a .wav, .mp3, or .ogg stem."
        )

    clean_filename = file.filename.replace(" ", "_")
    destination_path = make_unique_cache_path(clean_filename)
    saved_filename = os.path.basename(destination_path)

    try:
        # 📁 Stream and save the file synchronously
        with open(destination_path, "wb") as buffer:
            # Since it's a standard def, we use file.file.read() instead of await file.read()
            content = file.file.read()
            buffer.write(content)

        print(f"📥 Successfully cached new source file: {saved_filename}")

        # 📊 This heavy librosa CPU calculation no longer freezes your app!
        bpm, key_sig = analyze_audio_properties(destination_path)
        print(f"📊 Live Scan Results -> {bpm} BPM | Key: {key_sig}")

        return {
            "success": True,
            "filename": saved_filename,
            "message": f"Successfully loaded and analyzed track at {bpm} BPM!"
        }
    except Exception as e:
        print(f"❌ Upload processing failure: {e}")
        if os.path.exists(destination_path):
            os.remove(destination_path)
        raise HTTPException(status_code=500, detail=f"Failed to process audio file: {str(e)}")


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

        # Extract song name without stem type suffix
        base_name = filename.replace("_", " ").split(".")[0]
        # Remove stem type keywords from the end of the name
        for keyword in ["vocals", "drums", "bass", "other", "vox", "beat"]:
            if base_name.lower().endswith(" " + keyword):
                base_name = base_name[:-len(keyword)-1]
                break
        song_display_name = base_name.title()

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


@app.delete("/api/stems")
async def delete_cached_stems(songName: str | None = None):
    supported_extensions = (".wav", ".mp3", ".ogg")
    removed = []

    for filename in os.listdir(CACHE_DIR):
        if not filename.lower().endswith(supported_extensions):
            continue

        if songName is not None:
            stem_name = os.path.splitext(filename)[0].replace("_", " ").lower()
            if songName.lower() not in stem_name:
                continue

        file_path = os.path.join(CACHE_DIR, filename)
        os.remove(file_path)
        removed.append(filename)

    return {
        "success": True,
        "message": f"Removed {len(removed)} cached stems." if removed else "No matching cached stems found."
    }


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
        if source_bpm <= 0:
            source_bpm = 120.0
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
            target_bpm=TARGET_BPM,  # 🏎️ Uses the dynamic average instead of static 120!
            start_offset=clip.start_offset_seconds,
            target_sr=TARGET_SR
        )

        if clip.duration_seconds is not None and clip.duration_seconds > 0:
            target_samples = int(clip.duration_seconds * TARGET_SR)
            if target_samples < len(y_aligned):
                y_aligned = y_aligned[:target_samples]

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