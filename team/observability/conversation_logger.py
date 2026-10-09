import json
import time
from pathlib import Path
from typing import Any

from team.protocol.messages import Message


def _shorten(value: Any, limit: int = 1500) -> Any:
    if isinstance(value, str):
        return value if len(value) <= limit else value[:limit] + f"…[+{len(value) - limit} chars]"
    if isinstance(value, dict):
        return {k: _shorten(v, limit) for k, v in value.items()}
    if isinstance(value, list):
        return [_shorten(v, limit) for v in value[:50]]
    return value


class ConversationLogger:
    """Writes the typed-message transcript and low-level events as JSONL."""

    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir
        run_dir.mkdir(parents=True, exist_ok=True)
        self.messages_path = run_dir / "messages.jsonl"
        self.events_path = run_dir / "events.jsonl"
        self.started = time.time()

    def _append(self, path: Path, record: dict) -> None:
        with path.open("a") as f:
            f.write(json.dumps(record, default=str) + "\n")

    def log_message(self, msg: Message) -> None:
        self._append(self.messages_path, msg.model_dump(mode="json"))

    def event(self, agent: str, kind: str, data: dict | None = None) -> None:
        self._append(self.events_path, {
            "t": time.time(), "agent": agent, "kind": kind, "data": _shorten(data or {}),
        })