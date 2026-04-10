"""
Shared fixtures for Azulweb tests.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def tmp_workspace(tmp_path):
    """Temporary workspace."""
    return tmp_path


@pytest.fixture
def client(tmp_workspace, monkeypatch):
    """
    Init and yield a TestClient with the app, patching WORKSPACE to tmp_workspace.
    """
    import routers.crop as crop_module
    import routers.find as find_module
    import routers.process as proc_module
    import utils

    # Patch workspace path in utils and routers to use the temporary workspace
    monkeypatch.setattr(utils, "WORKSPACE", tmp_workspace)
    monkeypatch.setattr(proc_module, "ws_path", lambda: tmp_workspace)
    monkeypatch.setattr(crop_module, "ws_path", lambda: tmp_workspace)
    monkeypatch.setattr(find_module, "ws_path", lambda: tmp_workspace)

    from main import app

    # Remove the frontend route to avoid conflicts with TestClient
    routes_to_keep = [r for r in app.routes if not (hasattr(r, "name") and r.name == "frontend")]
    original_routes = app.routes[:]
    app.routes[:] = routes_to_keep

    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        yield c

    app.routes[:] = original_routes
