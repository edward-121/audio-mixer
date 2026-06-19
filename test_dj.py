import os
from backend.engine import smooth_transition
from backend.bass_swap import bass_swap_transition

# Import your new multi-file mashup modules!
from backend.mashup.splitter import split_song_stems
from backend.mashup.blender import create_mashup

SONG_A = "clean_bandit.mp3"
SONG_B = "savage.mp3"

if __name__ == "__main__":
    if not os.path.exists(SONG_A) or not os.path.exists(SONG_B):
        print(f"\n❌ Error: Missing files. Please make sure '{SONG_A}' and '{SONG_B}' are in this directory.")
        exit()

    print("\n=========================================")
    print("       🎚️ AUTO-DJ MIXER CONSOLE 🎚️       ")
    print("=========================================")
    print("Select your engine mode:")
    print("1) Classic Crossfade (Simple Volume Blend)")
    print("2) Advanced Bass-Swap (Seamless Frequency Split)")
    print("3) Custom Mashup Engine (Instrument & Stem Blender) 🌟")
    print("=========================================")
    
    choice = input("Enter option (1, 2, or 3): ").strip()
    
    print("\n🚀 Processing request...")
    print("-" * 40)
    
    if choice == "1":
        OUTPUT_MIX = "classic_crossfade_mix.mp3"
        smooth_transition(SONG_A, SONG_B, OUTPUT_MIX, crossfade_seconds=10)
        print(f"\n✅ Success! Created: {OUTPUT_MIX}")
        
    elif choice == "2":
        OUTPUT_MIX = "premium_bass_swap_mix.mp3"
        bass_swap_transition(SONG_A, SONG_B, OUTPUT_MIX, crossfade_seconds=10)
        print(f"\n✅ Success! Created: {OUTPUT_MIX}")
        
    elif choice == "3":
        print("⚡ STEP 1: Pre-processing tracks through the folder splitter...")
        # Split both tracks into their respective directories
        stems_a = split_song_stems(SONG_A)
        stems_b = split_song_stems(SONG_B)
        
        print("\n=========================================")
        print("         🎤 MASHUP MIXING BOARD          ")
        print("=========================================")
        print(f"Which song should provide the VOCALS?")
        print(f"1) {SONG_A}")
        print(f"2) {SONG_B}")
        v_choice = input("Choice (1 or 2): ").strip()
        
        print(f"\nWhich song should provide the BASS & INSTRUMENTS?")
        print(f"1) {SONG_A}")
        print(f"2) {SONG_B}")
        i_choice = input("Choice (1 or 2): ").strip()
        
        # Build our custom mapping based on your menu answers
        custom_map = {
            "vocals": stems_a["vocals"] if v_choice == "1" else stems_b["vocals"],
            "bass": stems_a["bass"] if i_choice == "1" else stems_b["bass"],
            "drums": stems_a["drums"] if i_choice == "1" else stems_b["drums"],
            "other": stems_a["other"] if i_choice == "1" else stems_b["other"]
        }
        
        OUTPUT_MIX = "custom_mashup_output.mp3"
        create_mashup(custom_map, OUTPUT_MIX)
        print(f"\n✅ Success! Go check your root folder for: {OUTPUT_MIX}")
        
    else:
        print("❌ Invalid selection. Please enter '1', '2', or '3'.")