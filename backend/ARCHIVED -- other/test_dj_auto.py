import os
import sys
import librosa
import soundfile as sf
import numpy as np

# Bring in your backend modules cleanly
from backend.mashup.splitter import split_song_stems
from backend.mashup.audio_processor import align_and_match_stems

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def main():
    clear_screen()
    print("=========================================")
    print("        🎚️ AUTO-DJ MIXER CONSOLE 🎚️        ")
    print("=========================================")
    print("Select your engine mode:")
    print("1) Classic Crossfade (Simple Volume Blend)")
    print("2) Advanced Bass-Swap (Seamless Frequency Split)")
    print("3) Custom Mashup Engine (Instrument & Stem Blender) 🌟")
    print("=========================================")
    
    choice = input("Enter option (1, 2, or 3): ").strip()
    
    if choice != "3":
        print("➡️ Running standard mode... (add your legacy crossfade/bass-swap triggers here)")
        return

    # --- CUSTOM MASHUP ENGINE PIPELINE ---
    print("\n🚀 Processing local AI mashup request...")
    print("----------------------------------------")
    
    # 1. Identify the files sitting in your project root folder
    tracks = ["clean_bandit.mp3", "savage.mp3", "bones.mp3", "industry_baby.mp3", "earth.mp3"]
    # Filter out anything missing just in case
    available_tracks = [t for t in tracks if os.path.exists(t)]
    
    if len(available_tracks) < 2:
        print("❌ Error: You need at least 2 tracks to run this engine!")
        return

    # 2. Assign channels on the mixing board
    print("\n=========================================")
    print("        🎛️ 3-CHANNEL STEM MIXING BOARD     ")
    print("=========================================")
    for i, track in enumerate(available_tracks, 1):
        print(f"{i}) {track}")
        
    v_idx = int(input("\n🎤 Which song for VOCALS?: ")) - 1
    b_idx = int(input("🎸 Which song for BASS?: ")) - 1
    i_idx = int(input("🎹 Which song for OTHER INSTRUMENTS & DRUMS?: ")) - 1

    vocal_song = available_tracks[v_idx]
    bass_song = available_tracks[b_idx]
    inst_song = available_tracks[i_idx]

    print("\n⚡ STEP 1: Extracting all elements via Local AI...")
    v_stems = split_song_stems(vocal_song)
    b_stems = split_song_stems(bass_song)
    i_stems = split_song_stems(inst_song)

    print("\n📊 STEP 2: Analyzing Native Tempos & Optimizing Target Grid Speed...")
    try:
        print("⏳ Scanning source track tempos...")
        y_v_raw, sr_v = librosa.load(v_stems["vocals"], duration=60, sr=None)
        y_b_raw, sr_b = librosa.load(b_stems["bass"], duration=60, sr=None)
        y_i_raw, sr_i = librosa.load(i_stems["other"], duration=60, sr=None)

        # Clean modern tempo features (Fixes the yellow warning text!)
        # Update your three scan lines to look exactly like this:
        bpm_v = librosa.feature.tempo(onset_envelope=librosa.onset.onset_strength(y=y_v_raw, sr=sr_v), sr=sr_v)[0]
        bpm_b = librosa.feature.tempo(onset_envelope=librosa.onset.onset_strength(y=y_b_raw, sr=sr_b), sr=sr_b)[0]
        bpm_i = librosa.feature.tempo(onset_envelope=librosa.onset.onset_strength(y=y_i_raw, sr=sr_i), sr=sr_i)[0]

        print(f"🎵 Detected Source Tempos: Vocals={bpm_v:.1f} BPM | Bass={bpm_b:.1f} BPM | Melodies={bpm_i:.1f} BPM")

        # Mathematically calculate the optimized median target speed
        optimized_target_bpm = float(np.median([bpm_v, bpm_b, bpm_i]))
        print(f"🎯 Optimized Master Grid Speed Chosen: {optimized_target_bpm:.1f} BPM")

    except Exception as e:
        print(f"⚠️ Tempo optimization failed, defaulting to 120 BPM. Error: {e}")
        optimized_target_bpm = 120.0

    print("\n🎚️ STEP 2b: Time-stretching elements to the optimized master grid...")
    aligned_vocals = os.path.join("stem_cache", "tmp_aligned_vocals.wav")
    aligned_bass = os.path.join("stem_cache", "tmp_aligned_bass.wav")
    aligned_inst = os.path.join("stem_cache", "tmp_aligned_inst.wav")
    aligned_drums = os.path.join("stem_cache", "tmp_aligned_drums.wav")

    # 🚀 FIX: We pass optimized_target_bpm directly as the second parameter now!
    align_and_match_stems(v_stems["vocals"], optimized_target_bpm, aligned_vocals, semitone_shift=0)
    align_and_match_stems(b_stems["bass"], optimized_target_bpm, aligned_bass, semitone_shift=0)
    align_and_match_stems(i_stems["other"], optimized_target_bpm, aligned_inst, semitone_shift=0)
    align_and_match_stems(i_stems["drums"], optimized_target_bpm, aligned_drums, semitone_shift=0)

    print("\n🎯 STEP 3: Automated Energy Scanning & Auto-Drop Alignment...")
    try:
        # Load time-aligned arrays
        y_vocals, sr = librosa.load(aligned_vocals, sr=None)
        y_bass, _ = librosa.load(aligned_bass, sr=sr)
        y_inst, _ = librosa.load(aligned_inst, sr=sr)
        y_drums, _ = librosa.load(aligned_drums, sr=sr)

        print("⏳ Mapping beat grids...")
        tempo_inst, beat_samples_inst = librosa.beat.beat_track(y=y_drums, sr=sr, units='samples')
        tempo_voc, beat_samples_voc = librosa.beat.beat_track(y=y_vocals, sr=sr, units='samples')

        # --- 🤖 AUTOMATED BEAT DROP DETECTION CODE ---
        print("⚡ Scanning instrumental track for the ultimate beat drop...")
        # 1. Compute short-term energy (loudness profile) across the instrumental track
        hop_length = 512
        rmse_inst = librosa.feature.rms(y=y_drums, hop_length=hop_length)[0]
        
        # 2. Find where the volume increases the fastest (the massive drop transient)
        energy_diff = np.diff(rmse_inst)
        max_diff_frame = np.argmax(energy_diff)
        auto_drop_sample = max_diff_frame * hop_length
        
        # 3. Snap that sample to the nearest actual grid beat so it stays perfectly on time
        closest_inst_beat_idx = np.argmin(np.abs(beat_samples_inst - auto_drop_sample))
        inst_drop_sample = beat_samples_inst[closest_inst_beat_idx]
        
        # 4. Do the same for vocals: find the loudest section (the chorus) to place on the drop
        rmse_voc = librosa.feature.rms(y=y_vocals, hop_length=hop_length)[0]
        max_voc_frame = np.argmax(rmse_voc)
        auto_vocal_sample = max_voc_frame * hop_length
        closest_voc_beat_idx = np.argmin(np.abs(beat_samples_voc - auto_vocal_sample))
        vocal_drop_sample = beat_samples_voc[closest_voc_beat_idx]

        print(f"✨ Auto-Detected Instrumental Drop at: {inst_drop_sample / sr:.2f} seconds (Beat {closest_inst_beat_idx + 1})")
        print(f"✨ Auto-Detected Vocal Chorus Drop at: {vocal_drop_sample / sr:.2f} seconds (Beat {closest_voc_beat_idx + 1})")

        # Calculate the alignment offset matrix
        sample_offset = inst_drop_sample - vocal_drop_sample

        if sample_offset > 0:
            y_vocals = np.pad(y_vocals, (sample_offset, 0), mode='constant')
        elif sample_offset < 0:
            pad_size = abs(sample_offset)
            y_bass = np.pad(y_bass, (pad_size, 0), mode='constant')
            y_inst = np.pad(y_inst, (pad_size, 0), mode='constant')
            y_drums = np.pad(y_drums, (pad_size, 0), mode='constant')

        # Equalize array sizes for mixing
        max_len = max(len(y_vocals), len(y_bass), len(y_inst), len(y_drums))
        y_vocals = np.pad(y_vocals, (0, max_len - len(y_vocals)), mode='constant')
        y_bass = np.pad(y_bass, (0, max_len - len(y_bass)), mode='constant')
        y_inst = np.pad(y_inst, (0, max_len - len(y_inst)), mode='constant')
        y_drums = np.pad(y_drums, (0, max_len - len(y_drums)), mode='constant')

        # Blend channels together
        final_mix = (y_vocals * 0.4) + (y_bass * 0.2) + (y_inst * 0.2) + (y_drums * 0.2)

        if np.max(np.abs(final_mix)) > 0:
            final_mix = final_mix / np.max(np.abs(final_mix))

        output_filename = "fortnite_autodrop_mashup.mp3"
        sf.write(output_filename, final_mix, sr)

        for f in [aligned_vocals, aligned_bass, aligned_inst, aligned_drums]:
            if os.path.exists(f): os.remove(f)

        print(f"\n🎉 Fortnite Festival Mode Active! AI locked the beat drop completely hands-free: {output_filename}")

    except Exception as e:
        print(f"❌ Failed to auto-align beat-grids. Details: {e}")

if __name__ == "__main__":
    main()