import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from chastease import create_app
import uvicorn

app = create_app()

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=5000)
