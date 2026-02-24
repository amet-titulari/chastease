import sys
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from chastease import create_app
import uvicorn

app = create_app()

if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    log_level = os.getenv("LOG_LEVEL", "INFO").strip().lower()
    uvicorn.run(app, host=host, port=port, log_level=log_level)
