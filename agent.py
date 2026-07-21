#!/usr/bin/env python3
"""agent.py — verify the setup (default) or run the server (--run).

Default (`uv run python agent.py`): a doctor pass — checks the environment,
deps, .env keys (presence only), DB, frontend, and runs the unit tests.
`--run`: applies migrations (if alembic is initialised) and starts the server.

All commands run from the repo root.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
GREEN, RED, YELLOW, RESET = "\033[32m", "\033[31m", "\033[33m", "\033[0m"


def _ok(msg: str) -> None:
    print(f"  {GREEN}✓{RESET} {msg}")


def _fail(msg: str) -> None:
    print(f"  {RED}✗{RESET} {msg}")


def _warn(msg: str) -> None:
    print(f"  {YELLOW}!{RESET} {msg}")


def verify() -> int:
    failures = 0
    print("Verifying setup (repo root: %s)\n" % ROOT)

    # 1. Python + deps
    print("Environment:")
    if sys.version_info >= (3, 11):
        _ok(f"Python {sys.version.split()[0]}")
    else:
        _fail(f"Python {sys.version.split()[0]} — need >= 3.11")
        failures += 1
    for mod in ("fastapi", "uvicorn", "sqlalchemy", "langgraph", "httpx", "structlog", "pydantic_settings"):
        try:
            __import__(mod)
            _ok(f"dependency: {mod}")
        except ImportError:
            _fail(f"dependency missing: {mod} — run `uv sync`")
            failures += 1

    # 2. .env / provider key (presence only — never print values)
    print("\nConfiguration:")
    if (ROOT / ".env").exists():
        _ok(".env exists")
    else:
        _warn(".env missing — copy .env.example and set one provider key")
    try:
        from src.config.settings import get_settings

        provider = get_settings().resolve_provider()
        if provider == "stub":
            _warn("no LLM key set — set ONE of AGENT_ANTHROPIC_API_KEY / "
                  "AGENT_GEMINI_API_KEY / AGENT_OPENROUTER_API_KEY in .env")
        else:
            _ok(f"provider: {provider} · model: {get_settings().resolve_model()}")
    except Exception as exc:  # noqa: BLE001
        _fail(f"settings failed to load: {exc}")
        failures += 1

    # 3. App imports + graph compiles
    print("\nApplication:")
    try:
        from src.api import create_app

        create_app()
        _ok("FastAPI app builds")
    except Exception as exc:  # noqa: BLE001
        _fail(f"app failed to build: {exc}")
        failures += 1
    try:
        from src.graph.agent import agentic_ai  # noqa: F401

        _ok("agent graph compiles")
    except Exception as exc:  # noqa: BLE001
        _fail(f"graph failed to compile: {exc}")
        failures += 1
    if (ROOT / "frontend" / "public" / "index.html").exists():
        _ok("frontend present (frontend/public)")
    else:
        _fail("frontend/public/index.html missing")
        failures += 1

    # 4. Unit tests (no key needed)
    print("\nUnit tests:")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/unit/", "-q"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    tail = (result.stdout or result.stderr).strip().splitlines()
    print("  " + "\n  ".join(tail[-3:]))
    if result.returncode != 0:
        _fail("unit tests failed")
        failures += 1
    else:
        _ok("unit tests pass")

    print()
    if failures:
        print(f"{RED}{failures} check(s) failed.{RESET}")
        return 1
    print(f"{GREEN}All checks passed.{RESET} Start the server with: uv run python agent.py --run")
    return 0


def run_server() -> int:
    # Apply migrations when an alembic revision exists; otherwise init_db()
    # (called in the app lifespan) creates the schema.
    versions = ROOT / "alembic" / "versions"
    if versions.is_dir() and any(p.suffix == ".py" for p in versions.iterdir()):
        if shutil.which("alembic") or (ROOT / ".venv").exists():
            print("Applying migrations: alembic upgrade head")
            rc = subprocess.run(
                [sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT
            ).returncode
            if rc != 0:
                print("alembic upgrade failed — fix migrations before serving")
                return rc
    port = os.environ.get("PORT", "8001")
    print(f"Starting server on http://localhost:{port}  (UI: http://localhost:{port}/app/)")
    return subprocess.run([sys.executable, "-m", "src"], cwd=ROOT).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="apply migrations and start the server")
    args = parser.parse_args()
    return run_server() if args.run else verify()


if __name__ == "__main__":
    raise SystemExit(main())
