import os
import librosa
import numpy as np
import soundfile as sf
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List
from pathlib import Path
from app.dependencies import get_session_cache_dir
from app.services.audio_processing import process_and_align_stem

router = APIRouter(prefix="/api", tags=["mix"])

BASE_DIR = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", str(BASE_DIR / "output_mixes"))

class TimelineClipPayload(BaseModel):
    filename: str
    stem_type: str
    start_offset_seconds: float
    audio_start_offset_seconds: float = 0.0
    duration_seconds: float | None = None
    key_signature: str | None = None

class MixMatrixPayload(BaseModel):
    clips: List[TimelineClipPayload]

@router.post("/mix")
async def render_mashup_matrix(payload: MixMatrixPayload, session_cache: str = Depends(get_session_cache_dir)):
    if not payload.clips:
        raise HTTPException(status_code=400, detail="Timeline grid layout matrix is empty.")

    TARGET_SR = 22050 
    source_bpms = []
    valid_clips = []

    for clip in payload.clips:
        file_path = os.path.join(session_cache, clip.filename)
        if not os.path.exists(file_path): continue
        valid_clips.append(clip)

        try:
            y, sr = librosa.load(file_path, sr=TARGET_SR)
            onset_env = librosa.onset.onset_strength(y=y, sr=sr)
            bpm = float(librosa.feature.tempo(onset_envelope=onset_env, sr=sr)[0])
            if bpm > 0: source_bpms.append(bpm)
        except Exception: pass

    TARGET_BPM = round(sum(source_bpms) / len(source_bpms), 1) if source_bpms else 120.0
    processed_tracks = []
    max_length = 0

    for clip in valid_clips:
        file_path = os.path.join(session_cache, clip.filename)
        y_aligned = process_and_align_stem(file_path, TARGET_BPM, clip.start_offset_seconds, clip.audio_start_offset_seconds, TARGET_SR)

        if clip.duration_seconds is not None and clip.duration_seconds > 0:
            target_samples = int(clip.duration_seconds * TARGET_SR)
            if target_samples < len(y_aligned): y_aligned = y_aligned[:target_samples]

        processed_tracks.append(y_aligned)
        if len(y_aligned) > max_length: max_length = len(y_aligned)

    if not processed_tracks:
        raise HTTPException(status_code=404, detail="No source audio files found to mix down.")

    master_mix = np.zeros(max_length, dtype=np.float32)
    for track in processed_tracks: master_mix[:len(track)] += track

    max_peak = np.max(np.abs(master_mix))
    if max_peak > 1.0: master_mix /= max_peak

    output_filename = "master_mashup_mix.wav"
    output_path = os.path.join(OUTPUT_DIR, output_filename)
    sf.write(output_path, master_mix, TARGET_SR)

    return {
        "success": True,
        "message": f"Mashup compiled successfully at optimal {TARGET_BPM} BPM!",
        "downloadUrl": f"/mixes/{output_filename}" 
    }