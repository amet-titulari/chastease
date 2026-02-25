import sys
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from chastease import create_app
import uvicorn
from dotenv import load_dotenv

app = create_app()

# load .env from project root if present (allows RELOAD/UVICORN_RELOAD settings)
load_dotenv(dotenv_path=ROOT / '.env')

if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    log_level = os.getenv("LOG_LEVEL", "INFO").strip().lower()
    # Enable autoreload when UVICORN_RELOAD env var is set to a truthy value
    reload_env = os.getenv("UVICORN_RELOAD", os.getenv("RELOAD", "")).strip().lower()
    reload = reload_env in ("1", "true", "yes", "on")
    # watch the src directory by default when reloading
    reload_dirs = [str(SRC)] if reload else None
    if reload:
        # When using reload, uvicorn requires an import string so the server
        # can spawn a subprocess and re-import the application. Use the
        # application factory `create_app` from the `chastease` package and
        # set `factory=True` so uvicorn calls the factory to get an app.
        uvicorn.run(
            "chastease:create_app",
            host=host,
            port=port,
            log_level=log_level,
            reload=reload,
            reload_dirs=reload_dirs,
            factory=True,
        )
    else:
        uvicorn.run(app, host=host, port=port, log_level=log_level)
