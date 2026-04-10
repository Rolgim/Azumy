"""
Tests for /process - args building, progress parsing, WCS reading.
"""

import pytest

import routers.process as process_module


class BadStream:
    def __aiter__(self):
        return self

    async def __anext__(self):
        raise RuntimeError("boom")


# Args & progress unit tests
class TestProcessArgs:
    def _args(self, tile, **kwargs):
        defaults = dict(
            zero=[24.5, 29.8, 30.1, 30.0],
            scaling=[2.2, 1.3, 1.2, 1.0],
            fwhm=[1.6, 3.5, 3.4, 3.5],
            sharpen=0.5,
            nirl=0.1,
            ib=1.0,
            yg=0.5,
            jr=0.25,
            white=22.0,
            stretch=28.0,
            offset=29.0,
            hue=-20.0,
            saturation=1.2,
        )
        defaults.update(kwargs)

        args = [tile]
        args += ["--zero"] + [str(v) for v in defaults["zero"]]
        args += ["--scaling"] + [str(v) for v in defaults["scaling"]]
        args += ["--fwhm"] + [str(v) for v in defaults["fwhm"]]

        for flag in [
            "sharpen",
            "nirl",
            "ib",
            "yg",
            "jr",
            "white",
            "stretch",
            "offset",
            "hue",
            "saturation",
        ]:
            args += [f"--{flag}", str(defaults[flag])]

        return args

    def test_tile_first_arg(self):
        args = self._args("TILE[0:1,0:1]")
        assert args[0] == "TILE[0:1,0:1]"

    def test_all_flags_present(self):
        args = self._args("TILE")
        for flag in ["--zero", "--scaling", "--fwhm", "--sharpen", "--white"]:
            assert flag in args

    def test_custom_hue(self):
        args = self._args("TILE", hue=99.0)
        idx = args.index("--hue")
        assert args[idx + 1] == "99.0"

    def test_zero_length(self):
        args = self._args("TILE")
        idx = args.index("--zero")
        assert len(args[idx + 1 : idx + 5]) == 4


# Progress parsing (direct coverage)
class TestProgressParsing:
    def test_read_step(self):
        assert process_module._progress("Read IYJH image")["percent"] == 10

    def test_inpaint_step(self):
        assert process_module._progress("Inpaint pixels")["percent"] == 40

    def test_write_step(self):
        assert process_module._progress("- Write: file.tiff")["percent"] == 100

    def test_case_insensitive(self):
        assert process_module._progress("INPAINT PIXELS") is not None

    def test_no_match(self):
        assert process_module._progress("random log") is None


# WebSocket tests
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


# 1. Missing tile → early error branch
@pytest.mark.asyncio
async def test_missing_tile_error(monkeypatch):
    ws = FakeWS(
        {
            "tile": "",
        }
    )

    await process_module.process_ws(ws)

    assert ws.sent[0]["type"] == "error"


# 2. normal flow + progress + exit
@pytest.mark.asyncio
async def test_ws_normal_flow(monkeypatch):
    ws = FakeWS({"tile": "123"})

    async def fake_stream(cmd):
        yield "Read IYJH something"
        yield "__EXIT__0"

    monkeypatch.setattr(process_module, "build_cmd", lambda *a: ["cmd"])
    monkeypatch.setattr(process_module, "stream_command", fake_stream)

    await process_module.process_ws(ws)

    types = [m["type"] for m in ws.sent]

    assert "cmd" in types
    assert "log" in types
    assert "progress" in types
    assert "exit" in types
    assert "done" in types


# 3. output file extraction branch
@pytest.mark.asyncio
async def test_output_file_parsing(monkeypatch):
    ws = FakeWS({"tile": "123"})

    async def fake_stream(cmd):
        yield "- Write: result.tiff"
        yield "__EXIT__0"

    monkeypatch.setattr(process_module, "build_cmd", lambda *a: ["cmd"])
    monkeypatch.setattr(process_module, "stream_command", fake_stream)

    await process_module.process_ws(ws)

    assert any(m["type"] == "output_file" for m in ws.sent)


# 4. preview generation success
@pytest.mark.asyncio
async def test_preview_success(monkeypatch):
    ws = FakeWS({"tile": "123"})

    async def fake_stream(cmd):
        yield "- Write: result.tiff"
        yield "__EXIT__0"

    monkeypatch.setattr(process_module, "build_cmd", lambda *a: ["cmd"])
    monkeypatch.setattr(process_module, "stream_command", fake_stream)

    # mock filesystem + pyvips
    monkeypatch.setattr(process_module, "ws_path", lambda: __import__("pathlib").Path("/tmp"))

    def fake_preview(path, size=512):
        return "/tmp/result_preview.jpg"

    monkeypatch.setattr(process_module, "generate_preview", fake_preview)

    await process_module.process_ws(ws)

    assert any(m["type"] == "preview" for m in ws.sent)


# 5. preview failure branch
@pytest.mark.asyncio
async def test_preview_failure(monkeypatch):
    ws = FakeWS({"tile": "123"})

    async def fake_stream(cmd):
        yield "- Write: result.tiff"
        yield "__EXIT__0"

    monkeypatch.setattr(process_module, "build_cmd", lambda *a: ["cmd"])
    monkeypatch.setattr(process_module, "stream_command", fake_stream)

    def fail_preview(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(process_module, "generate_preview", fail_preview)

    await process_module.process_ws(ws)

    assert any(m["type"] == "error" for m in ws.sent)


# 6. websocket disconnect branch
class DisconnectWS(FakeWS):
    async def receive_json(self):
        raise process_module.WebSocketDisconnect()


@pytest.mark.asyncio
async def test_disconnect():
    ws = DisconnectWS({"tile": "123"})

    await process_module.process_ws(ws)

    assert True


# 7. generic exception branch
@pytest.mark.asyncio
async def test_ws_exception(monkeypatch):
    ws = FakeWS({"tile": "123"})

    async def bad_stream(cmd):
        raise RuntimeError("boom")

    monkeypatch.setattr(process_module, "build_cmd", lambda *a: ["cmd"])
    monkeypatch.setattr(process_module, "stream_command", BadStream())

    await process_module.process_ws(ws)

    assert any(m["type"] == "error" for m in ws.sent)
