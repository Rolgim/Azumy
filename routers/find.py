# SPDX-FileCopyrightText: Copyright (C) 2026, CNES (Rollin Gimenez)
# SPDX-License-Identifier: Apache-2.0

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
import re
from utils import stream_command, build_cmd
from fastapi import HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
import json
from utils import ws_path

router = APIRouter()


class FindReq(BaseModel):
    objects: list[str] = []
    coordinates: list[dict] = []
    tiling: str = ""


def _args(req: FindReq) -> list[str]:
    args = list(req.objects)
    for c in req.coordinates:
        args += ["--radec", str(c["ra"]), str(c["dec"])]
    if req.tiling:
        args += ["--tiling", req.tiling]
    return args


def _parse_tile(line: str) -> dict | None:
    m = re.search(r"-\s+(\w+):\s+(\d+)\s+\(([^)]+)\);\s+distance:\s+([\d.]+)", line)
    if m:
        return {
            "index": m.group(2),
            "mode":  m.group(1),
            "dsr":   m.group(3),
            "distance": float(m.group(4)),
        }
    return None


@router.websocket("/ws")
async def find_ws(ws: WebSocket):
    await ws.accept()
    try:
        req = FindReq(**(await ws.receive_json()))
        args = _args(req)
        if not args:
            await ws.send_json({"type": "error", "message": "Provide at least one object or coordinates"})
            return

        cmd = build_cmd("find", args)
        await ws.send_json({"type": "cmd", "message": " ".join(cmd)})

        seen = set()
        async for line in stream_command(cmd):
            if line.startswith("__EXIT__"):
                await ws.send_json({"type": "exit", "code": int(line[8:])})
            else:
                await ws.send_json({"type": "log", "message": line})
                t = _parse_tile(line)
                if t and t["index"] not in seen:
                    seen.add(t["index"])
                    await ws.send_json({"type": "tile", "data": t})

        await ws.send_json({"type": "done"})
    except WebSocketDisconnect:
        pass
    except Exception as e:
        try: await ws.send_json({"type": "error", "message": str(e)})
        except: pass


@router.post("/geojson")
async def upload_geojson(file: UploadFile = File(...)):
    """Receive a GeoJSON file and store it in workspace."""
    if not file.filename.lower().endswith(".geojson"):
        raise HTTPException(400, "Only .geojson files are allowed")
    path = ws_path() / file.filename
    try:
        content = await file.read()
        path.write_bytes(content)
    except Exception as e:
        raise HTTPException(500, f"Could not save file: {e}")
    return JSONResponse({"filename": file.filename})

@router.get("/tiling")
def get_tiling(filename: str):
    """Return the list of tiles from a tiling GeoJSON file."""
    path = ws_path() / filename
    if not path.exists():
        # Look in current dir as fallback (for testing)
        from pathlib import Path
        path = Path(filename)
    if not path.exists():
        raise HTTPException(404, f"{filename} unavailable in workspace or current directory")

    with open(path) as f:
        data = json.load(f)

    tiles = []
    for feature in data.get("features", []):
        props = feature.get("properties", {})
        geom  = feature.get("geometry", {})
        if geom.get("type") != "Polygon":
            continue
        coords = geom["coordinates"][0]
        tiles.append({
            "index": props.get("TileIndex"),
            "mode":  props.get("ProcessingMode"),
            "dsr":   props.get("DatasetRelease"),
            "coords": coords,  
        })

    return JSONResponse({"tiles": tiles})