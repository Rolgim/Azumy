import asyncio
import logging
import os
from collections.abc import AsyncIterator
from pathlib import Path

logger = logging.getLogger(__name__)

WORKSPACE = Path("workspace")
WORKSPACE.mkdir(exist_ok=True)


async def stream_command(cmd: list[str], cwd: str | None = None) -> AsyncIterator[str]:
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=cwd,
        env=env,
    )
    assert process.stdout is not None
    async for raw in process.stdout:
        line = raw.decode("utf-8", errors="replace").rstrip()
        if line:
            yield line
    await process.wait()
    yield f"__EXIT__{process.returncode}"


def build_cmd(sub: str, args: list[str], flags: dict | None = None) -> list[str]:
    cmd = ["azul", "--workspace", str(WORKSPACE), sub]
    cmd.extend(args)
    if flags:
        for k, v in flags.items():
            if v is True:
                cmd.append(k)
            elif v not in (None, False, ""):
                cmd += [k, str(v)]
    return cmd


def ws_path() -> Path:
    return WORKSPACE.resolve()
