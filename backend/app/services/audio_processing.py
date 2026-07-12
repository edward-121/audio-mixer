import os
import json
import threading
import librosa
import soundfile as sf
import numpy as np
from pathlib import Path
from mutagen import File as MutagenFile 
from concurrent.futures import ThreadPoolExecutor, TimeoutError

BASE_DIR = Path(__file__).resolve().parent.parent.parent
analysis_executor = ThreadPoolExecutor(max_workers=1)
PITCH_CLASSES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

def get_audio_duration(file_path: str) -> int:
    """
    ⏱️ Extracts the precise audio playback runtime length in seconds using Mutagen.
    """
    try:
        audio = MutagenFile(file_path)
        if audio is not None and audio.info is not None:
            return int(audio.info.length)
    except Exception as e:
        print(f"⚠️ [DURATION WARNING] Failed reading duration via Mutagen for {Path(file_path).name}: {e}")
    return 180 

def get_metadata_path(file_path_or_dir: str, filename: str | None = None) -> str:
    """
    🚀 FIXED: Calculates the metadata path relative to the file's true 
    session directory instead of forcing it into the global root folder.
    """
    if filename:
        stem_name = Path(filename).stem
        return os.path.join(file_path_or_dir, f"{stem_name}.meta.json")
    else:
        p = Path(file_path_or_dir)
        return os.path.join(str(p.parent), f"{p.stem}.meta.json")

def load_cached_metadata_from_path(file_path: str):
    """Session-aware metadata loader"""
    metadata_path = get_metadata_path(file_path)
    if not os.path.exists(metadata_path): 
        return None
    try:
        with open(metadata_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
            print(f"📊 [METADATA READ] Found cache for {Path(file_path).name} -> {data}")
            return data
    except Exception as e: 
        print(f"⚠️ [METADATA ERROR] Failed to read cache: {e}")
        return None

def save_cached_metadata_from_path(file_path: str, bpm: float, key_signature: str, onset_offset_seconds: float):
    """Session-aware metadata saver"""
    metadata_path = get_metadata_path(file_path)
    payload = {"bpm": bpm, "key": key_signature, "onset_offset_seconds": onset_offset_seconds}
    try:
        with open(metadata_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)
        print(f"💾 [METADATA WRITE] Saved cache for {Path(file_path).name} to {metadata_path} -> {payload}")
    except Exception as exc:
        print(f"⚠️ [METADATA ERROR] Could not persist metadata: {exc}")

def analyze_audio_properties(file_path: str):
    print(f"🕵️‍♂️ [ANALYZER] Starting deep analysis on: {Path(file_path).name}")
    try:
        y, sr = librosa.load(file_path, sr=11025, offset=30.0, duration=7.0)
        
        if len(y) == 0:
            y, sr = librosa.load(file_path, sr=11025, duration=7.0)

        try:
            onset_env = librosa.onset.onset_strength(y=y, sr=sr)
            bpm = float(librosa.feature.tempo(onset_envelope=onset_env, sr=sr)[0])
            if not np.isfinite(bpm) or bpm <= 0: bpm = 120.0
        except Exception as e: 
            print(f"⚠️ [ANALYZER WARNING] BPM calculation failed: {e}")
            bpm = 120.0

        try:
            onset_frames = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr, backtrack=True)
            onset_offset_seconds = float(librosa.frames_to_time(int(onset_frames[0]), sr=sr)) if len(onset_frames) > 0 else 0.0
        except Exception: 
            onset_offset_seconds = 0.0

        try:
            chroma = librosa.feature.chroma_stft(y=y, sr=sr)
            chroma_avg = np.mean(chroma, axis=1)
            key_idx = int(np.argmax(chroma_avg))
            is_minor = chroma_avg[(key_idx + 3) % 12] > chroma_avg[(key_idx + 4) % 12]
            estimated_key = f"{PITCH_CLASSES[key_idx]}{'m' if is_minor else ''}"
        except Exception: 
            estimated_key = "C"

        print(f"✅ [ANALYZER SUCCESS] Analyzed {Path(file_path).name} -> {round(bpm, 1)} BPM | Key: {estimated_key}")
        return round(bpm, 1), estimated_key, round(onset_offset_seconds, 3)
    except Exception as e:
        print(f"❌ [ANALYZER CRITICAL] Failed to read audio file: {e}")
        return 120.0, "C", 0.0

def analyze_audio_properties_with_timeout(file_path: str, timeout_seconds: int = 8):
    print(f"⏱️ [TIMEOUT GUARD] Running quick sync check on {Path(file_path).name} (Max {timeout_seconds}s)")
    try:
        future = analysis_executor.submit(analyze_audio_properties, file_path)
        return future.result(timeout=timeout_seconds)
    except TimeoutError:
        print(f"⏳ [TIMEOUT HIT] Sync check hit {timeout_seconds}s limit for {Path(file_path).name}. Handing off to background thread.")
        # 🚀 CHANGE: Return the fallback values to the API, but DO NOT save them to disk yet!
        # This keeps the cache empty so the background thread can overwrite it cleanly.
        return 120.0, "C", 0.0
    except Exception as e:
        print(f"❌ [TIMEOUT ERROR] Sync check failed: {e}")
        return 120.0, "C", 0.0

def enqueue_metadata_analysis(file_path: str):
    """Enqueues background worker matching correct folder targets"""
    def _analyze_and_cache():
        print(f"🧵 [THREAD] Background worker thread spawned for {Path(file_path).name}")
        try:
            # Run the deep math calculation
            bpm, key_signature, onset_offset_seconds = analyze_audio_properties(file_path)
            
            # 🚀 Save the real, calculated values directly to disk
            save_cached_metadata_from_path(file_path, bpm, key_signature, onset_offset_seconds)
            print(f"🎉 [THREAD SUCCESS] Overwrote cache for {Path(file_path).name} with true values: {bpm} BPM | Key: {key_signature}")
        except Exception as e: 
            print(f"❌ [THREAD ERROR] Background thread died: {e}")
            
    threading.Thread(target=_analyze_and_cache, daemon=True).start()

def process_and_align_stem(file_path: str, target_bpm: float, start_offset: float, audio_start_offset: float = 0.0, target_sr: int = 22050):
    """Time-stretches and pads the clip array to perfectly snap grid items to the tempo map"""
    y, sr = librosa.load(file_path, sr=target_sr)
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    try:
        source_bpm = float(librosa.feature.tempo(onset_envelope=onset_env, sr=sr)[0])
        if source_bpm <= 0: source_bpm = 120.0
    except Exception: 
        source_bpm = 120.0

    if audio_start_offset > 0:
        start_sample = min(len(y), int(audio_start_offset * sr))
        y = y[start_sample:]

    stretch_ratio = target_bpm / source_bpm
    y_stretched = librosa.effects.time_stretch(y, rate=stretch_ratio)

    silence_samples = int(start_offset * target_sr)
    return np.concatenate([np.zeros(silence_samples, dtype=np.float32), y_stretched]) if silence_samples > 0 else y_stretched

def make_unique_cache_path(filename: str, cache_dir: str) -> str:
    """Safeguards user folder configurations against duplicate filename overwrites"""
    base_name, extension = os.path.splitext(filename)
    candidate_path = os.path.join(cache_dir, filename)
    counter = 1
    while os.path.exists(candidate_path):
        candidate_path = os.path.join(cache_dir, f"{base_name}_{counter}{extension}")
        counter += 1
    return candidate_path