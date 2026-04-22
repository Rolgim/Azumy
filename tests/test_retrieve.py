"""
Tests for /retrieve - args building, parsing, websocket behavior.
"""

import pytest

import routers.retrieve as retrieve_module


# Args logic (unit)
class TestRetrieveArgs:
    def _args(self, targets, provider="sas", dsr="DR1_R2,DR1_R1,Q1_R1", radius=None, limit=None):
        args = ["--from", provider, "--dsr", dsr]
        if radius:
            args += ["--radius", radius + "°"]
        if limit:
            args += ["--limit", str(limit)]
        args.extend(targets)
        return args

    def test_single_tile(self):
        args = self._args(["102159776"], provider="sas")
        assert "102159776" in args
        assert "--from" in args
        assert "sas" in args

    def test_multiple_tiles(self):
        args = self._args(["102159776", "102159777"])
        assert "102159776" in args
        assert "102159777" in args

    def test_object_target(self):
        args = self._args(["NGC6505"])
        assert "NGC6505" in args

    def test_radec_target(self):
        args = self._args(["12.09,4.09"])
        assert "12.09,4.09" in args

    def test_provider_idr(self):
        assert "idr" in self._args(["102159776"], provider="idr")

    def test_dsr_passed(self):
        assert "Q1_R1" in self._args(["102159776"], dsr="Q1_R1")

    def test_radius_appended(self):
        args = self._args(["NGC6505"], radius="1m")
        assert "--radius" in args
        assert "1m°" in args

    def test_limit_appended(self):
        args = self._args(["NGC6505"], limit=2)
        assert "--limit" in args
        assert "2" in args

    def test_from_before_targets(self):
        args = self._args(["102159776"], provider="sas")
        assert args.index("--from") < args.index("102159776")

    def test_no_radius_for_tiles(self):
        args = self._args(["102159776"])
        assert "--radius" not in args


# Parsing logic (unit)


class TestRetrieveParsing:
    def test_vis_file(self):
        line = "- [VIS] EUC_MER_BGSUB-VIS_TILE102159776.fits"
        m = retrieve_module._RE_FILE.search(line)
        assert m and m.group(1) == "VIS"

    def test_nir_file(self):
        line = "- [NIR_Y] EUC_MER-NIR_Y_TILE102159776.fits"
        m = retrieve_module._RE_FILE.search(line)
        assert m and m.group(1) == "NIR_Y"

    def test_file_no_match(self):
        assert retrieve_module._RE_FILE.search("Elapsed time: 1.0s") is None

    def test_tile_regex_new_format(self):
        line = "- Tile: WIDE: 102088678 (DR1_R1); distance: 0.12°"
        m = retrieve_module._RE_TILE.search(line)
        assert m and m.group(1) == "102088678"

    def test_tile_regex_no_match(self):
        assert retrieve_module._RE_TILE.search("Download and extract") is None

    def test_workdir_standalone_with_source(self):
        line = "102088678/12.098764,4.092438"
        m = retrieve_module._RE_WORKDIR.match(line.strip())
        assert m and m.group(1) == "102088678"

    def test_workdir_standalone_tile_only(self):
        m = retrieve_module._RE_WORKDIR.match("102159776")
        assert m and m.group(1) == "102159776"

    def test_workdir_no_match_on_log_line(self):
        assert retrieve_module._RE_WORKDIR.match("- Elapsed time: 1.0s") is None


# WebSocket fake helpers
class FakeWS:
    def __init__(self, payload):
        self.payload = payload
        self.sent = []

    async def accept(self):
        pass

    async def receive_json(self):
        return self.payload

    async def send_json(self, d):
        self.sent.append(d)

    def types(self):
        return [m["type"] for m in self.sent]


class DisconnectWS(FakeWS):
    async def receive_json(self):
        raise retrieve_module.WebSocketDisconnect()


class BadStream:
    def __aiter__(self):
        return self

    async def __anext__(self):
        raise RuntimeError("boom")


# WebSocket tests
@pytest.mark.asyncio
async def test_ws_empty_targets():
    ws = FakeWS({"targets": []})
    await retrieve_module.retrieve_ws(ws)
    assert ws.sent[0]["type"] == "error"


@pytest.mark.asyncio
async def test_ws_full_flow(monkeypatch):
    ws = FakeWS({"targets": ["102159776"], "provider": "sas", "dsr": "DR1_R2"})

    async def fake_stream(cmd):
        yield "- [VIS] file1.fits"
        yield "__EXIT__0"

    monkeypatch.setattr(retrieve_module, "build_cmd", lambda *a: ["cmd"])
    monkeypatch.setattr(retrieve_module, "stream_command", fake_stream)

    await retrieve_module.retrieve_ws(ws)
    types = ws.types()
    assert "cmd" in types
    assert "log" in types
    assert "file" in types
    assert "exit" in types
    assert "done" in types


@pytest.mark.asyncio
async def test_ws_with_object_and_radius(monkeypatch):
    ws = FakeWS({"targets": ["NGC6505"], "radius": "1m", "provider": "sas", "dsr": "DR1_R2"})

    captured = []

    async def fake_stream(cmd):
        captured.extend(cmd)
        yield "__EXIT__0"

    monkeypatch.setattr(
        retrieve_module, "build_cmd", lambda *a: ["azul", "retrieve", "--radius", "1m°", "NGC6505"]
    )
    monkeypatch.setattr(retrieve_module, "stream_command", fake_stream)

    await retrieve_module.retrieve_ws(ws)
    assert "done" in ws.types()


@pytest.mark.asyncio
async def test_ws_tile_detected(monkeypatch):
    ws = FakeWS({"targets": ["NGC6505"], "provider": "sas", "dsr": "DR1_R2"})

    async def fake_stream(cmd):
        yield "- Tile: WIDE: 102088678 (DR1_R1); distance: 0.12°"
        yield "__EXIT__0"

    monkeypatch.setattr(retrieve_module, "build_cmd", lambda *a: ["cmd"])
    monkeypatch.setattr(retrieve_module, "stream_command", fake_stream)

    await retrieve_module.retrieve_ws(ws)
    tiles = [m for m in ws.sent if m["type"] == "tile"]
    assert len(tiles) == 1
    assert tiles[0]["index"] == "102088678"


@pytest.mark.asyncio
async def test_ws_workdir_detected(monkeypatch):
    ws = FakeWS({"targets": ["NGC6505"], "provider": "sas", "dsr": "DR1_R2"})

    async def fake_stream(cmd):
        yield "102088678/NGC6505"
        yield "__EXIT__0"

    monkeypatch.setattr(retrieve_module, "build_cmd", lambda *a: ["cmd"])
    monkeypatch.setattr(retrieve_module, "stream_command", fake_stream)

    await retrieve_module.retrieve_ws(ws)
    workdirs = [m for m in ws.sent if m["type"] == "workdir"]
    assert len(workdirs) == 1
    assert workdirs[0]["value"] == "102088678/NGC6505"


@pytest.mark.asyncio
async def test_ws_tile_dedup(monkeypatch):
    ws = FakeWS({"targets": ["NGC6505"], "provider": "sas", "dsr": "DR1_R2"})

    async def fake_stream(cmd):
        yield "- Tile: WIDE: 102088678 (DR1_R1); distance: 0.12°"
        yield "- Tile: WIDE: 102088678 (DR1_R1); distance: 0.12°"  # duplicate
        yield "__EXIT__0"

    monkeypatch.setattr(retrieve_module, "build_cmd", lambda *a: ["cmd"])
    monkeypatch.setattr(retrieve_module, "stream_command", fake_stream)

    await retrieve_module.retrieve_ws(ws)
    tiles = [m for m in ws.sent if m["type"] == "tile"]
    assert len(tiles) == 1


@pytest.mark.asyncio
async def test_ws_exception(monkeypatch):
    ws = FakeWS({"targets": ["102159776"], "provider": "sas"})
    monkeypatch.setattr(retrieve_module, "build_cmd", lambda *a: ["cmd"])
    monkeypatch.setattr(retrieve_module, "stream_command", lambda cmd: BadStream())
    await retrieve_module.retrieve_ws(ws)
    assert any(m["type"] == "error" for m in ws.sent)


@pytest.mark.asyncio
async def test_ws_disconnect():
    ws = DisconnectWS({"targets": ["102159776"]})
    await retrieve_module.retrieve_ws(ws)
    assert True  # no crash = pass
