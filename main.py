"""
Azulweb — Backend FastAPI
Start with: uvicorn main:app --reload --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from routers import find, workspace, retrieve

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
app.include_router(find.router,      prefix="/find",      tags=["Find"])
app.include_router(retrieve.router, prefix="/retrieve", tags=["Retrieve"])

# Serve images/videos
outputs_dir = Path("outputs")
outputs_dir.mkdir(exist_ok=True)
app.mount("/outputs", StaticFiles(directory="outputs"), name="outputs")


@app.get("/", tags=["Health"])
def root():
    return {"status": "ok", "service": "Azulero GUI API v1.0.0"}


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
