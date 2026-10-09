import json

import pytest

from team.memory.decision_log import DecisionLog
from team.memory.shared_store import SharedStore
from team.protocol.schemas import Plan, TaskSpec


def _plan():
    tasks = [
        TaskSpec(id="T1", title="a", description="d", acceptance_criteria=["x"]),
        TaskSpec(id="T2", title="b", description="d", acceptance_criteria=["y"], depends_on=["T1"]),
    ]
    return Plan(summary="plan", tasks=tasks)


def test_set_plan_initializes_status():
    store = SharedStore()
    store.set_plan(_plan())
    assert store.task_status == {"T1": "pending", "T2": "pending"}


def test_get_task():
    store = SharedStore()
    store.set_plan(_plan())
    assert store.get_task("T2").depends_on == ["T1"]
    with pytest.raises(KeyError):
        store.get_task("nope")


def test_status_and_artifacts():
    store = SharedStore()
    store.set_plan(_plan())
    store.set_status("T1", "done")
    store.add_artifact("T1", "last_diff", "diff text")
    data = store.to_dict()
    assert data["task_status"]["T1"] == "done"
    assert data["artifacts"]["T1"]["last_diff"] == "diff text"


def test_snapshot_written(tmp_path):
    store = SharedStore(tmp_path / "snaps")
    store.set_request("build it")
    store.set_plan(_plan())
    path = store.snapshot("after plan")
    assert path is not None and path.exists()
    assert json.loads(path.read_text())["request"] == "build it"


def test_snapshot_disabled_without_dir():
    assert SharedStore().snapshot("x") is None


def test_decision_log_render():
    log = DecisionLog()
    log.add("planner", "use dataclasses", "simple", task_id="T1")
    log.add("arbiter", "accept_work", task_id="T2")
    assert "use dataclasses" in log.render()
    assert "accept_work" not in log.render(task_id="T1")