# SPDX-FileCopyrightText: Copyright (C) 2026, CNES (Rollin Gimenez)
# SPDX-License-Identifier: Apache-2.0

import json
import logging
import re

from fastapi import APIRouter, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from utils import build_cmd, stream_command, ws_path

logger = logging.getLogger(__name__)

router = APIRouter()


class FindReq(BaseModel):
    objects: list[str] = []
    coordinates: list[dict[str, float]] = []
    tiling: str = ""


def _args(req: FindReq) -> list[str]:
    args = list(req.objects)
    for c in req.coordinates:
        args += ["--radec", str(c["ra"]), str(c["dec"])]
    if req.tiling:
        args += ["--tiling", req.tiling]
    return args


def _parse_tile(line: str) -> dict[str, str | float] | None:
    m = re.search(r"-\s+(\w+):\s+(\d+)\s+\(([^)]+)\);\s+distance:\s+([\d.]+)", line)
    if m:
        return {
            "index": m.group(2),
            "mode": m.group(1),
            "dsr": m.group(3),
            "distance": float(m.group(4)),
        }
    return None


@router.websocket("/ws")
async def find_ws(ws: WebSocket) -> None:
    await ws.accept()
    try:
        req = FindReq(**(await ws.receive_json()))
        args = _args(req)
        if not args:
            await ws.send_json(
                {"type": "error", "message": "Provide at least one object or coordinates"}
            )
            logger.debug("No objects or coordinates provided")
            return

        cmd = build_cmd("find", args)
        await ws.send_json({"type": "cmd", "message": " ".join(cmd)})

        seen = set()
        async for line in stream_command(cmd):
            if line.startswith("__EXIT__"):
                logger.debug(f"Command exited with code {line[8:]}")
                await ws.send_json({"type": "exit", "code": int(line[8:])})
            else:
                await ws.send_json({"type": "log", "message": line})
                t = _parse_tile(line)
                if t and t["index"] not in seen:
                    seen.add(t["index"])
                    await ws.send_json({"type": "tile", "data": t})

        logger.info("Find command completed, total tiles found: %d", len(seen))
        await ws.send_json({"type": "done"})

    except WebSocketDisconnect:
        logger.debug("WebSocket disconnected")

    except Exception as e:
        logger.exception(f"Unhandled error in websocket: {e}")

        try:
            await ws.send_json({"type": "error", "message": str(e)})
        except Exception:
            logger.debug("WebSocket closed before sending error")


@router.post("/geojson")
async def upload_geojson(file: UploadFile = File(...)) -> JSONResponse:
    """Receive a GeoJSON file and store it in workspace."""
    if not file.filename.lower().endswith(".geojson"):
        logger.debug("Invalid file type: %s", file.filename)
        raise HTTPException(400, "Only .geojson files are allowed")
    path = ws_path() / file.filename
    try:
        logger.debug("Saving uploaded file to %s", path)
        content = await file.read()
        path.write_bytes(content)
    except Exception as e:
        logger.debug("Error saving file: %s", e)
        raise HTTPException(500, f"Could not save file: {e}")
    return JSONResponse({"filename": file.filename})


@router.get("/tiling")
def get_tiling(filename: str) -> JSONResponse:
    """Return the list of tiles from a tiling GeoJSON file."""
    path = ws_path() / filename
    if not path.exists():
        # Look in current dir as fallback (for testing)
        from pathlib import Path

        logger.debug(f"{filename} not found in workspace, checking current directory")
        path = Path(filename)
    if not path.exists():
        logger.debug(f"{filename} not found in current directory either")
        raise HTTPException(404, f"{filename} unavailable in workspace or current directory")

    with open(path) as f:
        logger.debug(f"Reading tiling file from {path}")
        data = json.load(f)

    tiles = []
    for feature in data.get("features", []):
        props = feature.get("properties", {})
        geom = feature.get("geometry", {})
        if geom.get("type") != "Polygon":
            continue
        coords = geom["coordinates"][0]
        tiles.append(
            {
                "index": props.get("TileIndex"),
                "mode": props.get("ProcessingMode"),
                "dsr": props.get("DatasetRelease"),
                "coords": coords,
            }
        )

    return JSONResponse({"tiles": tiles})
