from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

from team.sandbox.docker_manager import DockerManager


@dataclass
class TestRun:
    __test__ = False  # stop pytest from trying to collect this class

    passed: bool
    summary: str
    output_tail: str
    returncode: int


def _summary_line(output: str) -> str:
    for line in reversed(output.splitlines()):
        if re.search(r"\d+ (passed|failed|error)|no tests ran", line):
            return line.strip(" =")
    return ""


def run_tests(sandbox: DockerManager, workspace: Path, target: str = "tests") -> TestRun:
    python = "python" if sandbox.use_docker else sys.executable
    result = sandbox.run(
        workspace,
        [python, "-m", "pytest", "-q", "--tb=short", "-p", "no:cacheprovider", target],
    )
    output = (result.stdout + "\n" + result.stderr).strip()
    summary = _summary_line(output)
    if not summary:
        summary = "timed out" if result.timed_out else f"exit code {result.returncode}"
    return TestRun(
        passed=result.returncode == 0,
        summary=summary,
        output_tail=output[-4000:],
        returncode=result.returncode,
    )