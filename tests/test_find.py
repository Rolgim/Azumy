"""
Tests for /find endpoints - tiling GeoJSON, upload, and tile parser.
"""

import json
import re

import pytest

import routers.find as find_module


# helpers ---------------------------------
class BadStream:
    def __aiter__(self):
        return self

    async def __anext__(self):
        raise RuntimeError("boom")


class FakeWS:
    def __init__(self, payload):
        self.payload = payload
        self.sent = []

    async def accept(self):
        pass

    async def receive_json(self):
        return self.payload

    async def send_json(self, data):
        self.sent.append(data)


class DisconnectWS(FakeWS):
    async def receive_json(self):
        raise find_module.WebSocketDisconnect()


# Unit tests: tile parser ---------------------------------------------
class TestParseTile:
    """Test _parse_tile regex logic."""

    def _parse(self, line):
        m = re.search(r"-\s+(\w+):\s+(\d+)\s+\(([^)]+)\);\s+distance:\s+([\d.]+)", line)
        if m:
            return {
                "index": m.group(2),
                "mode": m.group(1),
                "dsr": m.group(3),
                "distance": float(m.group(4)),
            }
        return None

    def test_standard_line(self):
        line = "- wide: 102159776 (DR1_R2); distance: 0.12"
        r = self._parse(line)
        assert r["index"] == "102159776"
        assert r["mode"] == "wide"
        assert r["dsr"] == "DR1_R2"
        assert r["distance"] == pytest.approx(0.12)

    def test_deep_mode(self):
        r = self._parse("- deep: 102159777 (Q1_R1); distance: 0.05")
        assert r["mode"] == "deep"

    def test_no_match(self):
        assert self._parse("invalid line") is None

    def test_distance_float(self):
        r = self._parse("- wide: 1 (A); distance: 1.234")
        assert r["distance"] == pytest.approx(1.234)


# Integration tests: find/ws ---------------------------------------------
# 1. args empty → error branch
@pytest.mark.asyncio
async def test_ws_no_args(monkeypatch):
    ws = FakeWS({"objects": [], "coordinates": [], "tiling": ""})
    monkeypatch.setattr(find_module, "stream_command", lambda cmd: iter([]))
    await find_module.find_ws(ws)
    assert ws.sent[0]["type"] == "error"


# 2. normal flow + tile + exit + done
@pytest.mark.asyncio
async def test_ws_full_flow(monkeypatch):
    ws = FakeWS({"objects": ["M31"], "coordinates": [], "tiling": ""})

    async def fake_stream(cmd):
        yield "- wide: 123 (DR1); distance: 0.1"
        yield "__EXIT__0"

    monkeypatch.setattr(find_module, "build_cmd", lambda *a: ["cmd"])
    monkeypatch.setattr(find_module, "stream_command", fake_stream)
    await find_module.find_ws(ws)
    types = [m["type"] for m in ws.sent]
    assert "cmd" in types
    assert "log" in types
    assert "tile" in types
    assert "exit" in types
    assert "done" in types


# 3. duplicate tile filtering (seen set)
@pytest.mark.asyncio
async def test_ws_dedup_tiles(monkeypatch):
    ws = FakeWS({"objects": ["M31"], "coordinates": [], "tiling": ""})

    async def fake_stream(cmd):
        yield "- wide: 123 (DR1); distance: 0.1"
        yield "- wide: 123 (DR1); distance: 0.2"  # duplicate index
        yield "__EXIT__0"

    monkeypatch.setattr(find_module, "build_cmd", lambda *a: ["cmd"])
    monkeypatch.setattr(find_module, "stream_command", fake_stream)
    await find_module.find_ws(ws)
    tile_msgs = [m for m in ws.sent if m["type"] == "tile"]
    assert len(tile_msgs) == 1


# 4. exception branch (outer try)
@pytest.mark.asyncio
async def test_ws_exception(monkeypatch):
    ws = FakeWS({"objects": ["M31"], "coordinates": [], "tiling": ""})
    monkeypatch.setattr(find_module, "build_cmd", lambda *a: ["cmd"])
    monkeypatch.setattr(find_module, "stream_command", lambda cmd: BadStream())
    await find_module.find_ws(ws)
    assert any(m["type"] == "error" for m in ws.sent)


# 5. websocket disconnect branch
@pytest.mark.asyncio
async def test_ws_disconnect(monkeypatch):
    ws = DisconnectWS({"objects": ["M31"]})
    await find_module.find_ws(ws)
    # No error should be raised,
    # and we can check logs or just that it completes without exception
    assert True


# Integration tests: /tiling ---------------------------------------------
class TestFindTiling:
    @pytest.fixture
    def sample_geojson(self, tmp_workspace):
        data = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [10.0, 20.0],
                                [10.5, 20.0],
                                [10.5, 20.5],
                                [10.0, 20.5],
                                [10.0, 20.0],
                            ]
                        ],
                    },
                    "properties": {
                        "TileIndex": 102159776,
                        "ProcessingMode": "wide",
                        "DatasetRelease": "DR1_R2",
                    },
                },
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [11.0, 21.0],
                                [11.5, 21.0],
                                [11.5, 21.5],
                                [11.0, 21.5],
                                [11.0, 21.0],
                            ]
                        ],
                    },
                    "properties": {
                        "TileIndex": 102159777,
                        "ProcessingMode": "deep",
                        "DatasetRelease": "Q1_R1",
                    },
                },
            ],
        }

        path = tmp_workspace / "test.geojson"
        path.write_text(json.dumps(data))
        return "test.geojson"

    def test_returns_tiles(self, client, sample_geojson):
        r = client.get(f"/find/tiling?filename={sample_geojson}")
        assert r.status_code == 200
        assert len(r.json()["tiles"]) == 2

    def test_tile_fields(self, client, sample_geojson):
        tile = client.get(f"/find/tiling?filename={sample_geojson}").json()["tiles"][0]
        assert {"index", "mode", "dsr", "coords"} <= tile.keys()

    def test_coords_format(self, client, sample_geojson):
        coords = client.get(f"/find/tiling?filename={sample_geojson}").json()["tiles"][0]["coords"]
        assert isinstance(coords, list)
        assert len(coords) == 5
        assert len(coords[0]) == 2

    def test_not_found(self, client):
        r = client.get("/find/tiling?filename=missing.geojson")
        assert r.status_code == 404

    def test_filters_non_polygon(self, client, tmp_workspace):
        data = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [1, 2]},
                    "properties": {"TileIndex": 1},
                }
            ],
        }
        path = tmp_workspace / "points.geojson"
        path.write_text(json.dumps(data))

        r = client.get("/find/tiling?filename=points.geojson")
        assert r.status_code == 200
        assert r.json()["tiles"] == []


# Integration tests: /geojson upload ---------------------------------------------
class TestFindUploadGeoJSON:
    def test_upload_success(self, client, tmp_workspace):
        files = {"file": ("test.geojson", "{}", "application/geo+json")}

        r = client.post("/find/geojson", files=files)

        assert r.status_code == 200
        assert r.json()["filename"] == "test.geojson"

        assert (tmp_workspace / "test.geojson").exists()

    def test_wrong_extension(self, client):
        files = {"file": ("test.txt", "{}", "text/plain")}

        r = client.post("/find/geojson", files=files)

        assert r.status_code == 400

    def test_upload_write_error(self, client, tmp_workspace, monkeypatch):
        import pathlib

        files = {"file": ("test.geojson", "{}", "application/geo+json")}

        original = pathlib.Path.write_bytes

        def raise_error(self, *args, **kwargs):
            raise OSError("disk full")

        monkeypatch.setattr(pathlib.Path, "write_bytes", raise_error)

        r = client.post("/find/geojson", files=files)

        assert r.status_code == 500
        assert "Could not save file" in r.text

        monkeypatch.setattr(pathlib.Path, "write_bytes", original)

    # robustness testsclass DisconnectWS(FakeWS):
    async def receive_json(self):
        raise find_module.WebSocketDisconnect()


class TestFindEdgeCases:
    def test_case_insensitive_extension(self, client):
        files = {"file": ("TEST.GEOJSON", "{}", "application/json")}

        r = client.post("/find/geojson", files=files)

        assert r.status_code == 200
