"""Server entry point: `python -m src` (from the repo root).

Binds port 8001 by default (8000 is commonly occupied). Override with PORT.
"""
from __future__ import annotations

import os

import uvicorn


def main() -> None:
    port = int(os.environ.get("PORT", "8001"))
    uvicorn.run("src.api:app", host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    main()
