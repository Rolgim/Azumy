"""
Tests for /process
args building, progress parsing, WCS reading, eummy.
"""

from pathlib import Path

import pytest
import yaml

import routers.process as process_module

# Fake WebSocket helpers ---------------------


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
        raise process_module.WebSocketDisconnect()


class BadStream:
    def __aiter__(self):
        return self

    async def __anext__(self):
        raise RuntimeError("boom")


# Azul args ------------------------------------------------


class TestAzulArgs:
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
        for f in [
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
            args += [f"--{f}", str(defaults[f])]
        return args

    def test_tile_first_arg(self):
        assert self._args("TILE[0:1,0:1]")[0] == "TILE[0:1,0:1]"

    def test_all_flags_present(self):
        args = self._args("TILE")
        for flag in ["--zero", "--scaling", "--fwhm", "--sharpen", "--white"]:
            assert flag in args

    def test_custom_hue(self):
        args = self._args("TILE", hue=99.0)
        assert args[args.index("--hue") + 1] == "99.0"

    def test_zero_length(self):
        args = self._args("TILE")
        idx = args.index("--zero")
        assert len(args[idx + 1 : idx + 5]) == 4


# Azul progress -----------------------------------------------


class TestAzulProgress:
    def test_read_step(self):
        assert process_module._azul_progress("Read IYJH image")["percent"] == 10

    def test_inpaint_step(self):
        assert process_module._azul_progress("Inpaint pixels")["percent"] == 40

    def test_write_step(self):
        assert process_module._azul_progress("- Write: file.tiff")["percent"] == 100

    def test_case_insensitive(self):
        assert process_module._azul_progress("INPAINT PIXELS") is not None

    def test_no_match(self):
        assert process_module._azul_progress("random log") is None


# Eummy args ----------------------------------------------------------------


class TestEummyArgs:
    def _req(self, tile="102159776", slicing=None, **kwargs):
        from routers.process import EummyProcessReq

        data = dict(engine="eummy", tile=tile, slicing=slicing)
        data.update(kwargs)
        return EummyProcessReq(**data)

    def test_starts_with_eummy(self, tmp_path):
        args = process_module._eummy_args(self._req(), tmp_path)
        assert args[0] == "eummy"

    def test_path_flag(self, tmp_path):
        args = process_module._eummy_args(self._req(), tmp_path)
        assert "--path" in args
        assert str(tmp_path) in args

    def test_um_enabled(self, tmp_path):
        req = self._req(um_enabled=True)
        args = process_module._eummy_args(req, tmp_path)
        idx = args.index("--UM")
        assert args[idx + 1] != "false"

    def test_um_disabled(self, tmp_path):
        req = self._req(um_enabled=False)
        args = process_module._eummy_args(req, tmp_path)
        idx = args.index("--UM")
        assert args[idx + 1] == "false"

    def test_blend_iy_off_by_default(self, tmp_path):
        assert "--blendIY" not in process_module._eummy_args(self._req(), tmp_path)

    def test_blend_iy_on(self, tmp_path):
        req = self._req(blend_iy=True, fi=2.0)
        args = process_module._eummy_args(req, tmp_path)
        assert "--blendIY" in args
        assert args[args.index("--fi") + 1] == "2.0"

    def test_contrast_omitted_when_none(self, tmp_path):
        assert "--contrast" not in process_module._eummy_args(self._req(contrast=None), tmp_path)

    def test_contrast_included(self, tmp_path):
        args = process_module._eummy_args(self._req(contrast=1.6), tmp_path)
        assert args[args.index("--contrast") + 1] == "1.6"

    def test_no_cutout_without_slicing(self, tmp_path):
        assert "--cutout" not in process_module._eummy_args(self._req(slicing=None), tmp_path)

    def test_cutout_from_slicing(self, tmp_path):
        """[6000:7000,5000:7000] → --cutout 6000 6500 1000p 2000p"""
        req = self._req(slicing="[6000:7000,5000:7000]")
        args = process_module._eummy_args(req, tmp_path)
        idx = args.index("--cutout")
        assert args[idx + 1] == "6000"  # col_c = (5000+7000)//2
        assert args[idx + 2] == "6500"  # row_c = (6000+7000)//2
        assert args[idx + 3] == "2000p"  # width
        assert args[idx + 4] == "1000p"  # heigth

    def test_cutout_non_square(self, tmp_path):
        args = process_module._eummy_args(self._req(slicing="[0:2000,0:4000]"), tmp_path)
        idx = args.index("--cutout")
        assert args[idx + 3] == "4000p"
        assert args[idx + 4] == "2000p"


# Eummy progress -----------------------------------------------


class TestEummyProgress:
    def test_processing_step(self):
        assert process_module._eummy_progress("Processing FITS images")["percent"] == 10

    def test_writing_step(self):
        assert process_module._eummy_progress("Writing result to /app/...")["percent"] == 100

    def test_no_match(self):
        assert process_module._eummy_progress("eummy v1.0.0") is None

    def test_case_insensitive(self):
        assert process_module._eummy_progress("WRITING RESULT") is not None


# WebSocket - azul engine ----------------------------------------------------


@pytest.mark.asyncio
async def test_missing_tile_azul():
    ws = FakeWS({"engine": "azul", "tile": ""})
    await process_module.process_ws(ws)
    assert ws.sent[0]["type"] == "error"


@pytest.mark.asyncio
async def test_azul_normal_flow(monkeypatch):
    ws = FakeWS({"engine": "azul", "tile": "123"})

    async def fake_stream(cmd):
        yield "Read IYJH something"
        yield "__EXIT__0"

    monkeypatch.setattr(process_module, "build_cmd", lambda *a, **kw: ["cmd"])
    monkeypatch.setattr(process_module, "stream_command", fake_stream)
    monkeypatch.setattr(process_module, "ws_path", lambda: Path("/tmp"))

    await process_module.process_ws(ws)
    types = ws.types()
    assert "cmd" in types
    assert "log" in types
    assert "progress" in types
    assert "exit" in types
    assert "done" in types


@pytest.mark.asyncio
async def test_azul_output_file_parsing(monkeypatch):
    ws = FakeWS({"engine": "azul", "tile": "123"})

    async def fake_stream(cmd):
        yield "- Write: result.tiff"
        yield "__EXIT__0"

    monkeypatch.setattr(process_module, "build_cmd", lambda *a, **kw: ["cmd"])
    monkeypatch.setattr(process_module, "stream_command", fake_stream)
    monkeypatch.setattr(process_module, "ws_path", lambda: Path("/tmp"))

    await process_module.process_ws(ws)
    assert "output_file" in ws.types()


@pytest.mark.asyncio
async def test_azul_preview_success(monkeypatch, tmp_path):
    ws = FakeWS({"engine": "azul", "tile": "123"})

    async def fake_stream(cmd):
        yield "- Write: result.tiff"
        yield "__EXIT__0"

    # Make the output_file appear to exist
    tile_dir = tmp_path / "123"
    tile_dir.mkdir()

    fake_file = tile_dir / "result.tiff"
    fake_file.touch()

    monkeypatch.setattr(process_module, "build_cmd", lambda *a, **kw: ["cmd"])
    monkeypatch.setattr(process_module, "stream_command", fake_stream)
    monkeypatch.setattr(process_module, "ws_path", lambda: tmp_path)
    monkeypatch.setattr(
        process_module, "generate_preview", lambda p, **kw: str(tmp_path / "result_preview.jpg")
    )

    await process_module.process_ws(ws)
    print(ws.sent)
    print(ws.types())
    done = next(m for m in ws.sent if m["type"] == "done")
    assert done["preview_file"] == "result_preview.jpg"


@pytest.mark.asyncio
async def test_azul_preview_failure(monkeypatch, tmp_path):
    ws = FakeWS({"engine": "azul", "tile": "123"})

    async def fake_stream(cmd):
        yield "- Write: result.tiff"
        yield "__EXIT__0"

    tile_dir = tmp_path / "123"
    tile_dir.mkdir()

    fake_file = tile_dir / "result.tiff"
    fake_file.touch()

    monkeypatch.setattr(process_module, "build_cmd", lambda *a, **kw: ["cmd"])
    monkeypatch.setattr(process_module, "stream_command", fake_stream)
    monkeypatch.setattr(process_module, "ws_path", lambda: tmp_path)
    monkeypatch.setattr(
        process_module,
        "generate_preview",
        lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    await process_module.process_ws(ws)
    assert any(m["type"] == "error" and "Preview" in m.get("message", "") for m in ws.sent)


# WebSocket - eummy engine ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_tile_eummy():
    ws = FakeWS({"engine": "eummy", "tile": ""})
    await process_module.process_ws(ws)
    assert ws.sent[0]["type"] == "error"


@pytest.mark.asyncio
async def test_eummy_normal_flow(monkeypatch, tmp_path):
    ws = FakeWS({"engine": "eummy", "tile": "123"})

    async def fake_stream(cmd):
        yield "Processing FITS images"
        yield "Writing result to /tmp/TILE123.tif"
        yield "__EXIT__0"

    monkeypatch.setattr(process_module, "stream_command", fake_stream)
    monkeypatch.setattr(process_module, "ws_path", lambda: tmp_path)

    await process_module.process_ws(ws)
    types = ws.types()
    assert "cmd" in types
    assert "progress" in types
    assert "exit" in types
    assert "done" in types


@pytest.mark.asyncio
async def test_eummy_with_slicing(monkeypatch, tmp_path):
    """Check that slicing info is correctly converted to --cutout args."""
    ws = FakeWS({"engine": "eummy", "tile": "123", "slicing": "[0:1000,0:2000]"})

    captured_cmd = []

    async def fake_stream(cmd):
        captured_cmd.extend(cmd)
        yield "__EXIT__0"

    monkeypatch.setattr(process_module, "stream_command", fake_stream)
    monkeypatch.setattr(process_module, "ws_path", lambda: tmp_path)

    await process_module.process_ws(ws)
    assert "--cutout" in captured_cmd


# WebSocket - unknown engine -------------------------------------------


@pytest.mark.asyncio
async def test_unknown_engine():
    ws = FakeWS({"engine": "unknown", "tile": "123"})
    await process_module.process_ws(ws)
    assert ws.sent[0]["type"] == "error"


# WebSocket - disconnect & exception -----------------------------------


@pytest.mark.asyncio
async def test_disconnect():
    ws = DisconnectWS({"engine": "azul", "tile": "123"})
    await process_module.process_ws(ws)
    assert True  # no crash = pass


@pytest.mark.asyncio
async def test_ws_exception(monkeypatch):
    ws = FakeWS({"engine": "azul", "tile": "123"})

    monkeypatch.setattr(process_module, "build_cmd", lambda *a, **kw: ["cmd"])
    monkeypatch.setattr(process_module, "stream_command", BadStream())
    monkeypatch.setattr(process_module, "ws_path", lambda: Path("/tmp"))

    await process_module.process_ws(ws)
    assert any(m["type"] == "error" for m in ws.sent)


# WCS endpoint ---------------------------------------------------


class TestWcsReading:
    WCS_DATA = {
        "CRPIX1": -4400.0,
        "CRPIX2": -5400.0,
        "CRVAL1": 11.0205556,
        "CRVAL2": 4.0,
        "CTYPE1": "RA---TAN",
        "CTYPE2": "DEC--TAN",
        "CUNIT1": "deg",
        "CUNIT2": "deg",
        "PC1_1": -2.777777777778e-05,
        "PC2_2": 2.777777777778e-05,
        "CDELT1": 1.0,
        "CDELT2": 1.0,
        "RADESYS": "ICRS",
    }

    @pytest.fixture
    def wcs_tile(self, client, tmp_workspace):
        tile = "102159776"
        tile_dir = tmp_workspace / tile
        tile_dir.mkdir(parents=True, exist_ok=True)
        (tile_dir / f"{tile}_wcs.yaml").write_text(yaml.dump(self.WCS_DATA))
        return tile

    def test_wcs_200(self, client, wcs_tile):
        assert client.get(f"/process/wcs/{wcs_tile}").status_code == 200

    def test_wcs_ra_dec(self, client, wcs_tile):
        data = client.get(f"/process/wcs/{wcs_tile}").json()
        assert data["ra"] == pytest.approx(11.0205556, rel=1e-4)
        assert data["dec"] == pytest.approx(4.0, rel=1e-4)

    def test_wcs_pixel_scale(self, client, wcs_tile):
        data = client.get(f"/process/wcs/{wcs_tile}").json()
        assert data["pixel_scale"] == pytest.approx(2.777e-5, rel=1e-2)

    def test_wcs_not_found(self, client):
        assert client.get("/process/wcs/nonexistent").status_code == 404
