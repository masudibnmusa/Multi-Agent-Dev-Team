from __future__ import annotations

import subprocess
from pathlib import Path


class GitError(RuntimeError):
    pass


def _git(root: Path, *args: str, check: bool = True) -> str:
    proc = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise GitError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout


def current_branch(root: Path) -> str:
    return _git(root, "rev-parse", "--abbrev-ref", "HEAD").strip()


def head_sha(root: Path) -> str:
    return _git(root, "rev-parse", "HEAD").strip()


def commit_all(root: Path, message: str, allow_empty: bool = False) -> bool:
    _git(root, "add", "-A")
    if not allow_empty and subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=root).returncode == 0:
        return False  # nothing to commit
    args = ["-c", "user.name=dev-team", "-c", "user.email=team@local", "commit", "-m", message]
    if allow_empty:
        args.append("--allow-empty")
    _git(root, *args)
    return True


def init_repo(root: Path) -> str:
    """Ensure root is a git repo with at least one commit. Returns the base branch name."""
    root.mkdir(parents=True, exist_ok=True)
    if not (root / ".git").exists():
        _git(root, "init", "-b", "main")
    gitignore = root / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("__pycache__/\n.pytest_cache/\n.ruff_cache/\n.venv/\n")
    has_commits = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD"], cwd=root, capture_output=True
    ).returncode == 0
    if not has_commits:
        commit_all(root, "Initial commit", allow_empty=True)
    return current_branch(root)


def create_branch(root: Path, name: str, base: str) -> None:
    _git(root, "checkout", "-B", name, base)


def checkout(root: Path, name: str) -> None:
    _git(root, "checkout", name)


def merge(root: Path, branch: str, base: str, message: str) -> None:
    _git(root, "checkout", base)
    _git(root, "-c", "user.name=dev-team", "-c", "user.email=team@local", "merge", "--no-ff", "-m", message, branch)


def diff_against(root: Path, base: str) -> str:
    _git(root, "add", "-A")
    return _git(root, "diff", "--cached", base)


def changed_files(root: Path, base: str) -> list[str]:
    _git(root, "add", "-A")
    return [f for f in _git(root, "diff", "--cached", "--name-only", base).splitlines() if f]


def final_patch(root: Path, from_sha: str) -> str:
    return _git(root, "diff", from_sha, "HEAD")