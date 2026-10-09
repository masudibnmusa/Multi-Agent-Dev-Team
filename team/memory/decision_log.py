import time
from dataclasses import dataclass, field


@dataclass
class Decision:
    author: str
    decision: str
    rationale: str = ""
    task_id: str | None = None
    timestamp: float = field(default_factory=time.time)


class DecisionLog:
    """Records why choices were made so agents don't re-litigate them."""

    def __init__(self) -> None:
        self._entries: list[Decision] = []

    def add(self, author: str, decision: str, rationale: str = "", task_id: str | None = None) -> None:
        self._entries.append(Decision(author, decision, rationale, task_id))

    def for_task(self, task_id: str) -> list[Decision]:
        return [d for d in self._entries if d.task_id == task_id]

    def render(self, task_id: str | None = None, limit: int = 15) -> str:
        entries = self._entries if task_id is None else self.for_task(task_id)
        lines = []
        for d in entries[-limit:]:
            why = f" ({d.rationale})" if d.rationale else ""
            lines.append(f"- [{d.author}] {d.decision}{why}")
        return "\n".join(lines)