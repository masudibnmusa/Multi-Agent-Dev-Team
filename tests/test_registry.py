from team.tools.registry import ToolContext, ToolRegistry


def test_coder_cannot_write_tests(tmp_path):
    reg = ToolRegistry(ToolContext(tmp_path, sandbox=None))
    for path in ("tests/test_t1.py", "src/../tests/test_t1.py"):
        assert reg.execute("coder", "write_file", {"path": path, "content": "x"}).startswith("ERROR")
    assert not (tmp_path / "tests").exists()
    assert reg.execute("coder", "write_file", {"path": "app.py", "content": "x"}).startswith("Wrote")
