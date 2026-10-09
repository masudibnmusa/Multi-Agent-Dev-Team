from enum import Enum


class TaskState(str, Enum):
    PENDING = "pending"
    CODING = "coding"
    REVIEWING = "reviewing"
    TESTING = "testing"
    DONE = "done"
    FAILED = "failed"


ALLOWED: dict[TaskState, set[TaskState]] = {
    TaskState.PENDING: {TaskState.CODING, TaskState.FAILED},
    TaskState.CODING: {TaskState.REVIEWING, TaskState.TESTING, TaskState.FAILED},
    TaskState.REVIEWING: {TaskState.CODING, TaskState.TESTING, TaskState.FAILED},
    TaskState.TESTING: {TaskState.CODING, TaskState.DONE, TaskState.FAILED},
    TaskState.DONE: set(),
    TaskState.FAILED: set(),
}


class InvalidTransition(RuntimeError):
    pass


class TaskWorkflow:
    """State machine for one task: plan -> code -> review -> test -> done."""

    def __init__(self, task_id: str) -> None:
        self.task_id = task_id
        self.state = TaskState.PENDING
        self.rounds = 0
        self.history: list[str] = []

    def transition(self, to: TaskState) -> None:
        if to not in ALLOWED[self.state]:
            raise InvalidTransition(f"{self.task_id}: {self.state.value} -> {to.value} is not allowed")
        self.state = to

    def start_round(self) -> None:
        self.rounds += 1
        self.transition(TaskState.CODING)

    def begin_review(self) -> None:
        self.transition(TaskState.REVIEWING)

    def begin_testing(self) -> None:
        self.transition(TaskState.TESTING)

    def complete(self) -> None:
        self.transition(TaskState.DONE)

    def fail(self) -> None:
        if self.state not in (TaskState.DONE, TaskState.FAILED):
            self.transition(TaskState.FAILED)

    def log(self, note: str) -> None:
        self.history.append(f"[round {self.rounds} / {self.state.value}] {note}")