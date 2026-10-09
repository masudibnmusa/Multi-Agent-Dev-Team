from team.agents.base_agent import AgentError
from team.memory.decision_log import DecisionLog
from team.orchestrator.arbitration import Arbitration
from team.protocol.schemas import ArbitrationDecision, TaskSpec

TASK = TaskSpec(id="T1", title="t", description="d", acceptance_criteria=["ok"])


class FakePlanner:
    def __init__(self, decision=None, error=None):
        self.decision = decision
        self.error = error
        self.calls = []

    def arbitrate(self, task, history, rounds, stuck_on):
        self.calls.append((task.id, rounds, stuck_on))
        if self.error:
            raise self.error
        return self.decision


def test_returns_planner_decision_and_logs_it():
    planner = FakePlanner(ArbitrationDecision(decision="accept_work", rationale="meets criteria"))
    log = DecisionLog()
    result = Arbitration(planner, log).resolve(TASK, ["h1", "h2"], 3, "review")
    assert result.decision == "accept_work"
    assert planner.calls == [("T1", 3, "review")]
    assert "accept_work" in log.render(task_id="T1")


def test_coder_must_fix_passes_instruction_through():
    planner = FakePlanner(ArbitrationDecision(decision="coder_must_fix", instruction="handle empty input"))
    result = Arbitration(planner, DecisionLog()).resolve(TASK, [], 3, "tests")
    assert result.decision == "coder_must_fix"
    assert result.instruction == "handle empty input"


def test_planner_failure_escalates():
    planner = FakePlanner(error=AgentError("model returned nothing"))
    result = Arbitration(planner, DecisionLog()).resolve(TASK, [], 3, "review")
    assert result.decision == "escalate"
    assert "Arbitration failed" in result.rationale