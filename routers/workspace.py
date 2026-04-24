# SPDX-FileCopyrightText: Copyright (C) 2026, CNES (Rollin Gimenez)
# SPDX-License-Identifier: Apache-2.0

import logging
from pathlib import Path
from typing import Any, TypedDict

from fastapi import APIRouter, HTTPException

from utils import ws_path

logger = logging.getLogger(__name__)

router = APIRouter()


class WorkspaceInfo(TypedDict):
    path: str
    exists: bool
    tiles: list[dict[str, Any]]
    total_size_mb: float


@router.get("/info")
def info(path: str = ".") -> WorkspaceInfo:
    ws = Path(path).expanduser().resolve()
    if not ws.exists():
        logger.debug("Workspace does not exist: %s", ws)
        return {"path": str(ws), "exists": False, "tiles": [], "total_size_mb": 0}
    tiles, total = [], 0
    for item in sorted(ws.iterdir()):
        if item.is_dir() and item.name.isdigit():
            files = list(item.rglob("*"))
            size = sum(f.stat().st_size for f in files if f.is_file())
            total += size
            imgs = [f.name for f in files if f.suffix.lower() in (".jpg", ".jpeg", ".png")]
            vids = [f.name for f in files if f.suffix.lower() == ".mp4"]
            tiles.append(
                {
                    "index": item.name,
                    "fits_count": sum(1 for f in files if f.suffix.lower() in (".fits", ".fit")),
                    "images": imgs,
                    "videos": vids,
                    "size_mb": round(size / 1e6, 2),
                }
            )
    logger.info(f"Scanned workspace {ws}: {len(tiles)}tiles, {(total / 1e6)} MB")
    return {
        "path": str(ws),
        "exists": True,
        "tiles": tiles,
        "total_size_mb": round(total / 1e6, 2),
    }


@router.get("/tile/{tile_index}/latest-image")
def latest_image(tile_index: str, workspace: str = ".") -> dict[str, str]:
    tile_dir = Path(workspace).expanduser().resolve() / tile_index
    if not tile_dir.exists():
        logger.debug("Tile not found: %s", tile_dir)
        raise HTTPException(404, "Tile not found")
    imgs = sorted(tile_dir.glob("*.jpg")) + sorted(tile_dir.glob("*.png"))
    if not imgs:
        logger.debug("No image found for tile: %s", tile_dir)
        raise HTTPException(404, "No image")
    latest = max(imgs, key=lambda p: p.stat().st_mtime)
    return {"url": f"/outputs/{tile_index}/{latest.name}", "name": latest.name}


@router.get("/gallery")
def gallery():
    ws = ws_path()
    if not ws.exists():
        return {"entries": []}

    entries = []

    # previews
    previews = list(ws.rglob("*_preview.jpg"))

    for preview in previews:
        rel = preview.relative_to(ws)
        parts = rel.parts

        workdir = str(Path(*parts[:-1])) if len(parts) > 1 else parts[0]

        stem = preview.stem.replace("_preview", "")
        parent = preview.parent

        # full-res candidates
        candidates = [
            parent / f"{stem}.tiff",
            parent / f"{stem}.tif",
            parent / f"{stem}.jpg",
            parent / f"{stem}.png",
        ]

        full = next((p for p in candidates if p.exists()), None)

        preview_url = "/workspace/" + str(rel).replace("\\", "/")

        if full:
            full_url = "/workspace/" + str(full.relative_to(ws)).replace("\\", "/")
            size_mb = round(full.stat().st_size / 1e6, 2)
            mtime = full.stat().st_mtime
        else:
            # fallback - no full available
            full_url = preview_url
            size_mb = round(preview.stat().st_size / 1e6, 2)
            mtime = preview.stat().st_mtime

        # Engine detection
        engine = "azul" if "_adjusted" in stem else "eummy"

        entries.append(
            {
                "workdir": workdir,
                "filename": stem,
                "preview_url": preview_url,
                "full_url": full_url,
                "engine": engine,
                "size_mb": size_mb,
                "mtime": mtime,
            }
        )

    entries.sort(key=lambda e: e["mtime"], reverse=True)

    return {"entries": entries}
