from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
import re
from utils import stream_command, build_azul_cmd

router = APIRouter()


class FindReq(BaseModel):
    workspace: str = "."
    objects: list[str] = []
    coordinates: list[dict] = []   # [{"ra": 266.9, "dec": 64.0}, ...]
    tiling: str = ""               # ex: "DpdMerFinalCatalog.geojson"


def _args(req: FindReq) -> list[str]:
    args = list(req.objects)
    for c in req.coordinates:
        args += ["--radec", str(c["ra"]), str(c["dec"])]
    if req.tiling:
        args += ["--tiling", req.tiling]
    return args


def _parse_tile(line: str) -> dict | None:
    # "- wide: 102159776 (DR1); distance: 0.12°"
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
async def find_ws(ws: WebSocket):
    await ws.accept()
    try:
        req = FindReq(**(await ws.receive_json()))
        args = _args(req)
        if not args:
            await ws.send_json({"type": "error", "message": "Required at least one object or coordinate RA/Dec"})
            return

        cmd = build_azul_cmd("find", args, req.workspace)
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