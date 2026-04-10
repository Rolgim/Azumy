"""
Tests for /crop endpoints - slicing computation and preview.
"""

import numpy as np
import pytest
from fastapi import HTTPException

import routers.crop as crop_module

# Local fixtures --------------------------------


@pytest.fixture
def make_tile(tmp_workspace):
    def _make(tile="test_tile"):
        path = tmp_workspace / tile
        path.mkdir()
        return tile

    return _make


@pytest.fixture
def mock_vis_file(monkeypatch):
    def _mock(path="fake.fits"):
        monkeypatch.setattr(crop_module, "_find_vis_file", lambda workdir: path)

    return _mock


@pytest.fixture
def mock_fits(monkeypatch):
    def _mock(data):
        class FakeHDU:
            def __init__(self, d):
                self.data = d

        class FakeHDUList(list):
            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

        monkeypatch.setattr(
            "astropy.io.fits.open", lambda *args, **kwargs: FakeHDUList([FakeHDU(data)])
        )

    return _mock


# /crop slicing --------------------------------------------------


class TestCropSlicing:
    def test_basic_slicing(self, client):
        r = client.post(
            "/crop/slicing",
            json={
                "tile": "102159776",
                "x0": 5000,
                "x1": 7000,
                "y0": 6000,
                "y1": 7000,
                "w": 16000,
                "h": 16000,
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert "slicing" in data
        assert "102159776" in data["slicing"]

    def test_slicing_format(self, client):
        r = client.post(
            "/crop/slicing",
            json={
                "tile": "102159776",
                "x0": 5000,
                "x1": 7000,
                "y0": 6000,
                "y1": 7000,
                "w": 16000,
                "h": 16000,
            },
        )
        slicing = r.json()["slicing"]
        assert slicing.startswith("102159776[")
        assert "," in slicing
        assert slicing.endswith("]")

    def test_slicing_rounding(self, client):
        r = client.post(
            "/crop/slicing",
            json={
                "tile": "102159776",
                "x0": 5100,
                "x1": 6900,
                "y0": 6100,
                "y1": 6900,
                "w": 16000,
                "h": 16000,
                "round": 500,
            },
        )
        data = r.json()
        assert data["x0"] == 5000
        assert data["x1"] == 7000

    def test_slicing_capped_at_image_size(self, client):
        r = client.post(
            "/crop/slicing",
            json={
                "tile": "102159776",
                "x0": 0,
                "x1": 16100,
                "y0": 0,
                "y1": 16100,
                "w": 16000,
                "h": 16000,
            },
        )
        data = r.json()
        assert data["x1"] <= 16000
        assert data["y1"] <= 16000

    def test_slicing_custom_rounding(self, client):
        r = client.post(
            "/crop/slicing",
            json={
                "tile": "mytile",
                "x0": 250,
                "x1": 750,
                "y0": 250,
                "y1": 750,
                "w": 2000,
                "h": 2000,
                "round": 100,
            },
        )
        data = r.json()
        assert data["x0"] % 100 == 0
        assert data["x1"] % 100 == 0


# /crop preview ---------------------------------------------------


class TestCropPreview:
    def test_preview_success(self, client, make_tile, mock_vis_file, mock_fits):
        tile = make_tile()

        mock_vis_file()
        mock_fits(np.ones((100, 200), dtype=np.float32))

        r = client.get(f"/crop/preview/{tile}")

        assert r.status_code == 200
        assert r.headers["content-type"] == "image/png"
        assert int(r.headers["X-Tile-Width"]) == 200
        assert int(r.headers["X-Tile-Height"]) == 100
        assert len(r.content) > 0

    def test_preview_no_2d_data(self, client, make_tile, mock_vis_file, mock_fits):
        tile = make_tile()

        mock_vis_file()
        mock_fits(None)

        r = client.get(f"/crop/preview/{tile}")

        assert r.status_code == 500
        assert "No 2D image data" in r.text

    def test_preview_tile_not_found(self, client, monkeypatch):
        def raise_not_found(_):
            raise HTTPException(404, "No VIS file found")

        monkeypatch.setattr(crop_module, "_find_vis_file", raise_not_found)

        r = client.get("/crop/preview/missing")

        assert r.status_code == 404

    def test_preview_custom_params(self, client, make_tile, mock_vis_file, mock_fits):
        tile = make_tile()

        mock_vis_file()
        mock_fits(np.random.rand(100, 100).astype(np.float32))

        r = client.get(f"/crop/preview/{tile}?white=0.5&downsample=5")

        assert r.status_code == 200
