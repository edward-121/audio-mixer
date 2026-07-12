import os
from pydub import AudioSegment

def smooth_transition(song_a_path, song_b_path, output_path, crossfade_seconds=10):
    """
    Takes two audio files and blends them together seamlessly using 
    a logarithmic, interference-free crossfade.
    """
    print(f"📁 Loading Song A: {os.path.basename(song_a_path)}...")
    song_a = AudioSegment.from_file(song_a_path)
    
    print(f"📁 Loading Song B: {os.path.basename(song_b_path)}...")
    song_b = AudioSegment.from_file(song_b_path)
    
    # Convert seconds to milliseconds for Pydub
    fade_duration_ms = crossfade_seconds * 1000
    
    print(f"🎛️ Blending tracks with a {crossfade_seconds}-second smooth crossfade...")
    
    # The append operator (+) with a 'crossfade' argument automatically calculates
    # the equal-power logarithmic fade between the end of Song A and start of Song B.
    # This prevents the volume dip or overlapping distortion.
    combined_mix = song_a.append(song_b, crossfade=fade_duration_ms)
    
    print(f"💾 Exporting the clean mix to {output_path}...")
    combined_mix.export(output_path, format="mp3")
    print("🎉 Done! Your smooth mix is ready.")

if __name__ == "__main__":

    TRACK_1 = "bones.mp3"
    TRACK_2 = "savage.mp3"
    FINAL_OUTPUT = "smooth_blend_output.mp3"
    
    if os.path.exists(TRACK_1) and os.path.exists(TRACK_2):
        # Let's do a generous 8-second smooth transition
        smooth_transition(TRACK_1, TRACK_2, FINAL_OUTPUT, crossfade_seconds=8)
    else:
        # FIXED: Now prints the actual missing file names dynamically
        print(f"\n❌ Error: Please make sure both '{TRACK_1}' and '{TRACK_2}' are placed in this folder to test.")