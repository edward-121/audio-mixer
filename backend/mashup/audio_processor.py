import os
import librosa
import soundfile as sf
import numpy as np

def align_and_match_stems(vocal_path, target_bpm, output_vocal_path, semitone_shift=0):
    """
    Stretches a vocal/stem track to precisely match a calculated numerical target BPM.
    """
    print(f"⏳ Loading stem for alignment: {os.path.basename(vocal_path)}")
    y_voc, sr_voc = librosa.load(vocal_path, sr=None)
    
    # Clean, warning-free native tempo detection
    onset_env_voc = librosa.onset.onset_strength(y=y_voc, sr=sr_voc)
# Change this:
# source_bpm = librosa.feature.rhythm.tempo(onset_envelope=onset_env_voc, sr=sr_voc)[0]

# To this:
    source_bpm = librosa.feature.tempo(onset_envelope=onset_env_voc, sr=sr_voc)[0]
    
    # Calculate the precise time-stretch ratio
    stretch_ratio = target_bpm / source_bpm
    
    # Time-stretch
    y_processed = librosa.effects.time_stretch(y_voc, rate=stretch_ratio)
    
    # Pitch-shift if requested
    if semitone_shift != 0:
        y_processed = librosa.effects.pitch_shift(y_processed, sr=sr_voc, n_steps=semitone_shift)
        
    # Ensure folder path exists and save
    os.makedirs(os.path.dirname(output_vocal_path), exist_ok=True)
    sf.write(output_vocal_path, y_processed, sr_voc)
    print(f"✅ Generated: {output_vocal_path} ({source_bpm:.1f} BPM -> {target_bpm:.1f} BPM)")