from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ExecResult:
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False


class DockerManager:
    """Runs commands in an isolated container (no network), or locally when Docker is disabled."""

    DOCKERFILE = "FROM python:3.11-slim\nRUN pip install --no-cache-dir pytest\n"

    def __init__(self, image: str = "team-sandbox:latest", timeout: int = 120, use_docker: bool = False) -> None:
        self.image = image
        self.timeout = timeout
        self.use_docker = use_docker

    def ensure_image(self) -> None:
        if not self.use_docker:
            return
        exists = subprocess.run(["docker", "image", "inspect", self.image], capture_output=True).returncode == 0
        if not exists:
            subprocess.run(
                ["docker", "build", "-t", self.image, "-"],
                input=self.DOCKERFILE, text=True, check=True,
            )

    def run(self, workspace: Path, command: list[str]) -> ExecResult:
        workspace = workspace.resolve()
        if self.use_docker:
            cmd = ["docker", "run", "--rm", "--network", "none", "--memory", "1g", "--cpus", "1",
                   "-v", f"{workspace}:/work", "-w", "/work",
                   "-e", "PYTHONPATH=/work:/work/src", "-e", "PYTHONDONTWRITEBYTECODE=1"]
            if hasattr(os, "getuid"):
                cmd += ["--user", f"{os.getuid()}:{os.getgid()}"]
            cmd += [self.image, *command]
            env = None
        else:
            cmd = command
            env = {
                **os.environ,
                "PYTHONPATH": os.pathsep.join([str(workspace), str(workspace / "src")]),
                "PYTHONDONTWRITEBYTECODE": "1",
            }
        try:
            proc = subprocess.run(
                cmd, cwd=workspace, env=env, capture_output=True, text=True, timeout=self.timeout
            )
            return ExecResult(proc.returncode, proc.stdout, proc.stderr)
        except subprocess.TimeoutExpired:
            return ExecResult(124, "", f"Timed out after {self.timeout}s", timed_out=True)
        except FileNotFoundError as e:
            return ExecResult(127, "", f"Command not found: {e}")