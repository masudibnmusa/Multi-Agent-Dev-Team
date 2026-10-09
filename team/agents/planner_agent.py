from __future__ import annotations

from pydantic import ValidationError

from team.agents.base_agent import AgentError, BaseAgent, format_task
from team.orchestrator.task_scheduler import PlanError, TaskScheduler
from team.protocol.schemas import ArbitrationDecision, Plan, TaskSpec


class PlannerAgent(BaseAgent):
    role = "planner"

    def plan(self, request: str) -> Plan:
        d = self.deps
        base_prompt = (
            f"# Feature request\n{request}\n\n## Repo map\n{d.repo.render()}\n\n"
            f"Plan at most {d.config.max_tasks} tasks. Inspect the repo with the read tools if needed, "
            f"then call submit_plan."
        )
        error = ""
        for _ in range(2):
            raw = self.run_loop("planner", base_prompt + error, "submit_plan")
            try:
                plan = Plan.model_validate(raw)
                TaskScheduler.validate(plan, d.config.max_tasks)
                return plan
            except (ValidationError, PlanError) as e:
                error = f"\n\nYour previous plan was invalid: {e}\nFix it and call submit_plan again."
        raise AgentError("Planner could not produce a valid plan")

    def arbitrate(self, task: TaskSpec, history: list[str], rounds: int, stuck_on: str) -> ArbitrationDecision:
        history_text = "\n".join(history[-12:]) or "(no history)"
        prompt = (
            f"# Deadlock on task {task.id}\n"
            f"The team is stuck on **{stuck_on}** after {rounds} round(s).\n\n"
            f"{format_task(task)}\n\n## History\n{history_text}\n\n"
            "Decide: accept_work, coder_must_fix, or escalate. Then call submit_arbitration."
        )
        raw = self.run_loop("planner_arbiter", prompt, "submit_arbitration")
        return ArbitrationDecision.model_validate(raw)