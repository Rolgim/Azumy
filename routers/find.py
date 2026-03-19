"""
Router /find — azul find
  - POST /find/run       => run azule find and return results at the end
  - WebSocket /find/ws   => streaming of the logs
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel
from typing import Optional
import asyncio
import re

from utils import stream_command, build_azul_cmd

router = APIRouter()


# Data models

class CoordPair(BaseModel):
    ra: float
    dec: float

class FindRequest(BaseModel):
    workspace: str = "."
    objects: list[str] = []
    coordinates: list[CoordPair] = []
    geojson: Optional[str] = None


class TileResult(BaseModel):
    index: str
    ra: Optional[float] = None
    dec: Optional[float] = None
    status: str = "available"


class FindResponse(BaseModel):
    command: str
    tiles: list[TileResult]
    raw_output: str


# Helpers

def parse_tiles_from_output(output: str) -> list[TileResult]:
    """
    Parse 'azul find' output to get tile index
    """
    tiles = []
    seen = set()

    # Pattern : ligne contenant un identifiant numérique 9 chiffres
    tile_pattern = re.compile(r"\b(\d{9})\b")
    # Pattern optionnel : RA/Dec sur la même ligne
    radec_pattern = re.compile(r"RA[=:\s]+([\d.+-]+).*?[Dd]ec[=:\s]+([\d.+-]+)", re.IGNORECASE)

    for line in output.splitlines():
        m = tile_pattern.search(line)
        if m:
            idx = m.group(1)
            if idx in seen:
                continue
            seen.add(idx)
            ra_dec = radec_pattern.search(line)
            tiles.append(TileResult(
                index=idx,
                ra=float(ra_dec.group(1)) if ra_dec else None,
                dec=float(ra_dec.group(2)) if ra_dec else None,
            ))

    return tiles


def build_find_args(req: FindRequest) -> list[str]:
    args = list(req.objects)
    for c in req.coordinates:
        args += ["--radec", str(c.ra), str(c.dec)]
    if req.geojson:
        args += ["--geojson", req.geojson]
    return args


# Endpoints

@router.post("/run", response_model=FindResponse)
async def find_run(req: FindRequest):
    """Run 'azul find' and return results"""
    args = build_find_args(req)
    if not args:
        raise HTTPException(400, "Provide at least one object or coordinate RA/Dec")

    cmd = build_azul_cmd("find", args, workspace=req.workspace)
    command_str = " ".join(cmd)

    lines = []
    async for line in stream_command(cmd):
        if line.startswith("__EXIT_CODE__"):
            code = int(line.replace("__EXIT_CODE__", ""))
            if code != 0:
                raise HTTPException(500, f"Error in azul find (exit {code})\n" + "\n".join(lines))
        else:
            lines.append(line)

    raw = "\n".join(lines)
    tiles = parse_tiles_from_output(raw)

    return FindResponse(command=command_str, tiles=tiles, raw_output=raw)


@router.websocket("/ws")
async def find_ws(websocket: WebSocket):
    """WebSocket : streaming real time of 'azul find' logs."""
    await websocket.accept()
    try:
        data = await websocket.receive_json()
        req = FindRequest(**data)
        args = build_find_args(req)

        if not args:
            await websocket.send_json({"type": "error", "message": "Need at least one object or coordinate RA/Dec"})
            return

        cmd = build_azul_cmd("find", args, workspace=req.workspace)
        await websocket.send_json({"type": "cmd", "message": " ".join(cmd)})

        tiles = []
        async for line in stream_command(cmd):
            if line.startswith("__EXIT_CODE__"):
                code = int(line.replace("__EXIT_CODE__", ""))
                await websocket.send_json({"type": "exit", "code": code})
            else:
                await websocket.send_json({"type": "log", "message": line})
                # Tentative de parsing à la volée
                new_tiles = parse_tiles_from_output(line)
                for t in new_tiles:
                    if t.index not in [x.index for x in tiles]:
                        tiles.append(t)
                        await websocket.send_json({
                            "type": "tile_found",
                            "tile": t.model_dump(),
                        })

        await websocket.send_json({"type": "done", "tiles": [t.model_dump() for t in tiles]})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
