# SPDX-FileCopyrightText: Copyright (C) 2026, CNES (Rollin Gimenez)
# SPDX-License-Identifier: Apache-2.0

import logging
import re

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from utils import build_cmd, stream_command

logger = logging.getLogger(__name__)

router = APIRouter()


class RetrieveReq(BaseModel):
    tile_indices: list[str]
    provider: str = "idr"
    dsr: str = "DR1_R2,DR1_R1,Q1_R1"


def _args(req: RetrieveReq) -> list[str]:
    return ["--from", req.provider, "--dsr", req.dsr] + req.tile_indices


@router.websocket("/ws")
async def retrieve_ws(ws: WebSocket) -> None:
    await ws.accept()
    try:
        req = RetrieveReq(**(await ws.receive_json()))
        if not req.tile_indices:
            logger.debug("No tile indices provided")
            await ws.send_json({"type": "error", "message": "No tile indices provided"})
            return

        cmd = build_cmd("retrieve", _args(req))
        logger.debug("Running command: %s", " ".join(cmd))
        await ws.send_json({"type": "cmd", "message": " ".join(cmd)})

        downloaded = []
        total_expected = len(req.tile_indices) * 4
        count = 0

        tile_number = None
        seen_tiles = set()

        async for line in stream_command(cmd):
            if line.startswith("__EXIT__"):
                logger.debug(f"Command exited with code {line[8:]}")
                await ws.send_json({"type": "exit", "code": int(line[8:])})
            else:
                await ws.send_json({"type": "log", "message": line})

                m = re.search(r"-\s+\[([^\]]+)\]\s+(\S+)", line)
                if m:
                    filter_name = m.group(1)
                    filename = m.group(2)
                    downloaded.append({"filter": filter_name, "file": filename})
                    count += 1
                    pct = min(int(count / total_expected * 100), 99)
                    logger.debug("Downloaded %s, progress: %d%%", filename, pct)
                    await ws.send_json({"type": "file", "filter": filter_name, "name": filename})
                    await ws.send_json({"type": "progress", "percent": pct})

                # Catch tile number from lines like "azul --workspace ... process 123"
                if "azul --workspace" in line and ("crop" in line or "process" in line):
                    match = re.search(r"(crop|process)\s+(\d+)", line)
                    if match:
                        tile_id = match.group(2)
                        # Only send tile message the first time we see a tile_id,
                        # to avoid duplicates if multiple files are downloaded for the same tile,
                        # ie not for the set but the websocket
                        if tile_id not in seen_tiles:
                            seen_tiles.add(tile_id)
                            tile_number = tile_id
                            logger.debug("Tile number: %s", tile_number)
                            await ws.send_json({"type": "tile", "index": tile_id})

        logger.info(f"Command completed, sending done message for tiles {seen_tiles}")
        await ws.send_json({"type": "done", "downloaded": downloaded, "tiles": list(seen_tiles)})

    except WebSocketDisconnect:
        logger.debug("WebSocket disconnected")

    except Exception as e:
        logger.exception(f"Unhandled error in websocket: {e}")

        try:
            await ws.send_json({"type": "error", "message": "Internal server error"})
        except Exception:
            logger.debug("WebSocket closed before sending error")
