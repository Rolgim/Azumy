# SPDX-FileCopyrightText: Copyright (C) 2026, CNES (Rollin Gimenez)
# SPDX-License-Identifier: Apache-2.0

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import Optional
import re
import pyvips

from utils import stream_command, build_cmd, ws_path

router = APIRouter()


class ProcessReq(BaseModel):
    tile: str

    # White balance
    zero: list[float] = [24.5, 29.8, 30.1, 30.0]
    scaling: list[float] = [2.2, 1.3, 1.2, 1.0]
    fwhm: list[float] = [1.6, 3.5, 3.4, 3.5]

    # Processing
    sharpen: float = 0.5
    nirl: float = 0.1
    ib: float = 1.0
    yg: float = 0.5
    jr: float = 0.25

    # Rendering
    white: float = 22.0
    stretch: float = 28.0
    offset: float = 29.0
    hue: float = -20.0
    saturation: float = 1.2


# Processing steps used to estimate progress
STEPS = [
    ("Read IYJH", 10),
    ("Detect bad pixels", 25),
    ("Inpaint", 40),
    ("Sharpen", 55),
    ("Stretch", 68),
    ("Blend IYJH", 80),
    ("Adjust curves", 92),
    ("Write", 100),
]


def _progress(line: str) -> Optional[dict]:
    """Detect progress step from log line."""
    low = line.lower()
    for keyword, pct in STEPS:
        if keyword.lower() in low:
            return {"label": keyword, "percent": pct}
    return None


def _args(req: ProcessReq) -> list[str]:
    """Build CLI arguments for the processing command."""
    args = [req.tile]

    args += ["--zero"] + [str(v) for v in req.zero]
    args += ["--scaling"] + [str(v) for v in req.scaling]
    args += ["--fwhm"] + [str(v) for v in req.fwhm]

    args += ["--sharpen", str(req.sharpen)]
    args += ["--nirl", str(req.nirl)]
    args += ["--ib", str(req.ib)]
    args += ["--yg", str(req.yg)]
    args += ["--jr", str(req.jr)]

    args += ["--white", str(req.white)]
    args += ["--stretch", str(req.stretch)]
    args += ["--offset", str(req.offset)]
    args += ["--hue", str(req.hue)]
    args += ["--saturation", str(req.saturation)]

    return args


def generate_preview(input_file: str, size: int = 512) -> str:
    """
    Generate a small JPEG preview from a large TIFF image using pyvips.

    This method is memory-efficient and suitable for very large images.
    A simple normalization + gamma correction is applied to make the preview visible.
    """

    preview_file = input_file.replace(".tiff", "_preview.jpg")

    image = pyvips.Image.thumbnail(input_file, 512, size='both')  # generates a 512x512 preview
    image = image.cast("uchar")
    image.write_to_file(preview_file, Q=85)
    return preview_file


@router.websocket("/ws")
async def process_ws(ws: WebSocket):
    await ws.accept()

    try:
        # Parse request
        req = ProcessReq(**(await ws.receive_json()))

        if not req.tile:
            await ws.send_json({"type": "error", "message": "tile required"})
            return

        # Build command
        cmd = build_cmd("process", _args(req))
        await ws.send_json({"type": "cmd", "message": " ".join(cmd)})

        output_file = None
        preview_file = None

        # Stream process output
        async for line in stream_command(cmd):

            if line.startswith("__EXIT__"):
                code = int(line[8:])
                await ws.send_json({"type": "exit", "code": code})
                continue

            # Send raw logs
            await ws.send_json({"type": "log", "message": line})

            # Detect progress step
            prog = _progress(line)
            if prog:
                await ws.send_json({"type": "progress", **prog})

            # Extract output file from log
            # Example: "- Write: 102159776_adjusted.tiff"
            m = re.search(r"-\s+Write(?:\s+\S+)?:\s+(\S+)", line)
            if m:
                filename = m.group(1)
                tile_number = req.tile.split("[")[0]  # e.g., "102160242"
                output_file = ws_path() / tile_number / filename
                await ws.send_json({"type": "output_file", "name": filename})

        # Generate preview after processing completes
        if output_file:
            try:
                await ws.send_json({
                    "type": "progress",
                    "label": "Generating preview",
                    "percent": 98
                })

                preview_file = generate_preview(str(output_file))
                preview_file_name = preview_file.split("/")[-1]

                await ws.send_json({
                    "type": "preview",
                    "name": preview_file_name
                })

            except Exception as e:
                await ws.send_json({
                    "type": "error",
                    "message": f"Preview generation failed: {e}"
                })

        # Final message
        await ws.send_json({
            "type": "done",
            "output_file": filename if output_file else None,
            "preview_file": preview_file_name if preview_file else None,
        })

    except WebSocketDisconnect:
        pass

    except Exception as e:
        try:
            await ws.send_json({"type": "error", "message": str(e)})
        except:
            pass