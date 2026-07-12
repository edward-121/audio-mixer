import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

BASE_DIR = Path(__file__).resolve().parent.parent
CACHE_DIR = os.environ.get("CACHE_DIR", str(BASE_DIR / "stem_cache"))
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", str(BASE_DIR / "output_mixes"))

os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

analysis_executor = ThreadPoolExecutor(max_workers=1)
PITCH_CLASSES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']