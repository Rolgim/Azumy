"""
Tests for /health and /workspace endpoints.
"""

import subprocess


class TestHealth:
    def test_health_ok(self, client, monkeypatch):
        class FakeCompleted:
            stdout = "azul 1.2.3"
            stderr = ""

        monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: FakeCompleted())
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert "azulero_version" in data
        assert data["azulero_version"] == "azul 1.2.3"

    def test_health_file_not_found(self, client, monkeypatch):
        def raise_fnf(*args, **kwargs):
            raise FileNotFoundError

        monkeypatch.setattr(subprocess, "run", raise_fnf)
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "error"
        assert "not found" in data["detail"].lower()

    def test_health_unexpected_exception(self, client, monkeypatch):
        def raise_error(*args, **kwargs):
            raise RuntimeError("boom")

        monkeypatch.setattr(subprocess, "run", raise_error)
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "error"
        assert "boom" in data["detail"]


class TestWorkspace:
    def test_info_empty_workspace(self, client, tmp_workspace):
        r = client.get(f"/workspace/info?path={tmp_workspace}")
        assert r.status_code == 200
        data = r.json()
        assert data["exists"] is True
        assert data["tiles"] == []
        assert data["total_size_mb"] == 0.0

    def test_info_nonexistent_path(self, client):
        r = client.get("/workspace/info?path=/nonexistent/path/xyz")
        assert r.status_code == 200
        data = r.json()
        assert data["exists"] is False

    def test_info_with_tile_folder(self, client, tmp_workspace):
        # Create a tile folder with some files to test the info endpoint
        tile_dir = tmp_workspace / "102159776"
        tile_dir.mkdir()
        (tile_dir / "fake.fits").write_bytes(b"FITS" * 100)
        (tile_dir / "preview.jpg").write_bytes(b"JPG" * 50)

        r = client.get(f"/workspace/info?path={tmp_workspace}")
        data = r.json()
        assert len(data["tiles"]) == 1
        assert data["tiles"][0]["index"] == "102159776"
        assert data["tiles"][0]["fits_count"] == 1
        assert "preview.jpg" in data["tiles"][0]["images"]

    def test_latest_image_not_found(self, client, tmp_workspace):
        r = client.get(f"/workspace/tile/999999999/latest-image?workspace={tmp_workspace}")
        assert r.status_code == 404

    def test_latest_image_found(self, client, tmp_workspace):
        tile_dir = tmp_workspace / "102159776"
        tile_dir.mkdir()
        img = tile_dir / "result.jpg"
        img.write_bytes(b"fake jpg")

        r = client.get(f"/workspace/tile/102159776/latest-image?workspace={tmp_workspace}")
        assert r.status_code == 200
        data = r.json()
        assert "result.jpg" in data["name"]
