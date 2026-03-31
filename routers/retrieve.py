from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
import re
from utils import stream_command, build_cmd

router = APIRouter()


class RetrieveReq(BaseModel):
    tile_indices: list[str]
    provider: str = "idr"
    dsr: str = "DR1_R2,DR1_R1,Q1_R1"


def _args(req: RetrieveReq) -> list[str]:
    return ["--from", req.provider, "--dsr", req.dsr] + req.tile_indices


@router.websocket("/ws")
async def retrieve_ws(ws: WebSocket):
    await ws.accept()
    try:
        req = RetrieveReq(**(await ws.receive_json()))
        if not req.tile_indices:
            await ws.send_json({"type": "error", "message": "No tile indices provided"})
            return

        cmd = build_cmd("retrieve", _args(req))
        await ws.send_json({"type": "cmd", "message": " ".join(cmd)})

        downloaded = []
        total_expected = len(req.tile_indices) * 4
        count = 0

        heartbeat_started = False
        tile_number = None  

        async for line in stream_command(cmd):
            if line.startswith("__EXIT__"):
                await ws.send_json({"type": "exit", "code": int(line[8:])})
            else:
                await ws.send_json({"type": "log", "message": line})

                if line.startswith("Download and extract"):
                    heartbeat_started = True

                m = re.search(r"-\s+\[([^\]]+)\]\s+(\S+)", line)
                if m:
                    filter_name = m.group(1)
                    filename    = m.group(2)
                    downloaded.append({"filter": filter_name, "file": filename})
                    count += 1
                    pct = min(int(count / total_expected * 100), 99)
                    await ws.send_json({"type": "file",     "filter": filter_name, "name": filename})
                    await ws.send_json({"type": "progress", "percent": pct})

                # Catch tile number from lines like "azul --workspace ... crop 123" or "azul --workspace ... process 123"
                if "azul --workspace" in line and ("crop" in line or "process" in line):
                    match = re.search(r"(crop|process)\s+(\d+)", line)
                    if match:
                        tile_number = match.group(2)

        await ws.send_json({"type": "done", "downloaded": downloaded, "tile": tile_number})
    except WebSocketDisconnect:
        pass
    except Exception as e:
        try: await ws.send_json({"type": "error", "message": str(e)})
        except: pass