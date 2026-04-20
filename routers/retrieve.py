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
    targets: list[str]
    provider: str = "idr"
    dsr: str = "DR1_R2,DR1_R1,Q1_R1"
    radius: str | None = None
    limit: int | None = None


def _args(req: RetrieveReq) -> list[str]:
    args = ["--from", req.provider, "--dsr", req.dsr]
    if req.radius:
        args += ["--radius", req.radius + "°"]
    if req.limit:
        args += ["--limit", str(req.limit)]
    args.extend(req.targets)
    return args


# Regex pour détecter une ligne workdir standalone : "102088678/12.098764,4.092438"
# ou "102088678" seul (tile entière)
_RE_WORKDIR = re.compile(r"^(\d+)(/\S+)?$")

# Tile : "- Tile: WIDE: 102088678 (DR1_R1); distance: 0.12°"
_RE_TILE = re.compile(r"-\s+Tile:\s+\w+:\s+(\d+)")

# Fichier téléchargé : "- [VIS] EUC_MER_...fits"
_RE_FILE = re.compile(r"-\s+\[([^\]]+)\]\s+(\S+\.fits)")


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
        seen_workdirs = set()
        count = 0
        total_expected = len(req.targets) * 4

        async for line in stream_command(cmd):
            if line.startswith("__EXIT__"):
                await ws.send_json({"type": "exit", "code": int(line[8:])})
                continue

            await ws.send_json({"type": "log", "message": line})

            # Fichier téléchargé
            m_file = _RE_FILE.search(line)
            if m_file:
                filter_name, filename = m_file.group(1), m_file.group(2)
                downloaded.append({"filter": filter_name, "file": filename})
                count += 1
                pct = min(int(count / total_expected * 100), 99)
                await ws.send_json({"type": "file", "filter": filter_name, "name": filename})
                await ws.send_json({"type": "progress", "percent": pct})

            # Tile résolue : "- Tile: WIDE: 102088678 ..."
            m_tile = _RE_TILE.search(line)
            if m_tile:
                tile_id = m_tile.group(1)
                if tile_id not in seen_tiles:
                    seen_tiles.add(tile_id)
                    await ws.send_json({"type": "tile", "index": tile_id})

            # Workdir standalone : dernière ligne, ex "102088678/12.098764,4.092438"
            m_wd = _RE_WORKDIR.match(line.strip())
            if m_wd:
                workdir = line.strip()
                tile_id = m_wd.group(1)
                if tile_id not in seen_tiles:
                    seen_tiles.add(tile_id)
                    await ws.send_json({"type": "tile", "index": tile_id})
                if workdir not in seen_workdirs:
                    seen_workdirs.add(workdir)
                    await ws.send_json({"type": "workdir", "value": workdir})

        await ws.send_json(
            {
                "type": "done",
                "downloaded": downloaded,
                "tiles": list(seen_tiles),
                "workdirs": list(seen_workdirs),
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
