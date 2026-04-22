# SPDX-FileCopyrightText: Copyright (C) 2026, CNES (Rollin Gimenez)
# SPDX-License-Identifier: Apache-2.0

import io as sysio
import logging
import math
from pathlib import Path

import numpy as np
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from utils import ws_path

logger = logging.getLogger(__name__)

router = APIRouter()


def _find_vis_file(workdir: Path, pattern: str = "EUC_MER_BGSUB-MOSAIC-VIS*") -> Path:
    candidates = list(workdir.glob(pattern))
    if not candidates:
        raise HTTPException(404, f"No VIS file found in {workdir}")
    return candidates[0]


@router.get("/preview/{tile:path}")
def crop_preview(tile: str, white: float = 99.5, downsample: int = 10) -> Response:
    """
    Generate a downsampled, stretched preview PNG from the VIS FITS file of the tile.
    """
    try:
        import matplotlib
        from astropy.io import fits

        matplotlib.use("Agg")  # No display needed
        import matplotlib.pyplot as plt
    except ImportError as e:
        logger.exception("Required libraries for preview generation are missing")
        raise HTTPException(500, f"Missing dependency: {e}")

    workdir = ws_path() / tile
    logger.info(f"Generating preview for tile {tile} in workdir {workdir}")
    vis_file = _find_vis_file(workdir)

    with fits.open(vis_file, memmap=True) as hdul:
        logger.info(f"Opened FITS file {vis_file} with {len(hdul)} HDUs")
        # Look for the first 2D image data in the FITS file
        data = None
        for hdu in hdul:
            if hdu.data is not None and len(hdu.data.shape) == 2:
                data = hdu.data.astype(np.float32)
                break
        if data is None:
            logger.error("No 2D image data found in FITS file")
            raise HTTPException(500, "No 2D image data found in FITS file")

    h, w = data.shape

    # Downsample + stretch
    d = data[::downsample, ::downsample]
    p_low, p_high = np.percentile(d, (1, white))
    d = np.clip(d, p_low, p_high)
    d = (d - p_low) / (p_high - p_low + 1e-9)
    d = np.arcsinh(d / 0.7)
    d = (d - d.min()) / (d.max() - d.min() + 1e-9)

    # PNG in memory
    fig, ax = plt.subplots(figsize=(8, 8 * h / w))
    ax.imshow(np.flipud(d), cmap="gray", extent=(0.0, float(w), 0.0, float(h)), aspect="auto")
    ax.axis("off")
    fig.tight_layout(pad=0)
    buf = sysio.BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight", pad_inches=0)
    plt.close(fig)
    buf.seek(0)

    logger.info(f"Generated preview for tile {tile}, size: {buf.getbuffer().nbytes} bytes")
    return Response(
        content=buf.read(),
        media_type="image/png",
        headers={
            "X-Tile-Width": str(w),
            "X-Tile-Height": str(h),
            "Access-Control-Expose-Headers": "X-Tile-Width, X-Tile-Height",
        },
    )


class CropSlicing(BaseModel):
    tile: str
    x0: float
    x1: float
    y0: float
    y1: float
    w: int
    h: int
    round: int = 500


@router.post("/slicing")
def compute_slicing(req: CropSlicing) -> dict[str, int | str]:
    """Compute the slicing string for cropping the tile
    based on the requested coordinates and rounding."""
    r = req.round

    x0 = math.floor(req.x0 / r) * r
    x1 = min(math.ceil(req.x1 / r) * r, req.w)
    y0 = math.floor(req.y0 / r) * r
    y1 = min(math.ceil(req.y1 / r) * r, req.h)

    slicing = f"{req.tile}[{y0}:{y1},{x0}:{x1}]"
    logger.info(
        f"Computed slicing for tile {req.tile}: ({req.x0}, {req.y0})-({req.x1}, {req.y1}) "
        f"-> ({x0}, {y0})-({x1}, {y1}), slicing: {slicing}"
    )
    return {"slicing": slicing, "x0": x0, "x1": x1, "y0": y0, "y1": y1}
