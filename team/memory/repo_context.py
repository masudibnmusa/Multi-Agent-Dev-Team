import ast
from pathlib import Path

from team.tools.file_tools import _iter_files


def _py_symbols(path: Path) -> list[str]:
    try:
        tree = ast.parse(path.read_text(errors="replace"))
    except (SyntaxError, ValueError):
        return []
    out: list[str] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.append(f"def {node.name}({', '.join(a.arg for a in node.args.args)})")
        elif isinstance(node, ast.ClassDef):
            methods = [n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
            out.append(f"class {node.name}" + (f" [{', '.join(methods)}]" if methods else ""))
    return out


class RepoContext:
    """Compact repo map (files + top-level symbols) and coding conventions."""

    def __init__(self, workspace: Path, conventions: list[str] | None = None, max_files: int = 150) -> None:
        self.workspace = workspace.resolve()
        self.conventions = conventions or []
        self.max_files = max_files
        self._map: str | None = None

    def refresh(self) -> None:
        lines: list[str] = []
        files = list(_iter_files(self.workspace, self.workspace))
        for path in files[: self.max_files]:
            rel = path.relative_to(self.workspace).as_posix()
            lines.append(rel)
            # Hide test internals: they add noise (and would leak into the blind tester's view).
            if path.suffix == ".py" and not rel.startswith("tests/"):
                lines.extend(f"    {sym}" for sym in _py_symbols(path))
        if len(files) > self.max_files:
            lines.append(f"... {len(files) - self.max_files} more files")
        self._map = "\n".join(lines) if lines else "(empty workspace)"

    def render(self) -> str:
        if self._map is None:
            self.refresh()
        return self._map or "(empty workspace)"