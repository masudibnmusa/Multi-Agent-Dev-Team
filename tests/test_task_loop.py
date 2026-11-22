"""The per-task loop: round limits, arbitration outcomes and escalation, with fake agents."""
from types import SimpleNamespace

from team.config import Config
from team.orchestrator.orchestrator import Orchestrator
from team.orchestrator.workflow import TaskState, TaskWorkflow
from team.protocol.message_bus import MessageBus
from team.protocol.messages import Message, MessageType
from team.protocol.schemas import ArbitrationDecision, ReviewRequest, ReviewResult, TaskSpec
from team.protocol.schemas import TestReport as Report  # alias: stop pytest collecting it

TASK = TaskSpec(id="T1", title="t", description="d", acceptance_criteria=["ok"])


def make_orch(decisions, review="request_changes", tests_pass=True, rounds=2):
    orch = Orchestrator.__new__(Orchestrator)  # skip __init__: no git, LLM or sandbox
    orch.config = Config(max_revision_rounds=rounds)
    orch.run_id = "test"
    orch.stats = {"rounds": 0, "review_rejections": 0, "test_failures_after_review": 0}
    orch.bus = MessageBus()
    orch.logger = SimpleNamespace(event=lambda *a: None)
    orch._say = lambda text: None
    calls = {"coder": 0, "reviewer": 0, "tester": 0, "arbiter": []}

    def resolve(task, history, n, stuck_on):
        calls["arbiter"].append(stuck_on)
        return decisions.pop(0)

    def ask(msg):
        calls[msg.recipient] += 1
        if msg.recipient == "coder":
            payload = ReviewRequest(task_id="T1", round=1, summary="s")
            return Message.create(MessageType.REVIEW_REQUEST, "coder", "reviewer", payload, "T1")
        if msg.recipient == "reviewer":
            payload = ReviewResult(task_id="T1", verdict=review, summary="no")
            return Message.create(MessageType.REVIEW_RESULT, "reviewer", "orchestrator", payload, "T1")
        payload = Report(task_id="T1", passed=tests_pass, summary="1 failed" if not tests_pass else "ok")
        return Message.create(MessageType.TEST_REPORT, "tester", "orchestrator", payload, "T1")

    orch.arbitration = SimpleNamespace(resolve=resolve)
    orch._ask = ask
    return orch, calls


def test_coder_must_fix_grants_two_rounds_then_escalates():
    orch, calls = make_orch([
        ArbitrationDecision(decision="coder_must_fix", instruction="do X"),
        ArbitrationDecision(decision="coder_must_fix", instruction="do X again"),  # extra rounds used: escalate
    ])
    wf = TaskWorkflow("T1")
    assert orch._task_loop(TASK, wf) is False
    assert wf.rounds == 4  # limit 2 + 2 extra
    assert calls["arbiter"] == ["review", "review"]
    assert calls["tester"] == 0
    assert wf.state == TaskState.FAILED
    assert orch.bus.receive("human").type == MessageType.ESCALATION_NOTICE


def test_accept_work_skips_reviewer_and_runs_tests():
    orch, calls = make_orch([ArbitrationDecision(decision="accept_work")])
    wf = TaskWorkflow("T1")
    assert orch._task_loop(TASK, wf) is True
    assert calls["reviewer"] == 2 and calls["coder"] == 2 and calls["tester"] == 1
    assert wf.state == TaskState.DONE


def test_failing_tests_after_approval_counted_then_escalate():
    orch, calls = make_orch([ArbitrationDecision(decision="escalate")], review="approve", tests_pass=False)
    wf = TaskWorkflow("T1")
    assert orch._task_loop(TASK, wf) is False
    assert calls["arbiter"] == ["tests"]
    assert orch.stats["test_failures_after_review"] == 2
