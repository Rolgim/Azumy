from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
import re
from utils import stream_command, build_azul_cmd

router = APIRouter()


class RetrieveReq(BaseModel):
    workspace: str = "."
    tile_indices: list[str]
    provider: str = "idr"                    # dss, sas, idr
    dsr: str = "DR1_R2,DR1_R1,Q1_R1"        # comma-separated dataset releases


def _args(req: RetrieveReq) -> list[str]:
    args = ["--from", req.provider, "--dsr", req.dsr]
    args.extend(req.tile_indices)
    return args


def _parse_progress(line: str) -> int | None:
    # "Download and extract datafiles to: ..." => start download
    # "- [VIS] filename.fits" => one file downloaded
    m = re.search(r"(\d{1,3})\s*%", line)
    return int(m.group(1)) if m else None


@router.websocket("/ws")
async def retrieve_ws(ws: WebSocket):
    await ws.accept()
    try:
        req = RetrieveReq(**(await ws.receive_json()))
        if not req.tile_indices:
            await ws.send_json({"type": "error", "message": "tile_indices vide"})
            return

        cmd = build_azul_cmd("retrieve", _args(req), req.workspace)
        await ws.send_json({"type": "cmd", "message": " ".join(cmd)})

        downloaded = []
        total_expected = len(req.tile_indices) * 4  # 4 files per tile (VIS + NIR Y/J/H)
        count = 0

        async for line in stream_command(cmd):
            if line.startswith("__EXIT__"):
                await ws.send_json({"type": "exit", "code": int(line[8:])})
            else:
                await ws.send_json({"type": "log", "message": line})

                # File download progress
                m = re.search(r"-\s+\[([^\]]+)\]\s+(\S+)", line)
                if m:
                    filter_name = m.group(1)
                    filename = m.group(2)
                    downloaded.append({"filter": filter_name, "file": filename})
                    count += 1
                    pct = min(int(count / total_expected * 100), 99)
                    await ws.send_json({"type": "file", "filter": filter_name, "name": filename})
                    await ws.send_json({"type": "progress", "percent": pct})

        await ws.send_json({"type": "done", "downloaded": downloaded})
    except WebSocketDisconnect:
        pass
    except Exception as e:
        try: await ws.send_json({"type": "error", "message": str(e)})
        except: pass