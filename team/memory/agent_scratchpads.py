from collections import defaultdict


class Scratchpads:
    """Private working notes per (agent, task)."""

    def __init__(self) -> None:
        self._notes: dict[tuple[str, str | None], list[str]] = defaultdict(list)

    def add(self, role: str, note: str, task_id: str | None = None) -> None:
        self._notes[(role, task_id)].append(note)

    def get(self, role: str, task_id: str | None = None) -> list[str]:
        return list(self._notes[(role, task_id)])

    def render(self, role: str, task_id: str | None = None, limit: int = 5) -> str:
        return "\n".join(f"- {n}" for n in self._notes[(role, task_id)][-limit:])

    def clear(self, role: str, task_id: str | None = None) -> None:
        self._notes.pop((role, task_id), None)