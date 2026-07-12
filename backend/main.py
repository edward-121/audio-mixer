# backend/main.py
import os
os.environ["MUTAGEN_NO_WARNINGS"] = "1"
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Import your sub-routers
from app.routers import stems, mix

BASE_DIR = Path(__file__).resolve().parent
CACHE_DIR = os.environ.get("CACHE_DIR", str(BASE_DIR / "stem_cache"))
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", str(BASE_DIR / "output_mixes"))

os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

app = FastAPI(title="Audio Mixer Backend AI")

# CORS setup 
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🚀 Mount the Router gateways cleanly
app.include_router(stems.router)
app.include_router(mix.router)

@app.get("/")
async def root():
    return {"status": "ok", "service": "Audio Mixer Backend AI Reorganized"}

@app.get("/health")
async def health():
    return {"status": "ok"}

# Asset mounting targets
app.mount("/stems", StaticFiles(directory=CACHE_DIR), name="stems")
app.mount("/mixes", StaticFiles(directory=OUTPUT_DIR), name="mixes")