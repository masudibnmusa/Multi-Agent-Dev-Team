from collections import defaultdict, deque

from team.protocol.schemas import Plan, TaskSpec


class PlanError(ValueError):
    pass


class TaskScheduler:
    """Orders tasks by dependency and tracks their status."""

    def __init__(self, plan: Plan) -> None:
        self.validate(plan)
        self.tasks: dict[str, TaskSpec] = {t.id: t for t in plan.tasks}
        self.order: list[str] = self._topo(plan)
        self.status: dict[str, str] = {t.id: "pending" for t in plan.tasks}

    @staticmethod
    def validate(plan: Plan, max_tasks: int | None = None) -> None:
        ids = [t.id for t in plan.tasks]
        if not ids:
            raise PlanError("plan has no tasks")
        if len(set(ids)) != len(ids):
            raise PlanError("duplicate task ids")
        if max_tasks and len(ids) > max_tasks:
            raise PlanError(f"plan has {len(ids)} tasks; the limit is {max_tasks}")
        known = set(ids)
        for t in plan.tasks:
            if t.id in t.depends_on:
                raise PlanError(f"{t.id} depends on itself")
            missing = [d for d in t.depends_on if d not in known]
            if missing:
                raise PlanError(f"{t.id} depends on unknown task(s): {missing}")
        TaskScheduler._topo(plan)

    @staticmethod
    def _topo(plan: Plan) -> list[str]:
        indegree = {t.id: len(set(t.depends_on)) for t in plan.tasks}
        children: dict[str, list[str]] = defaultdict(list)
        for t in plan.tasks:
            for dep in set(t.depends_on):
                children[dep].append(t.id)
        queue = deque(t.id for t in plan.tasks if indegree[t.id] == 0)
        order: list[str] = []
        while queue:
            node = queue.popleft()
            order.append(node)
            for child in children[node]:
                indegree[child] -= 1
                if indegree[child] == 0:
                    queue.append(child)
        if len(order) != len(plan.tasks):
            raise PlanError("dependency cycle detected")
        return order

    def next_ready(self) -> TaskSpec | None:
        for task_id in self.order:
            task = self.tasks[task_id]
            if self.status[task_id] == "pending" and all(self.status[d] == "done" for d in task.depends_on):
                return task
        return None

    def mark(self, task_id: str, status: str) -> None:
        self.status[task_id] = status

    def mark_failed(self, task_id: str) -> None:
        """Mark a task failed and block everything that transitively depends on it."""
        self.status[task_id] = "failed"
        queue = deque([task_id])
        while queue:
            current = queue.popleft()
            for t in self.tasks.values():
                if current in t.depends_on and self.status[t.id] == "pending":
                    self.status[t.id] = "blocked"
                    queue.append(t.id)

    def all_done(self) -> bool:
        return all(s == "done" for s in self.status.values())