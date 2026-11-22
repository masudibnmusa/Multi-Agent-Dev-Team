from pathlib import Path

from team.sandbox.docker_manager import local_env


def test_local_env_drops_api_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-secret")
    env = local_env(Path("/ws"))
    assert "ANTHROPIC_API_KEY" not in env
    assert env["PYTHONPATH"].startswith("/ws")


def test_docker_command_times_itself_out(monkeypatch, tmp_path):
    import subprocess

    from team.sandbox.docker_manager import DockerManager

    seen = {}

    def fake_run(cmd, **kw):
        seen["cmd"], seen["timeout"] = cmd, kw["timeout"]
        return subprocess.CompletedProcess(cmd, 124, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = DockerManager(timeout=10, use_docker=True).run(tmp_path, ["python", "-m", "pytest"])
    i = seen["cmd"].index("team-sandbox:latest")
    assert seen["cmd"][i + 1:i + 4] == ["timeout", "--kill-after=5", "10"]
    assert seen["timeout"] > 10
    assert result.timed_out
