import pytest

from team.tools import file_tools as ft


@pytest.mark.parametrize("path", ["../outside.txt", "a/../../outside.txt", "/etc/passwd"])
def test_paths_cannot_escape_workspace(tmp_path, path):
    ws = tmp_path / "ws"
    ws.mkdir()
    with pytest.raises(ValueError, match="escapes"):
        ft.write_file(ws, path, "x")


def test_symlink_out_of_workspace_is_blocked(tmp_path):
    ws, outside = tmp_path / "ws", tmp_path / "outside"
    ws.mkdir(), outside.mkdir()
    (ws / "link").symlink_to(outside)
    with pytest.raises(ValueError, match="escapes"):
        ft.write_file(ws, "link/evil.py", "x")
    assert not (outside / "evil.py").exists()


@pytest.mark.parametrize("path", ["tests/../src/test_x.py", "src/test_x.py", "tests/helper.py", "tests/test_x.txt"])
def test_write_test_file_only_into_tests(tmp_path, path):
    assert ft.write_test_file(tmp_path, path, "x").startswith("ERROR")


def test_write_test_file_ok(tmp_path):
    assert ft.write_test_file(tmp_path, "tests/test_t1.py", "x").startswith("Wrote")
    assert (tmp_path / "tests" / "test_t1.py").read_text() == "x"
