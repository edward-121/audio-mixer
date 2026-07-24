import os
import shutil
import subprocess
import urllib.parse
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from pathlib import Path
from app.dependencies import get_session_cache_dir
from app.services.audio_processing import (
    load_cached_metadata_from_path,     
    save_cached_metadata_from_path,    
    get_audio_duration,
    analyze_audio_properties_with_timeout, 
    enqueue_metadata_analysis, 
    make_unique_cache_path
)

router = APIRouter(prefix="/api", tags=["stems"])

BASE_DIR = Path(__file__).resolve().parent.parent.parent
CACHE_DIR = os.environ.get("CACHE_DIR", str(BASE_DIR / "stem_cache"))

def run_demucs_splitter(song_path, cache_dir):
    os.environ["TORCHAUDIO_BACKEND"] = "soundfile"
    base_filename = os.path.basename(song_path)
    song_name = os.path.splitext(base_filename)[0].replace(" ", "_")
    demucs_output_dir = os.path.join("separated", "htdemucs", song_name)

    stem_types = ["vocals", "bass", "drums", "other"]
    final_flat_stems = {s_type: os.path.join(cache_dir, f"{song_name}_{s_type}.wav") for s_type in stem_types}

    if os.path.exists(final_flat_stems["vocals"]): return True

    user_profile = os.environ.get("USERPROFILE", "C:\\Users\\default")
    demucs_path = os.path.join(user_profile, ".local", "bin", "demucs.exe")
    if not os.path.exists(demucs_path):
        demucs_path = os.path.join(os.environ.get("APPDATA", ""), "Python", "Scripts", "demucs.exe")
    if not os.path.exists(demucs_path): demucs_path = "demucs"

    try:
        subprocess.run([demucs_path, song_path], check=True)
        for stem_name, destination_path in final_flat_stems.items():
            source_path = os.path.join(demucs_output_dir, f"{stem_name}.wav")
            if os.path.exists(source_path): shutil.move(source_path, destination_path)
        if os.path.exists("separated"): shutil.rmtree("separated")
        return True
    except Exception: return False

@router.post("/upload/song")
async def upload_full_song(file: UploadFile = File(...), session_cache: str = Depends(get_session_cache_dir)):
    if not file.filename.lower().endswith((".wav", ".mp3", ".ogg")):
        raise HTTPException(status_code=400, detail="Unsupported audio file format.")
    clean_filename = file.filename.replace(" ", "_")
    temp_upload_path = os.path.join(session_cache, clean_filename)
    try:
        with open(temp_upload_path, "wb") as buffer: buffer.write(await file.read())
        if not run_demucs_splitter(temp_upload_path, cache_dir=session_cache):
            raise HTTPException(status_code=500, detail="Demucs engine failed.")
        if os.path.exists(temp_upload_path): os.remove(temp_upload_path)
        return {"success": True, "message": "Song successfully isolated into private session stems!"}
    except Exception as e:
        if os.path.exists(temp_upload_path): os.remove(temp_upload_path)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stems")
async def get_available_stems(session_cache: str = Depends(get_session_cache_dir)):
    stems = []
    files = [f for f in os.listdir(session_cache) if f.lower().endswith((".wav", ".mp3", ".ogg"))]
    
    print(f"🔍 [GET STEMS] Scanning session cache folder: {session_cache} (Found {len(files)} tracks)")

    for idx, filename in enumerate(files):
        file_path = os.path.join(session_cache, filename)
        
        # Load cache using the unique full file path
        cached_metadata = load_cached_metadata_from_path(file_path)
        
        name_lower = filename.lower()
        stem_type = "vocals" if "vocal" in name_lower or "vox" in name_lower else "drums" if "drum" in name_lower or "beat" in name_lower else "bass" if "bass" in name_lower else "other"
        base_name = filename.replace("_", " ").split(".")[0]
        
        stems.append({
            "id": f"real_{idx}", 
            "song_name": base_name.title(), 
            "stem_type": stem_type,
            "duration_seconds": get_audio_duration(file_path), 
            "filename": filename,
            "bpm": cached_metadata.get("bpm", 120.0) if cached_metadata else 120.0,
            "key": cached_metadata.get("key", "C") if cached_metadata else "C",
            "onset_offset_seconds": cached_metadata.get("onset_offset_seconds", 0.0) if cached_metadata else 0.0
        })
    return stems

@router.post("/upload")
async def upload_audio_stem(file: UploadFile = File(...), session_cache: str = Depends(get_session_cache_dir)):
    clean_filename = file.filename.replace(" ", "_")
    destination_path = make_unique_cache_path(clean_filename, cache_dir=session_cache)
    saved_filename = os.path.basename(destination_path)
    
    print(f"[UPLOAD STEM] Storing {saved_filename} inside session subfolder...")
    try:
        with open(destination_path, "wb") as buffer: 
            buffer.write(await file.read())
        
        # Run calculation with 8-second limit
        bpm, key_sig, onset_offset_seconds = analyze_audio_properties_with_timeout(destination_path, timeout_seconds=8)
        
        # 🚀 CHANGE: Only write to cache immediately if the computation actually finished (didn't fall back to exactly 120/C)
        if bpm != 120.0 or key_sig != "C" or onset_offset_seconds != 0.0:
            save_cached_metadata_from_path(destination_path, bpm, key_sig, onset_offset_seconds)
        
        # Always trigger the background thread to handle timeouts or double-check the values
        enqueue_metadata_analysis(destination_path)
        
        return {
            "success": True, 
            "filename": saved_filename, 
            "bpm": bpm, 
            "key": key_sig, 
            "onset_offset_seconds": onset_offset_seconds
        }
    except Exception as e:
        print(f"[UPLOAD ERROR] Direct stem processing failed: {e}")
        if os.path.exists(destination_path): os.remove(destination_path)
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/stems/group/{song_name}")
async def delete_stem_group(
    song_name: str, 
    session_cache: str = Depends(get_session_cache_dir)
):
    """Deletes all stems, full audio files, and metadata JSON files matching a song name."""
    decoded_query = urllib.parse.unquote(song_name).strip().lower()
    clean_query = decoded_query.replace("_", " ").replace("-", " ")
    
    print(f"[DELETE GROUP] Target directory: {session_cache}")
    print(f"[DELETE GROUP] Request received to remove tracks matching: '{song_name}' (Cleaned: '{clean_query}')")
    deleted_count = 0
    
    if os.path.exists(session_cache):
        files = os.listdir(session_cache)
        print(f"[DELETE GROUP] Files currently in session directory: {files}")

        for file in files:
            file_lower = file.lower()
            # Strip known extensions cleanly
            base_filename = (
                file_lower.replace(".meta.json", "")
                .replace(".mp3", "")
                .replace(".wav", "")
                .replace(".ogg", "")
                .replace("_", " ")
                .replace("-", " ")
            )

            if clean_query in base_filename:
                file_path = os.path.join(session_cache, file)
                try:
                    os.remove(file_path)
                    deleted_count += 1
                    print(f"  └─ 🗑️ Deleted file: {file}")
                except Exception as e:
                    print(f"[DELETE ERROR] Could not remove {file}: {e}")

    print(f"[DELETE GROUP] Finished. Total files removed: {deleted_count}")

    import sys
    main_mod = sys.modules.get("main") or sys.modules.get("app.main")
    if main_mod and hasattr(main_mod, "notify_clients_stems_updated"):
        main_mod.notify_clients_stems_updated()

    return {"success": True, "deleted_count": deleted_count}

@router.delete("/api/stems/all")
async def clear_all_session_stems(
    session_cache: str = Depends(get_session_cache_dir)
):
    """Wipes all files inside the active user's session cache directory."""
    deleted_count = 0

    if os.path.exists(session_cache):
        for item in os.listdir(session_cache):
            item_path = os.path.join(session_cache, item)
            try:
                if os.path.isfile(item_path) or os.path.islink(item_path):
                    os.unlink(item_path)
                    deleted_count += 1
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                    deleted_count += 1
            except Exception as e:
                print(f"[CLEAR ALL ERROR] Failed to delete {item_path}: {e}")

    return {"success": True, "deleted_count": deleted_count}