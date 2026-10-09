from pydantic import ValidationError

from team.agents.base_agent import AgentError
from team.memory.decision_log import DecisionLog
from team.protocol.schemas import ArbitrationDecision, TaskSpec


class Arbitration:
    """Resolves deadlocks between agents by asking the Planner; falls back to escalation."""

    def __init__(self, planner, decisions: DecisionLog, logger=None) -> None:
        self.planner = planner
        self.decisions = decisions
        self.logger = logger

    def resolve(self, task: TaskSpec, history: list[str], rounds: int, stuck_on: str) -> ArbitrationDecision:
        try:
            decision = self.planner.arbitrate(task, history, rounds, stuck_on)
        except (AgentError, ValidationError) as e:
            decision = ArbitrationDecision(decision="escalate", rationale=f"Arbitration failed: {e}")
        self.decisions.add(
            "arbiter",
            f"{task.id}: {decision.decision}",
            decision.rationale,
            task_id=task.id,
        )
        if self.logger:
            self.logger.event("arbiter", "decision", {
                "task": task.id, "decision": decision.decision, "stuck_on": stuck_on,
            })
        return decision