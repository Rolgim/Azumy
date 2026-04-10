"""
Tests for /retrieve - args building, parsing, websocket behavior.
"""

import re

import pytest

import routers.retrieve as retrieve_module


# Args logic (unit)
class TestRetrieveArgs:
    def _args(self, tile_indices, provider="sas", dsr="DR1_R2,DR1_R1,Q1_R1"):
        return ["--from", provider, "--dsr", dsr] + tile_indices

    def test_single_tile(self):
        args = self._args(["102159776"], provider="sas")
        assert "102159776" in args
        assert "--from" in args
        assert "sas" in args

    def test_multiple_tiles(self):
        args = self._args(["102159776", "102159777"])
        assert "102159776" in args
        assert "102159777" in args

    def test_provider_idr(self):
        args = self._args(["102159776"], provider="idr")
        assert "idr" in args

    def test_dsr_passed(self):
        args = self._args(["102159776"], dsr="Q1_R1")
        assert "Q1_R1" in args

    def test_from_before_tiles(self):
        args = self._args(["102159776"], provider="sas")
        assert args.index("--from") < args.index("102159776")


# Parsing logic (unit)
class TestRetrieveProgressParsing:
    def _parse_file(self, line):
        m = re.search(r"-\s+\[([^\]]+)\]\s+(\S+)", line)
        if m:
            return {"filter": m.group(1), "name": m.group(2)}
        return None

    def test_vis_file(self):
        line = "- [VIS] EUC_MER_BGSUB-VIS_TILE102159776.fits"
        r = self._parse_file(line)
        assert r["filter"] == "VIS"
        assert "TILE102159776" in r["name"]

    def test_nir_file(self):
        line = "- [NIR_Y] EUC_MER-NIR_Y_TILE102159776.fits"
        r = self._parse_file(line)
        assert r["filter"] == "NIR_Y"

    def test_no_match(self):
        assert self._parse_file("Elapsed time: 1.0s") is None


# WebSocket fake helpers
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


class BadStream:
    """async generator that crashes immediately (fixes warning properly)"""

    def __aiter__(self):
        return self

    async def __anext__(self):
        raise RuntimeError("boom")


# WebSocket endpoint tests
@pytest.mark.asyncio
async def test_ws_empty_tiles(monkeypatch):
    ws = FakeWS({"tile_indices": []})

    await retrieve_module.retrieve_ws(ws)

    assert ws.sent[0]["type"] == "error"


@pytest.mark.asyncio
async def test_ws_full_flow(monkeypatch):
    ws = FakeWS({"tile_indices": ["102159776"], "provider": "sas", "dsr": "DR1_R2"})

    async def fake_stream(cmd):
        yield "- [VIS] file1.fits"
        yield "__EXIT__0"

    monkeypatch.setattr(retrieve_module, "build_cmd", lambda *a: ["cmd"])
    monkeypatch.setattr(retrieve_module, "stream_command", fake_stream)

    await retrieve_module.retrieve_ws(ws)

    types = [m["type"] for m in ws.sent]

    assert "cmd" in types
    assert "log" in types
    assert "file" in types
    assert "exit" in types
    assert "done" in types


@pytest.mark.asyncio
async def test_ws_tile_dedup(monkeypatch):
    ws = FakeWS({"tile_indices": ["1"], "provider": "sas", "dsr": "DR1_R2"})

    async def fake_stream(cmd):
        yield "azul --workspace process 123"
        yield "azul --workspace process 123"  # duplicate
        yield "__EXIT__0"

    monkeypatch.setattr(retrieve_module, "build_cmd", lambda *a: ["cmd"])
    monkeypatch.setattr(retrieve_module, "stream_command", fake_stream)

    await retrieve_module.retrieve_ws(ws)

    tiles = [m for m in ws.sent if m["type"] == "tile"]

    assert len(tiles) == 1


@pytest.mark.asyncio
async def test_ws_exception(monkeypatch):
    ws = FakeWS({"tile_indices": ["1"], "provider": "sas"})

    monkeypatch.setattr(retrieve_module, "build_cmd", lambda *a: ["cmd"])
    monkeypatch.setattr(retrieve_module, "stream_command", lambda cmd: BadStream())

    await retrieve_module.retrieve_ws(ws)

    assert any(m["type"] == "error" for m in ws.sent)


@pytest.mark.asyncio
async def test_ws_disconnect(monkeypatch):
    ws = FakeWS({"tile_indices": ["1"]})

    class DisconnectWS(FakeWS):
        async def receive_json(self):
            raise retrieve_module.WebSocketDisconnect()

    ws = DisconnectWS({"tile_indices": ["1"]})

    await retrieve_module.retrieve_ws(ws)

    assert True
