# SPDX-FileCopyrightText: Copyright (C) 2026, CNES (Rollin Gimenez)
# SPDX-License-Identifier: Apache-2.0

import logging
import re
from pathlib import Path
from typing import Any, Literal

import pyvips
import yaml
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from utils import build_cmd, stream_command, ws_path

logger = logging.getLogger(__name__)
router = APIRouter()


# Azul ----------------------------------------------------------------
class AzulProcessReq(BaseModel):
    engine: Literal["azul"] = "azul"
    tile: str

    zero: list[float] = [24.5, 29.8, 30.1, 30.0]
    scaling: list[float] = [2.2, 1.3, 1.2, 1.0]
    fwhm: list[float] = [1.6, 3.5, 3.4, 3.5]

    sharpen: float = 0.5
    nirl: float = 0.1
    ib: float = 1.0
    yg: float = 0.5
    jr: float = 0.25

    white: float = 22.0
    stretch: float = 28.0
    offset: float = 29.0
    hue: float = -20.0
    saturation: float = 1.2


AZUL_STEPS = [
    ("Read IYJH", 10),
    ("Detect bad pixels", 25),
    ("Inpaint", 40),
    ("Sharpen", 55),
    ("Stretch", 68),
    ("Blend IYJH", 80),
    ("Adjust curves", 92),
    ("Write", 100),
]


def _azul_progress(line: str) -> dict[str, Any] | None:
    low = line.lower()
    for keyword, pct in AZUL_STEPS:
        if keyword.lower() in low:
            return {"label": keyword, "percent": pct}
    return None


def _azul_args(req: AzulProcessReq) -> list[str]:
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


# Eummy ----------------------------------------------------------------
class EummyProcessReq(BaseModel):
    engine: Literal["eummy"] = "eummy"
    tile: str
    blackwhite: list[float] = [-1.3, 7000]
    pivot: float = 0.15
    contrast: float | None = None
    scales: list[float] = [0.002039, 0.5950, 1.0000, 1.0985]
    fr: float = 0.3
    saturate: list[float] = [2.0]
    um: list[float] = [1.6, 0.75, 0.09]
    um_enabled: bool = True
    blend_iy: bool = False
    fi: float = 1.6
    output: str = "TILE[id].tif"
    slicing: str | None = None  # e.g. "[100:500,200:600]"


EUMMY_STEPS = [
    ("Processing FITS", 10),
    ("Repairing bad", 25),
    ("Dynamic-range", 45),
    ("Enhancing contrast", 55),
    ("Color-space", 75),
    ("Unsharp", 88),
    ("Writing", 100),
]


def _eummy_progress(line: str) -> dict[str, Any] | None:
    low = line.lower()
    for keyword, pct in EUMMY_STEPS:
        if keyword.lower() in low:
            return {"label": keyword, "percent": pct}
    return None


def _eummy_args(req: EummyProcessReq, tile_dir: Path) -> list[str]:
    args = ["eummy", "--path", str(tile_dir)]
    args += ["--blackwhite", str(req.blackwhite[0]), str(req.blackwhite[1])]
    args += ["--pivot", str(req.pivot)]

    if req.contrast is not None:
        args += ["--contrast", str(req.contrast)]

    args += ["--scales"] + [str(v) for v in req.scales]
    args += ["--fr", str(req.fr)]
    args += ["--saturate"] + [str(v) for v in req.saturate]

    if req.um_enabled:
        args += ["--UM"] + [str(v) for v in req.um]
    else:
        args += ["--UM", "false"]

    if req.blend_iy:
        args.append("--blendIY")
        args += ["--fi", str(req.fi)]

    slicing_match = re.match(r"\[(\d+):(\d+),(\d+):(\d+)\]", req.slicing or "")
    if slicing_match:
        y0, y1, x0, x1 = map(int, slicing_match.groups())
        col_c = (x0 + x1) // 2
        row_c = (y0 + y1) // 2
        w = x1 - x0
        h = y1 - y0
        args += ["--cutout", str(col_c), str(row_c), f"{w}p", f"{h}p"]

    args += ["--output", req.output]
    return args


# Common ----------------------------------------------------------------
def generate_preview(input_file: str, size: int = 512) -> str:
    preview_file = re.sub(r"\.(tif|tiff)$", "_preview.jpg", input_file, flags=re.I)
    image = pyvips.Image.thumbnail(input_file, size, size="both")
    image = image.cast("uchar")
    image.write_to_file(preview_file, Q=85)
    return preview_file


def read_wcs(tile_number: str) -> dict[str, Any] | None:
    wcs_path = ws_path() / tile_number / f"{tile_number}_wcs.yaml"
    if not wcs_path.exists():
        return None

    with open(wcs_path) as f:
        wcs: dict[str, Any] = yaml.safe_load(f)

    ra = wcs.get("CRVAL1")
    dec = wcs.get("CRVAL2")
    pc11 = abs(wcs.get("PC1_1", wcs.get("CDELT1", 2.777e-5)))
    pc22 = abs(wcs.get("PC2_2", wcs.get("CDELT2", 2.777e-5)))
    pixel_scale = (pc11 + pc22) / 2

    return {"ra": ra, "dec": dec, "pixel_scale": pixel_scale}


def find_output_file(tile_dir: Path, line: str, engine: str) -> str | None:
    if engine == "azul":
        m = re.search(r"-\s+Write(?:\s+\S+)?:\s+(\S+)", line)
    else:
        m = re.search(r"Writing result to\s+(.+\.tif)", line, re.I)

    if m:
        return Path(m.group(1).strip()).name
    return None


async def _stream_and_respond(
    ws: WebSocket, cmd: list[str], engine: str, tile_number: str, tile_dir: Path
):
    output_file: Path | None = None
    filename: str | None = None

    async for line in stream_command(cmd):
        if line.startswith("__EXIT__"):
            code = int(line[8:])
            await ws.send_json({"type": "exit", "code": code})
            continue

        await ws.send_json({"type": "log", "message": line})

        prog = _azul_progress(line) if engine == "azul" else _eummy_progress(line)
        if prog:
            await ws.send_json({"type": "progress", **prog})

        name = find_output_file(tile_dir, line, engine)
        if name:
            filename = name
            output_file = tile_dir / name
            await ws.send_json({"type": "output_file", "name": name})

    preview_name: str | None = None
    if output_file and output_file.exists():
        try:
            await ws.send_json({"type": "progress", "label": "Generating preview", "percent": 98})
            preview_path = generate_preview(str(output_file))
            preview_name = Path(preview_path).name
            await ws.send_json({"type": "preview", "name": preview_name})
        except Exception as e:
            await ws.send_json({"type": "error", "message": f"Preview failed: {e}"})

    wcs = read_wcs(tile_number)
    if wcs:
        wcs["fov"] = 0.5
        await ws.send_json({"type": "wcs", **wcs})

    await ws.send_json(
        {
            "type": "done",
            "output_file": filename,
            "preview_file": preview_name,
        }
    )


@router.get("/wcs/{tile}")
def get_wcs(tile: str):
    wcs = read_wcs(tile)
    if not wcs:
        raise HTTPException(404, f"WCS not found for tile {tile}")
    return JSONResponse(wcs)


@router.websocket("/ws")
async def process_ws(ws: WebSocket):
    await ws.accept()
    try:
        data = await ws.receive_json()
        engine = data.get("engine", "azul")

        if engine == "azul":
            azul_req = AzulProcessReq(**data)

            if not azul_req.tile:
                await ws.send_json({"type": "error", "message": "tile required"})
                return

            tile_number = azul_req.tile.split("[")[0]
            tile_dir = ws_path() / tile_number
            cmd = build_cmd("process", _azul_args(azul_req))

        elif engine == "eummy":
            eummy_req = EummyProcessReq(**data)

            if not eummy_req.tile:
                await ws.send_json({"type": "error", "message": "tile required"})
                return

            tile_number = eummy_req.tile
            tile_dir = ws_path() / tile_number
            cmd = _eummy_args(eummy_req, tile_dir)

        else:
            await ws.send_json({"type": "error", "message": f"Unknown engine: {engine}"})
            return

        await ws.send_json({"type": "cmd", "message": " ".join(cmd)})
        await _stream_and_respond(ws, cmd, engine, tile_number, tile_dir)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await ws.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
