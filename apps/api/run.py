"""
Dev launcher — starts the FastAPI backend on port 8000.

On Windows with Microsoft Store Python, uvicorn's --reload subprocess
does not inherit the parent's sys.path, so we run without reload here.
Hot-reload can be achieved by re-running this script after changes.

Usage:
    python run.py
"""
import sys
import os

api_dir = os.path.dirname(os.path.abspath(__file__))
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,   # reload disabled — restart the script to pick up changes
    )
