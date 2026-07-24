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

    print("\n🎧 STEP 2: Time-stretching elements to match the instrument anchor...")
    anchor_track = i_stems["other"]
    
    aligned_vocals = os.path.join("stem_cache", "tmp_aligned_vocals.wav")
    aligned_bass = os.path.join("stem_cache", "tmp_aligned_bass.wav")
    aligned_inst = os.path.join("stem_cache", "tmp_aligned_inst.wav")
    aligned_drums = os.path.join("stem_cache", "tmp_aligned_drums.wav")

    # Warp the tempos first so the beat grids have identical spacing
    align_and_match_stems(v_stems["vocals"], anchor_track, aligned_vocals, semitone_shift=0)
    align_and_match_stems(b_stems["bass"], anchor_track, aligned_bass, semitone_shift=0)
    align_and_match_stems(i_stems["other"], anchor_track, aligned_inst, semitone_shift=0)
    align_and_match_stems(i_stems["drums"], anchor_track, aligned_drums, semitone_shift=0)

    print("\n🎯 STEP 3: Beat-Grid Mapping & Drop Alignment...")
    try:
        # Load time-aligned arrays
        y_vocals, sr = librosa.load(aligned_vocals, sr=None)
        y_bass, _ = librosa.load(aligned_bass, sr=sr)
        y_inst, _ = librosa.load(aligned_inst, sr=sr)
        y_drums, _ = librosa.load(aligned_drums, sr=sr)

        print("⏳ Analyzing downbeats and transient grids...")
        # Automatically detect the exact timing of every beat (returns sample indices)
        tempo_inst, beat_samples_inst = librosa.beat.beat_track(y=y_drums, sr=sr, units='samples')
        tempo_voc, beat_samples_voc = librosa.beat.beat_track(y=y_vocals, sr=sr, units='samples')

        total_inst_beats = len(beat_samples_inst)
        total_voc_beats = len(beat_samples_voc)

        print(f"📊 Track Grid: Detected {total_inst_beats} beats in the instrumental background.")
        print(f"📊 Vocal Grid: Detected {total_voc_beats} beats in the vocal track.")

        # Ask the user which beat numbers should lock together for the drop
        print("\n⚡ CONFIGURING THE BEAT DROP ⚡")
        print("Example: If the beat drops at beat 32 of the instrumental, and the vocal chorus starts at vocal beat 16, type 32 and 16.")
        inst_drop_beat = int(input(f"Which instrumental beat is the DROP? (1-{total_inst_beats}): ") or 1) - 1
        vocal_drop_beat = int(input(f"Which vocal beat lands ON the drop? (1-{total_voc_beats}): ") or 1) - 1

        # Get the precise audio frame index for those target beats
        inst_drop_sample = beat_samples_inst[inst_drop_beat]
        vocal_drop_sample = beat_samples_voc[vocal_drop_beat]

        # Calculate the positional shift difference
        # If difference is positive, vocals need silence padded at the front.
        # If negative, the vocals need to start *before* the instrumental.
        sample_offset = inst_drop_sample - vocal_drop_sample

        if sample_offset > 0:
            # Pad the front of the vocals with silence to push them back to line up with the drop
            y_vocals = np.pad(y_vocals, (sample_offset, 0), mode='constant')
        elif sample_offset < 0:
            # Pad the front of the instrumentals/bass if the vocals need to hit first
            pad_size = abs(sample_offset)
            y_bass = np.pad(y_bass, (pad_size, 0), mode='constant')
            y_inst = np.pad(y_inst, (pad_size, 0), mode='constant')
            y_drums = np.pad(y_drums, (pad_size, 0), mode='constant')

        # Equalize array sizes for the final matrix merge
        max_len = max(len(y_vocals), len(y_bass), len(y_inst), len(y_drums))
        y_vocals = np.pad(y_vocals, (0, max_len - len(y_vocals)), mode='constant')
        y_bass = np.pad(y_bass, (0, max_len - len(y_bass)), mode='constant')
        y_inst = np.pad(y_inst, (0, max_len - len(y_inst)), mode='constant')
        y_drums = np.pad(y_drums, (0, max_len - len(y_drums)), mode='constant')

        # Combine into master matrix
        final_mix = (y_vocals * 0.4) + (y_bass * 0.2) + (y_inst * 0.2) + (y_drums * 0.2)

        # Normalize audio levels
        if np.max(np.abs(final_mix)) > 0:
            final_mix = final_mix / np.max(np.abs(final_mix))

        output_filename = "festival_drop_mashup.mp3"
        sf.write(output_filename, final_mix, sr)

        for f in [aligned_vocals, aligned_bass, aligned_inst, aligned_drums]:
            if os.path.exists(f): os.remove(f)

        print(f"\n🎉 Perfect Grid Match! The beat drop is perfectly locked. Output: {output_filename}")

    except Exception as e:
        print(f"❌ Failed to align beat-grids. Details: {e}")

if __name__ == "__main__":
    main()