from __future__ import annotations

import os
import re
from pathlib import Path

IGNORE_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules", ".pytest_cache", ".ruff_cache", ".mypy_cache"}
MAX_READ_CHARS = 20000


def _resolve(root: Path, rel: str) -> Path:
    root = root.resolve()
    target = (root / rel).resolve()
    if target != root and root not in target.parents:
        raise ValueError(f"Path escapes workspace: {rel}")
    return target


def _iter_files(root: Path, start: Path):
    for dirpath, dirnames, filenames in os.walk(start):
        dirnames[:] = sorted(d for d in dirnames if d not in IGNORE_DIRS)
        for name in sorted(filenames):
            yield Path(dirpath) / name


def list_files(root: Path, path: str = ".") -> str:
    start = _resolve(root, path)
    if not start.exists():
        return f"ERROR: {path} does not exist"
    root_r = root.resolve()
    files = [p.relative_to(root_r).as_posix() for p in _iter_files(root_r, start)]
    if not files:
        return "(no files)"
    out = "\n".join(files[:300])
    if len(files) > 300:
        out += f"\n... {len(files) - 300} more"
    return out


def read_file(root: Path, path: str, start_line: int | None = None, end_line: int | None = None) -> str:
    p = _resolve(root, path)
    if not p.is_file():
        return f"ERROR: {path} is not a file"
    lines = p.read_text(errors="replace").splitlines()
    s = max((start_line or 1) - 1, 0)
    e = end_line or len(lines)
    out = "\n".join(f"{i + 1:>5}  {line}" for i, line in enumerate(lines[s:e], start=s))
    if len(out) > MAX_READ_CHARS:
        out = out[:MAX_READ_CHARS] + "\n... [truncated; use start_line/end_line]"
    return out or "(empty file)"


def search_code(root: Path, pattern: str, path: str = ".") -> str:
    try:
        rx = re.compile(pattern)
    except re.error as e:
        return f"ERROR: invalid regex: {e}"
    root_r = root.resolve()
    hits: list[str] = []
    for p in _iter_files(root_r, _resolve(root, path)):
        try:
            text = p.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        for n, line in enumerate(text.splitlines(), 1):
            if rx.search(line):
                hits.append(f"{p.relative_to(root_r).as_posix()}:{n}: {line.strip()}")
                if len(hits) >= 100:
                    return "\n".join(hits) + "\n... (100 match limit)"
    return "\n".join(hits) or "(no matches)"


def write_file(root: Path, path: str, content: str) -> str:
    p = _resolve(root, path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return f"Wrote {len(content)} chars to {path}"


def edit_file(root: Path, path: str, old_str: str, new_str: str) -> str:
    p = _resolve(root, path)
    if not p.is_file():
        return f"ERROR: {path} is not a file"
    text = p.read_text()
    count = text.count(old_str)
    if count == 0:
        return "ERROR: old_str not found"
    if count > 1:
        return f"ERROR: old_str appears {count} times; include more context so it is unique"
    p.write_text(text.replace(old_str, new_str, 1))
    return f"Edited {path}"


def write_test_file(root: Path, path: str, content: str) -> str:
    rel = Path(path)
    if rel.parts[:1] != ("tests",) or not rel.name.startswith("test_") or rel.suffix != ".py":
        return "ERROR: test files must be written to tests/test_*.py"
    return write_file(root, path, content)