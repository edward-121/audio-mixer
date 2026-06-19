import os
import sys
from pydub import AudioSegment

# --- PYTHON 3.14 COMPATIBILITY ---
try:
    import audioop
except ImportError:
    import audioop_lts as audioop
    sys.modules['audioop'] = audioop
    sys.modules['pyaudioop'] = audioop
# ----------------------------------

def create_mashup(stem_map, output_path):
    """
    Combines individual audio stems into a single mashed-up track
    while applying automatic gain management to prevent destructive distortion.
    """
    combined_track = None
    
    print("\n🎛️  Assembling your custom mashup elements...")
    
    for stem_type, file_path in stem_map.items():
        if not file_path or not os.path.exists(file_path):
            print(f"⚠️  Skipping {stem_type}: No file found at {file_path}")
            continue
            
        print(f"File raw path: {file_path}")
        stem_audio = AudioSegment.from_file(file_path)
        
        # 🛡️ ANTI-DISTORTION LOGIC 🛡️
        # Bring down the gain of each incoming track by default so they don't fight.
        # Vocals need to cut through, so we lower instruments slightly more.
        if stem_type == "vocals":
            # Give vocals a clear pocket in the mix
            target_gain = -3.0  
        else:
            # Drop backing tracks (bass/drums/melody) slightly lower to fit together
            target_gain = -6.0
            
        # Adjust the track relative to its current native loudness
        gain_adjustment = target_gain - stem_audio.dBFS
        stem_audio = stem_audio.apply_gain(gain_adjustment)
        
        # If this is our first layer, establish our mix timeline
        if combined_track is None:
            combined_track = stem_audio
        else:
            # Overlay smoothly at timestamp 0
            combined_track = combined_track.overlay(stem_audio, position=0)
            
    if combined_track is None:
        print("❌ Error: No valid audio files were layered.")
        return False

    # 🛡️ FINAL SAFEGUARD: Peak Normalization
    # If the combined track still manages to peek over -1.0 dBFS, 
    # compress it slightly down to prevent any physical speaker distortion.
    if combined_track.max_dBFS > -1.0:
        print("🎚️ Limiter Engaged: Adjusting master volume to prevent clipping...")
        combined_track = combined_track.normalize(headroom=1.5)

    print(f"💾 Exporting custom stabilized mix to {output_path}...")
    combined_track.export(output_path, format="mp3")
    print("🎉 Done! Your balanced mashup is ready.")
    return True