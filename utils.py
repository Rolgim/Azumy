"""
Utilitaires partagés : exécution de commandes avec streaming temps réel.
"""

import asyncio
import subprocess
import shlex
from typing import AsyncIterator, List
from pathlib import Path


async def stream_command(cmd: List[str], cwd: str | None = None) -> AsyncIterator[str]:
    """
    Exécute une commande et yield chaque ligne de stdout/stderr en temps réel.
    Utilisé par les endpoints WebSocket et SSE.
    """
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=cwd,
    )

    assert process.stdout is not None

    async for raw_line in process.stdout:
        line = raw_line.decode("utf-8", errors="replace").rstrip()
        if line:
            yield line

    await process.wait()
    yield f"__EXIT_CODE__{process.returncode}"


def build_azul_cmd(
    subcommand: str,
    args: List[str],
    workspace: str | None = None,
    extra_flags: dict | None = None,
) -> List[str]:
    """
    Construit la liste d'arguments pour une commande azul.
    Exemple : ["azul", "--workspace", "/path", "find", "M82"]
    """
    cmd = ["azul"]
    if workspace and workspace not in (".", "./"):
        cmd += ["--workspace", workspace]
    cmd.append(subcommand)
    cmd.extend(args)
    if extra_flags:
        for flag, value in extra_flags.items():
            if value is True:
                cmd.append(flag)
            elif value not in (None, False, ""):
                cmd += [flag, str(value)]
    return cmd


def workspace_path(workspace: str) -> Path:
    """Retourne un Path résolu et crée le dossier si besoin."""
    path = Path(workspace).expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path
