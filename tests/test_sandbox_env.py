from pathlib import Path

from team.sandbox.docker_manager import local_env


def test_local_env_drops_api_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-secret")
    env = local_env(Path("/ws"))
    assert "ANTHROPIC_API_KEY" not in env
    assert env["PYTHONPATH"].startswith("/ws")
