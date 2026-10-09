import pytest

from team.orchestrator.task_scheduler import PlanError, TaskScheduler
from team.orchestrator.workflow import InvalidTransition, TaskState, TaskWorkflow
from team.protocol.schemas import Plan, TaskSpec


def _task(tid, deps=()):
    return TaskSpec(id=tid, title=tid, description="d", acceptance_criteria=["ok"], depends_on=list(deps))


def _plan(*tasks):
    return Plan(summary="s", tasks=list(tasks))


# ---------- workflow state machine ----------
def test_happy_path():
    wf = TaskWorkflow("T1")
    wf.start_round()
    wf.begin_review()
    wf.begin_testing()
    wf.complete()
    assert wf.state == TaskState.DONE
    assert wf.rounds == 1


def test_review_rejection_loops_back_to_coding():
    wf = TaskWorkflow("T1")
    wf.start_round()
    wf.begin_review()
    wf.start_round()  # REVIEWING -> CODING
    assert wf.rounds == 2
    assert wf.state == TaskState.CODING


def test_invalid_transition_raises():
    wf = TaskWorkflow("T1")
    with pytest.raises(InvalidTransition):
        wf.begin_testing()  # PENDING -> TESTING is not allowed


def test_done_is_terminal():
    wf = TaskWorkflow("T1")
    wf.start_round()
    wf.begin_testing()
    wf.complete()
    with pytest.raises(InvalidTransition):
        wf.start_round()


def test_fail_is_idempotent():
    wf = TaskWorkflow("T1")
    wf.fail()
    wf.fail()
    assert wf.state == TaskState.FAILED


# ---------- scheduler ----------
def test_dependency_order():
    sched = TaskScheduler(_plan(_task("T2", ["T1"]), _task("T1")))
    first = sched.next_ready()
    assert first.id == "T1"
    sched.mark("T1", "done")
    assert sched.next_ready().id == "T2"
    sched.mark("T2", "done")
    assert sched.next_ready() is None
    assert sched.all_done()


def test_cycle_detected():
    with pytest.raises(PlanError):
        TaskScheduler(_plan(_task("A", ["B"]), _task("B", ["A"])))


def test_unknown_dependency_rejected():
    with pytest.raises(PlanError):
        TaskScheduler(_plan(_task("A", ["Z"])))


def test_duplicate_ids_rejected():
    with pytest.raises(PlanError):
        TaskScheduler(_plan(_task("A"), _task("A")))


def test_max_tasks_enforced():
    with pytest.raises(PlanError):
        TaskScheduler.validate(_plan(_task("A"), _task("B")), max_tasks=1)


def test_failure_blocks_dependents():
    sched = TaskScheduler(_plan(_task("A"), _task("B", ["A"]), _task("C", ["B"]), _task("D")))
    sched.mark_failed("A")
    assert sched.status == {"A": "failed", "B": "blocked", "C": "blocked", "D": "pending"}
    assert sched.next_ready().id == "D"