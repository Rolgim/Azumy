"""
Azulweb — Backend FastAPI
Start with: uvicorn main:app --reload --port 8000
"""

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from routers import crop, find, process, retrieve, workspace

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

app = FastAPI(
    title="Azulero GUI API",
    description="Backend for Azulweb - Azulero GUI (Euclid color images)",
    version="0.0.1",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(workspace.router, prefix="/workspace", tags=["Workspace"])
app.include_router(find.router, prefix="/find", tags=["Find"])
app.include_router(retrieve.router, prefix="/retrieve", tags=["Retrieve"])
app.include_router(crop.router, prefix="/crop", tags=["Crop"])
app.include_router(process.router, prefix="/process", tags=["Process"])

# Serve images/videos
outputs_dir = Path("workspace")
outputs_dir.mkdir(exist_ok=True)
app.mount("/workspace", StaticFiles(directory="workspace"), name="workspace")
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")


@app.get("/health", tags=["Health"])
def health():
    """Check azulero installation."""
    import subprocess

    try:
        result = subprocess.run(["azul", "--version"], capture_output=True, text=True, timeout=5)
        version = result.stdout.strip() or result.stderr.strip()
        return {"status": "ok", "azulero_version": version}
    except FileNotFoundError:
        return {"status": "error", "detail": "azulero not found — pip install azulero"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}
