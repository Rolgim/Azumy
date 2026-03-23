from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import Optional
import re
from utils import stream_command, build_cmd

router = APIRouter()


class ProcessReq(BaseModel):
    tile: str                                    # ex: "102159776[6000:7000,5000:7000]"
    # White balance
    zero:    list[float] = [24.5, 29.8, 30.1, 30.0]
    scaling: list[float] = [2.2,  1.3,  1.2,  1.0]
    fwhm:    list[float] = [1.6,  3.5,  3.4,  3.5]
    # Processing
    sharpen:    float = 0.5
    nirl:       float = 0.1
    ib:         float = 1.0
    yg:         float = 0.5
    jr:         float = 0.25
    # Rendering
    white:      float = 22.0
    stretch:    float = 28.0
    offset:     float = 29.0
    hue:        float = -20.0
    saturation: float = 1.2


STEPS = [
    ("Read IYJH",          10),
    ("Detect bad pixels",  25),
    ("Inpaint",            40),
    ("Sharpen",            55),
    ("Stretch",            68),
    ("Blend IYJH",         80),
    ("Adjust curves",      92),
    ("Write",             100),
]

def _progress(line: str) -> Optional[dict]:
    low = line.lower()
    for keyword, pct in STEPS:
        if keyword.lower() in low:
            return {"label": keyword, "percent": pct}
    return None


def _args(req: ProcessReq) -> list[str]:
    args = [req.tile]
    args += ["--zero"]    + [str(v) for v in req.zero]
    args += ["--scaling"] + [str(v) for v in req.scaling]
    args += ["--fwhm"]    + [str(v) for v in req.fwhm]
    args += ["--sharpen",    str(req.sharpen)]
    args += ["--nirl",       str(req.nirl)]
    args += ["--ib",         str(req.ib)]
    args += ["--yg",         str(req.yg)]
    args += ["--jr",         str(req.jr)]
    args += ["--white",      str(req.white)]
    args += ["--stretch",    str(req.stretch)]
    args += ["--offset",     str(req.offset)]
    args += ["--hue",        str(req.hue)]
    args += ["--saturation", str(req.saturation)]
    return args


@router.websocket("/ws")
async def process_ws(ws: WebSocket):
    await ws.accept()
    try:
        req = ProcessReq(**(await ws.receive_json()))
        if not req.tile:
            await ws.send_json({"type": "error", "message": "tile requis"})
            return

        cmd = build_cmd("process", _args(req))
        await ws.send_json({"type": "cmd", "message": " ".join(cmd)})

        # look for line like: "- Write: 102159776_adjusted.tiff" to get output file name
        output_file = None

        async for line in stream_command(cmd):
            if line.startswith("__EXIT__"):
                code = int(line[8:])
                await ws.send_json({"type": "exit", "code": code})
            else:
                await ws.send_json({"type": "log", "message": line})
                prog = _progress(line)
                if prog:
                    await ws.send_json({"type": "progress", **prog})
                # "- Write: 102159776_adjusted.tiff"
                m = re.search(r"-\s+Write(?:\s+\S+)?:\s+(\S+)", line)
                if m:
                    output_file = m.group(1)
                    await ws.send_json({"type": "output_file", "name": output_file})

        await ws.send_json({"type": "done", "output_file": output_file})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try: await ws.send_json({"type": "error", "message": str(e)})
        except: pass