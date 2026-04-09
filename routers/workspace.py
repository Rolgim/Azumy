# SPDX-FileCopyrightText: Copyright (C) 2026, CNES (Rollin Gimenez)
# SPDX-License-Identifier: Apache-2.0

import logging
from pathlib import Path
from typing import Any, TypedDict

from fastapi import APIRouter, HTTPException

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
