"""Server entry point: `python -m src` (from the repo root).

Binds port 8001 by default (8000 is commonly occupied). Override with PORT.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
import uvicorn


def main() -> None:
    _DOTENV_PATH = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(dotenv_path=_DOTENV_PATH if _DOTENV_PATH.is_file() else None, override=False)
    port = int(os.environ.get("PORT", "8001"))
    uvicorn.run("src.api:app", host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    main()
