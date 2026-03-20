import asyncio
import os
from typing import AsyncIterator
from pathlib import Path


async def stream_command(cmd: list[str], cwd: str | None = None) -> AsyncIterator[str]:
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"  # force Python to flush output immediately

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


def build_azul_cmd(sub: str, args: list[str], workspace: str = ".", flags: dict | None = None) -> list[str]:
    cmd = ["azul"]
    if workspace and workspace not in (".", "./"):
        cmd += ["--workspace", workspace]
    cmd.append(sub)
    cmd.extend(args)
    if flags:
        for k, v in flags.items():
            if v is True:       cmd.append(k)
            elif v not in (None, False, ""): cmd += [k, str(v)]
    return cmd


def ws_path(workspace: str) -> Path:
    p = Path(workspace).expanduser().resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p