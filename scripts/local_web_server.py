"""SecuLense backend server runner.

Wraps the FastAPI backend application for local development and CLI scripts,
re-exporting AuthStore for backward compatibility with existing tests and scripts.
"""
from __future__ import annotations

import os
from pathlib import Path
import sys
import uvicorn

# Re-export AuthStore and auth constants for backward compatibility
from secu_lense.server.auth import (
    AuthStore,
    COOKIE_NAME,
    PASSWORD_ROUNDS,
    SESSION_HOURS,
    DB_FILE,
)
from secu_lense.server.app import app

__all__ = ["AuthStore", "COOKIE_NAME", "PASSWORD_ROUNDS", "SESSION_HOURS", "DB_FILE", "app"]


def main():
    host = os.environ.get("SECULENSE_HOST", "127.0.0.1")
    port = int(os.environ.get("SECULENSE_API_PORT", os.environ.get("SECULENSE_PORT", "8000")))
    # start.mjs listens for "listening on" in stdout
    print(f"SecuLense backend API listening on http://{host}:{port}", flush=True)
    uvicorn.run(
        "secu_lense.server.app:app",
        host=host,
        port=port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
