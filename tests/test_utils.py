"""
Tests for utils.py - build_cmd, stream_command, ws_path.
"""

import asyncio
from pathlib import Path

from utils import WORKSPACE, build_cmd, stream_command, ws_path


class TestBuildCmd:
    def test_simple_subcommand(self):
        cmd = build_cmd("find", ["M82"])
        assert cmd[0] == "azul"
        assert "--workspace" in cmd
        assert "find" in cmd
        assert "M82" in cmd

    def test_workspace_is_included(self):
        cmd = build_cmd("find", ["M82"])
        idx = cmd.index("--workspace")
        assert cmd[idx + 1] == str(WORKSPACE)

    def test_args_are_appended(self):
        cmd = build_cmd("retrieve", ["--from", "sas", "102159776"])
        assert "--from" in cmd
        assert "sas" in cmd
        assert "102159776" in cmd

    def test_flags_true(self):
        cmd = build_cmd("process", ["tile123"], flags={"--stretch": True})
        assert "--stretch" in cmd

    def test_flags_false_excluded(self):
        cmd = build_cmd("process", ["tile123"], flags={"--stretch": False})
        assert "--stretch" not in cmd

    def test_flags_none_excluded(self):
        cmd = build_cmd("process", ["tile123"], flags={"--output": None})
        assert "--output" not in cmd

    def test_flags_with_value(self):
        cmd = build_cmd("process", ["tile123"], flags={"--hue": -20})
        assert "--hue" in cmd
        assert "-20" in cmd

    def test_order(self):
        cmd = build_cmd("find", ["obj1", "obj2"])
        find_idx = cmd.index("find")
        assert cmd[find_idx + 1] == "obj1"
        assert cmd[find_idx + 2] == "obj2"


class TestWsPath:
    def test_returns_path(self):
        path = ws_path()
        assert isinstance(path, Path)

    def test_workspace_exists(self):
        path = ws_path()
        assert path.exists()


class TestStreamCommand:
    def test_simple_echo(self):
        async def run():
            lines = []
            async for line in stream_command(["echo", "hello world"]):
                lines.append(line)
            return lines

        lines = asyncio.run(run())
        assert "hello world" in lines
        assert any(line.startswith("__EXIT__0") for line in lines)

    def test_exit_code_nonzero(self):
        async def run():
            lines = []
            async for line in stream_command(["bash", "-c", "exit 1"]):
                lines.append(line)
            return lines

        lines = asyncio.run(run())
        assert "__EXIT__1" in lines

    def test_multiline_output(self):
        async def run():
            lines = []
            async for line in stream_command(["bash", "-c", "echo line1; echo line2; echo line3"]):
                lines.append(line)
            return lines

        lines = asyncio.run(run())
        assert "line1" in lines
        assert "line2" in lines
        assert "line3" in lines

    def test_empty_lines_filtered(self):
        async def run():
            lines = []
            async for line in stream_command(["bash", "-c", "echo; echo hello; echo"]):
                lines.append(line)
            return lines

        lines = asyncio.run(run())
        # Empty lines should be filtered
        assert "" not in lines
        assert "hello" in lines
