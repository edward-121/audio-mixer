import os
from fastapi import Header
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CACHE_DIR = os.environ.get("CACHE_DIR", str(BASE_DIR / "stem_cache"))

def get_session_cache_dir(x_session_id: str = Header(..., alias="X-Session-ID")) -> str:
    """
    Dynamically extracts the user's browser session ID header
    and provisions a private sandboxed subfolder for them.
    """
    print(f"🔑 [SESSION ACCESS] ID: {x_session_id}")
    safe_session_id = "".join([c for c in x_session_id if c.isalnum() or c in "-_"])
    user_isolated_path = os.path.join(CACHE_DIR, safe_session_id)
    os.makedirs(user_isolated_path, exist_ok=True)
    return user_isolated_path