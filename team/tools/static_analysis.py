from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

from team.tools.file_tools import _iter_files


def _syntax_check(workspace: Path) -> str:
    errors = []
    for path in _iter_files(workspace, workspace):
        if path.suffix != ".py":
            continue
        try:
            ast.parse(path.read_text(errors="replace"))
        except SyntaxError as e:
            errors.append(f"{path.relative_to(workspace).as_posix()}:{e.lineno}: SyntaxError: {e.msg}")
    return "\n".join(errors) or "No syntax errors (install ruff for lint checks)."


def run_static_analysis(workspace: Path) -> str:
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "ruff", "check", "--no-cache", "--output-format", "concise", "."],
            cwd=workspace, capture_output=True, text=True, timeout=60,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        return f"Static analysis failed to run: {e}\n" + _syntax_check(workspace)
    if "No module named ruff" in proc.stderr:
        return _syntax_check(workspace)
    out = (proc.stdout + proc.stderr).strip()
    return out or "ruff: no issues found."