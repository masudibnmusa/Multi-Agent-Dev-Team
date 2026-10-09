import json
import re
import threading
from pathlib import Path
from typing import Any

from team.protocol.schemas import Plan, TaskSpec


class SharedStore:
    """Blackboard: request, plan, task status, and per-task artifacts."""

    def __init__(self, snapshot_dir: Path | None = None) -> None:
        self._lock = threading.RLock()
        self.request = ""
        self.plan: Plan | None = None
        self.task_status: dict[str, str] = {}
        self.artifacts: dict[str, dict[str, Any]] = {}
        self.snapshot_dir = snapshot_dir
        self._snap_count = 0

    def set_request(self, request: str) -> None:
        with self._lock:
            self.request = request

    def set_plan(self, plan: Plan) -> None:
        with self._lock:
            self.plan = plan
            self.task_status = {t.id: "pending" for t in plan.tasks}

    def get_task(self, task_id: str) -> TaskSpec:
        if self.plan is None:
            raise KeyError("No plan set")
        for task in self.plan.tasks:
            if task.id == task_id:
                return task
        raise KeyError(f"Unknown task: {task_id}")

    def set_status(self, task_id: str, status: str) -> None:
        with self._lock:
            self.task_status[task_id] = status

    def add_artifact(self, task_id: str, key: str, value: Any) -> None:
        with self._lock:
            self.artifacts.setdefault(task_id, {})[key] = value

    def to_dict(self) -> dict[str, Any]:
        with self._lock:
            return {
                "request": self.request,
                "plan": self.plan.model_dump() if self.plan else None,
                "task_status": dict(self.task_status),
                "artifacts": {
                    tid: {k: (v if len(str(v)) < 5000 else str(v)[:5000] + "…") for k, v in a.items()}
                    for tid, a in self.artifacts.items()
                },
            }

    def snapshot(self, label: str) -> Path | None:
        if not self.snapshot_dir:
            return None
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        self._snap_count += 1
        safe = re.sub(r"[^a-zA-Z0-9_-]+", "_", label)
        path = self.snapshot_dir / f"{self._snap_count:02d}_{safe}.json"
        path.write_text(json.dumps(self.to_dict(), indent=2))
        return path