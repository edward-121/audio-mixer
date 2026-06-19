import os
import subprocess
import shutil

def split_song_stems(song_path, cache_dir="stem_cache"):
    """
    Runs Meta's Demucs AI completely locally on your machine.
    Forces the use of the reliable soundfile backend globally.
    """
    # 🛡️ THE WINDOWS PYTHON 3.14 FIX: Force the global audio backend to soundfile
    os.environ["TORCHAUDIO_Backend"] = "soundfile"
    
    base_filename = os.path.basename(song_path)
    song_name = os.path.splitext(base_filename)[0]
    
    # ... (rest of your existing splitter.py code stays exactly the same)
    # 🛡️ THE ULTIMATE TORCHAUDIO PATCH FOR WINDOWS
    try:
        import torchaudio
        # Force torchaudio to completely forget torchcodec exists
        if hasattr(torchaudio, "_torchcodec") or hasattr(torchaudio, "save_with_torchcodec"):
            print("🔧 [Patch] Redirecting torchaudio save mechanics to standard soundfile backends...")
            # Override the broken internal function with standard soundfile save routine
            import torchaudio._soundfile as ta_sf
            torchaudio.save = ta_sf.save
    except Exception as e:
        # If it fails here, it's fine; demucs will try to handle it internally
        pass

    base_filename = os.path.basename(song_path)
    song_name = os.path.splitext(base_filename)[0]
    
    demucs_output_dir = os.path.join("separated", "htdemucs", song_name)
    final_target_dir = os.path.join(cache_dir, song_name)
    
    stems = {
        "vocals": os.path.join(final_target_dir, "vocals.wav"),
        "bass": os.path.join(final_target_dir, "bass.wav"),
        "drums": os.path.join(final_target_dir, "drums.wav"),
        "other": os.path.join(final_target_dir, "other.wav")
    }
    
    if os.path.exists(stems["vocals"]):
        print(f"📦 [Local AI] Found cached stems for '{song_name}'. Skipping computation!")
        return stems
        
    print(f"\n🧠 [Local AI] Initializing Demucs Neural Network for '{song_name}'...")
    
    user_profile = os.environ.get("USERPROFILE", "C:\\Users\\default")
    demucs_path = os.path.join(user_profile, ".local", "bin", "demucs.exe")

    if not os.path.exists(demucs_path):
        demucs_path = os.path.join(os.environ.get("APPDATA", ""), "Python", "Scripts", "demucs.exe")
    
    if not os.path.exists(demucs_path):
        demucs_path = "demucs"

    command = [
        demucs_path,
        song_path
    ]
    
    try:
        subprocess.run(command, check=True)
        
        os.makedirs(final_target_dir, exist_ok=True)
        
        print(f"🚚 Moving files from '{demucs_output_dir}' to '{final_target_dir}'...")
        
        for stem_name, destination_path in stems.items():
            source_path = os.path.join(demucs_output_dir, f"{stem_name}.wav")
            if os.path.exists(source_path):
                shutil.move(source_path, destination_path)
            else:
                print(f"⚠️ Warning: Could not find expected AI stem at {source_path}")
        
        if os.path.exists("separated"):
            shutil.rmtree("separated")
            
        print("✨ Extraction and folder organization complete!")
        
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"❌ Error: Local AI failed to run. Details: {e}")
        
    return stems