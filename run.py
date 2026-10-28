"""SecuLense project runner.

Launches the React & Python stack.
Usage:
    python run.py          # Production / standalone mode (FastAPI + React built SPA on http://127.0.0.1:8000)
    python run.py --dev    # Development mode (FastAPI API on :8000 + Vite Hot Reload on :5173)
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
PYTHON = sys.executable


def run_export():
    export_script = ROOT / "scripts" / "export_react_dashboard.py"
    if export_script.exists():
        subprocess.run([PYTHON, str(export_script)], cwd=ROOT, check=False)


def run_dev():
    print("Starting SecuLense in Development Mode...")
    run_export()
    start_mjs = ROOT / "frontend" / "start.mjs"
    if not start_mjs.exists():
        print(f"Error: {start_mjs} not found.")
        sys.exit(1)
    try:
        subprocess.run(["node", str(start_mjs)], cwd=ROOT / "frontend", check=True)
    except KeyboardInterrupt:
        print("\nSecuLense dev server stopped.")


def run_prod(host: str = "127.0.0.1", port: int = 8000):
    print(f"Starting SecuLense React & Python stack on http://{host}:{port}")
    run_export()
    dist_dir = ROOT / "frontend" / "dist"
    if not dist_dir.exists():
        print("Building React frontend first...")
        subprocess.run(["npm", "run", "build"], cwd=ROOT / "frontend", check=False)

    import uvicorn
    uvicorn.run("secu_lense.server.app:app", host=host, port=port, log_level="info")


def main():
    parser = argparse.ArgumentParser(description="SecuLense React & Python runner")
    parser.add_argument("--dev", action="store_true", help="Start development servers (FastAPI + Vite)")
    parser.add_argument("--host", default=os.environ.get("SECULENSE_HOST", "127.0.0.1"), help="Host to bind")
    parser.add_argument("--port", type=int, default=int(os.environ.get("SECULENSE_PORT", "8000")), help="Port to bind")
    args = parser.parse_args()

    if args.dev:
        run_dev()
    else:
        run_prod(args.host, args.port)


if __name__ == "__main__":
    main()

