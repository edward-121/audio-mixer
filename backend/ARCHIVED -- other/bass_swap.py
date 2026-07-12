import os
import sys
from pydub import AudioSegment

# --- PYTHON 3.14 COMPATIBILITY PATTERNS ---
try:
    import audioop
except ImportError:
    import audioop_lts as audioop
    sys.modules['audioop'] = audioop
    sys.modules['pyaudioop'] = audioop
# ------------------------------------------

def bass_swap_transition(song_a_path, song_b_path, output_path, crossfade_seconds=10):
    """
    Surgically separates low-end bass from high/mid frequencies.
    Crossfades vocals and instruments smoothly, but snaps the bassline instantly
    to prevent muddy frequency interference.
    """
    print(f"📁 [Bass Swap] Loading Song A: {os.path.basename(song_a_path)}...")
    song_a = AudioSegment.from_file(song_a_path)
    
    print(f"📁 [Bass Swap] Loading Song B: {os.path.basename(song_b_path)}...")
    song_b = AudioSegment.from_file(song_b_path)
    
    fade_ms = crossfade_seconds * 1000
    
    # 1. Isolate the final segment of Song A and the starting segment of Song B
    song_a_main = song_a[:-fade_ms]
    song_a_mix_zone = song_a[-fade_ms:]
    
    song_b_mix_zone = song_b[:fade_ms]
    song_b_main = song_b[fade_ms:]
    
    print("✂️ Splitting audio into frequency bands (Low-Pass & High-Pass filters)...")
    # 2. Filter Song A's mix zone (Keep the bass bumping, fade out the vocals/melodies)
    # 250 Hz is the standard acoustic crossover point for bass frequencies
    a_bass = song_a_mix_zone.low_pass_filter(250) 
    a_mids_highs = song_a_mix_zone.high_pass_filter(250).fade_out(duration=fade_ms)
    
    # 3. Filter Song B's mix zone (Fade in the vocals/melodies, completely KILL the bass)
    b_bass = song_b_mix_zone.low_pass_filter(250) - 120  # Mute bass completely using clean decibel subtraction
    b_mids_highs = song_b_mix_zone.high_pass_filter(250).fade_in(duration=fade_ms)
    
    print("🎛️ Executing the switch (Crossfading Mids/Highs + Swapping Basslines)...")
    # 4. Blend the Highs and Mids together smoothly
    blended_mids_highs = a_mids_highs.overlay(b_mids_highs)
    
    # 5. Keep Song A's bass running at 100% until the absolute final millisecond, then drop it
    # We overlay the blended melodies on top of Song A's solid bass framework
    completed_transition_zone = blended_mids_highs.overlay(a_bass)
    
    # 6. Reconstruct the entire track timeline
    # [Song A Main] -> [Transition Zone with Song A Bass & Blended Vocals] -> [Song B Main drops with full Bass]
    final_mix = song_a_main + completed_transition_zone + song_b_main
    
    print(f"💾 Exporting premium seamless mix to {output_path}...")
    final_mix.export(output_path, format="mp3")
    print("🎉 Done! Bass-Swap transition completed successfully.")