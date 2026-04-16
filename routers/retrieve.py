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
    targets: list[str]  # tile indices, "ra,dec", or object names
    provider: str = "idr"
    dsr: str = "DR1_R2,DR1_R1,Q1_R1"
    radius: str | None = None  # ex: "1m", "30s", "0.5d"
    limit: int | None = None


def _args(req: RetrieveReq) -> list[str]:
    args = ["--from", req.provider, "--dsr", req.dsr]
    if req.radius:
        args += ["--radius", req.radius + "°"]
    if req.limit:
        args += ["--limit", str(req.limit)]
    args.extend(req.targets)
    return args


@router.websocket("/ws")
async def retrieve_ws(ws: WebSocket) -> None:
    await ws.accept()
    try:
        req = RetrieveReq(**(await ws.receive_json()))

        if not req.targets:
            await ws.send_json({"type": "error", "message": "No targets provided"})
            return

        cmd = build_cmd("retrieve", _args(req))
        logger.debug("Running command: %s", " ".join(cmd))
        await ws.send_json({"type": "cmd", "message": " ".join(cmd)})

        downloaded = []
        seen_tiles = set()
        count = 0
        # Estimate total files: 4 per target (VIS + NIR Y/J/H)
        total_expected = len(req.targets) * 4

        async for line in stream_command(cmd):
            if line.startswith("__EXIT__"):
                await ws.send_json({"type": "exit", "code": int(line[8:])})
                continue

            await ws.send_json({"type": "log", "message": line})

            # Fichier téléchargé : "- [VIS] EUC_MER_...fits"
            m = re.search(r"-\s+\[([^\]]+)\]\s+(\S+)", line)
            if m:
                filter_name, filename = m.group(1), m.group(2)
                downloaded.append({"filter": filter_name, "file": filename})
                count += 1
                pct = min(int(count / total_expected * 100), 99)
                await ws.send_json({"type": "file", "filter": filter_name, "name": filename})
                await ws.send_json({"type": "progress", "percent": pct})

            # Tile: 102159776"
            m_tile = re.search(r"-\s+Tile:\s+(\d+)", line)
            if m_tile:
                tile_id = m_tile.group(1)
                if tile_id not in seen_tiles:
                    seen_tiles.add(tile_id)
                    await ws.send_json({"type": "tile", "index": tile_id})

            # Fallback : line "azul ... process 102159776"
            if "azul --workspace" in line and ("crop" in line or "process" in line):
                m_proc = re.search(r"(?:crop|process)\s+(\S+)", line)
                if m_proc:
                    tile_id = m_proc.group(1).split("[")[0]
                    if tile_id not in seen_tiles:
                        seen_tiles.add(tile_id)
                        await ws.send_json({"type": "tile", "index": tile_id})

        await ws.send_json(
            {
                "type": "done",
                "downloaded": downloaded,
                "tiles": list(seen_tiles),
            }
        )

    except WebSocketDisconnect:
        logger.debug("WebSocket disconnected")
    except Exception as e:
        logger.exception("Unhandled error in retrieve websocket: %s", e)
        try:
            await ws.send_json({"type": "error", "message": "Internal server error"})
        except Exception:
            pass
