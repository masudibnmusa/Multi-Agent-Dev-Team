import pytest

from team.tools import git_tools as g


def test_fresh_workspace(tmp_path):
    assert g.init_repo(tmp_path / "ws") == "main"
    assert (tmp_path / "ws" / ".gitignore").exists()


def test_existing_repo_guards(tmp_path):
    g.init_repo(tmp_path)
    (tmp_path / ".gitignore").unlink()
    g.commit_all(tmp_path, "drop gitignore")
    assert g.init_repo(tmp_path) == "main"          # clean repo: accepted, untouched
    assert not (tmp_path / ".gitignore").exists()

    (tmp_path / "mine.txt").write_text("user work")
    with pytest.raises(g.GitError, match="uncommitted"):
        g.init_repo(tmp_path)
    (tmp_path / "mine.txt").unlink()

    g.checkout(tmp_path, g.head_sha(tmp_path))       # detach
    with pytest.raises(g.GitError, match="detached"):
        g.init_repo(tmp_path)
