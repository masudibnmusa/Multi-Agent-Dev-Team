from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from team.agents.base_agent import AgentDeps, AgentError
from team.agents.coder_agent import CoderAgent
from team.agents.planner_agent import PlannerAgent
from team.agents.reviewer_agent import ReviewerAgent
from team.agents.tester_agent import TesterAgent
from team.config import Config
from team.llm.llm_client import LLMClient
from team.memory.agent_scratchpads import Scratchpads
from team.memory.decision_log import DecisionLog
from team.memory.repo_context import RepoContext
from team.memory.shared_store import SharedStore
from team.observability.conversation_logger import ConversationLogger
from team.observability.cost_tracker import BudgetExceeded, CostTracker
from team.orchestrator.arbitration import Arbitration
from team.orchestrator.task_scheduler import TaskScheduler
from team.orchestrator.workflow import TaskWorkflow
from team.protocol.message_bus import MessageBus
from team.protocol.messages import Message, MessageType
from team.protocol.schemas import (
    EscalationNotice, ReviewComment, ReviewResult, TaskAssignment, TaskSpec, TestReport,
)
from team.sandbox.docker_manager import DockerManager
from team.tools import git_tools
from team.tools.registry import ToolContext, ToolRegistry
from team.tools.test_runner import run_tests


@dataclass
class RunSummary:
    run_id: str
    success: bool
    integration_passed: bool
    tasks_total: int
    tasks_done: int
    rounds_total: int
    review_rejections: int
    test_failures_after_review: int
    cost_usd: float
    tokens: int
    duration_s: float
    run_dir: str
    stopped_reason: str = ""


def _fmt_comment(c: ReviewComment) -> str:
    loc = f"{c.file}:{c.line}" if c.line else c.file
    return f"[{c.severity}] {loc} - {c.comment}".replace("  ", " ")


class Orchestrator:
    """Controls the workflow, routes typed messages, and enforces limits."""

    def __init__(self, config: Config | None = None, workspace: Path | None = None, run_id: str | None = None) -> None:
        self.config = config or Config()
        self.run_id = run_id or time.strftime("%Y%m%d-%H%M%S")
        self.workspace = Path(workspace or (self.config.workspace_dir / self.run_id)).resolve()
        self.run_dir = self.config.runs_dir / self.run_id

        self.logger = ConversationLogger(self.run_dir)
        self.cost = CostTracker(self.config.cost_budget_usd, self.config.token_budget)
        self.llm = LLMClient(self.config, self.cost, self.logger)
        self.sandbox = DockerManager(self.config.docker_image, self.config.sandbox_timeout, self.config.use_docker)
        self.sandbox.ensure_image()

        self.base_branch = git_tools.init_repo(self.workspace)
        self.ctx = ToolContext(self.workspace, self.sandbox, self.base_branch)
        self.registry = ToolRegistry(self.ctx)

        self.store = SharedStore(self.run_dir / "snapshots")
        self.decisions = DecisionLog()
        self.scratch = Scratchpads()
        self.repo = RepoContext(self.workspace)

        deps = AgentDeps(
            config=self.config, llm=self.llm, registry=self.registry, ctx=self.ctx,
            store=self.store, decisions=self.decisions, scratch=self.scratch,
            repo=self.repo, logger=self.logger,
        )
        self.planner = PlannerAgent(deps)
        self.agents = {
            "planner": self.planner,
            "coder": CoderAgent(deps),
            "reviewer": ReviewerAgent(deps),
            "tester": TesterAgent(deps),
        }

        self.bus = MessageBus()
        self.bus.subscribe(self.logger.log_message)
        self.arbitration = Arbitration(self.planner, self.decisions, self.logger)

        self.scheduler: TaskScheduler | None = None
        self.task_rounds: dict[str, int] = {}
        self.task_history: dict[str, list[str]] = {}
        self.stats = {"rounds": 0, "review_rejections": 0, "test_failures_after_review": 0}

    # ------------------------------------------------------------------ helpers
    def _say(self, text: str) -> None:
        print(f"[{self.run_id}] {text}", flush=True)

    def _ask(self, msg: Message) -> Message:
        """Deliver a message via the bus, let the recipient handle it, return its reply."""
        self.bus.send(msg)
        inbound = self.bus.receive(msg.recipient)
        assert inbound is not None
        return self.agents[msg.recipient].handle(inbound)

    def _collect(self, msg: Message):
        """Record a message addressed to the orchestrator and return its typed payload."""
        self.bus.send(msg)
        inbound = self.bus.receive("orchestrator")
        assert inbound is not None
        return inbound.parse()

    # ------------------------------------------------------------------ main flow
    def run(self, request: str) -> RunSummary:
        start = time.time()
        start_sha = git_tools.head_sha(self.workspace)
        stopped = ""
        plan = None
        self.store.set_request(request)

        try:
            self.repo.refresh()
            self._say("Planning...")
            plan = self.planner.plan(request)
            self.store.set_plan(plan)
            self.repo.conventions = plan.conventions
            self.decisions.add("planner", f"Plan: {plan.summary}")
            self.store.snapshot("plan")
            self.scheduler = TaskScheduler(plan)
            self._say(f"Plan ready: {len(plan.tasks)} task(s)")

            while (task := self.scheduler.next_ready()) is not None:
                self._run_task(task)
        except BudgetExceeded as e:
            stopped = f"budget exceeded: {e}"
        except AgentError as e:
            stopped = f"agent error: {e}"

        git_tools.checkout(self.workspace, self.base_branch)
        self._say("Running integration tests...")
        integration = run_tests(self.sandbox, self.workspace, "tests")

        tasks_total = len(plan.tasks) if plan else 0
        tasks_done = sum(1 for s in self.scheduler.status.values() if s == "done") if self.scheduler else 0
        success = bool(plan) and tasks_done == tasks_total and integration.passed and not stopped

        (self.run_dir / "final.patch").write_text(git_tools.final_patch(self.workspace, start_sha))
        self.cost.save(self.run_dir / "cost.json")
        self.store.snapshot("final")

        summary = RunSummary(
            run_id=self.run_id, success=success, integration_passed=integration.passed,
            tasks_total=tasks_total, tasks_done=tasks_done, rounds_total=self.stats["rounds"],
            review_rejections=self.stats["review_rejections"],
            test_failures_after_review=self.stats["test_failures_after_review"],
            cost_usd=self.cost.total_usd, tokens=self.cost.total_tokens,
            duration_s=time.time() - start, run_dir=str(self.run_dir), stopped_reason=stopped,
        )
        self._write_report(request, plan, integration, summary)
        return summary

    def _run_task(self, task: TaskSpec) -> None:
        ws, base = self.workspace, self.base_branch
        branch = f"task/{task.id.lower()}"
        git_tools.create_branch(ws, branch, base)
        wf = TaskWorkflow(task.id)
        self.store.set_status(task.id, "in_progress")
        self._say(f"Task {task.id}: {task.title}")

        ok = False
        try:
            ok = self._task_loop(task, wf)
        except AgentError as e:
            wf.log(f"agent error: {e}")
            wf.fail()
        finally:
            # Always leave the working tree on the base branch (also when BudgetExceeded propagates).
            msg = f"{task.id}: {task.title}" if ok else f"WIP {task.id} (unfinished)"
            git_tools.commit_all(ws, msg)
            git_tools.checkout(ws, base)

        self.task_rounds[task.id] = wf.rounds
        self.task_history[task.id] = wf.history
        if ok:
            git_tools.merge(ws, branch, base, f"Merge {task.id}: {task.title}")
            self.scheduler.mark(task.id, "done")
            self.store.set_status(task.id, "done")
            self.repo.refresh()
            self._say(f"Task {task.id} done in {wf.rounds} round(s)")
        else:
            self.scheduler.mark_failed(task.id)
            self.store.set_status(task.id, "failed")
            self._say(f"Task {task.id} FAILED")
        self.store.snapshot(task.id)

    def _task_loop(self, task: TaskSpec, wf: TaskWorkflow) -> bool:
        cfg = self.config
        limit = cfg.max_revision_rounds
        extra_used = False
        review_skipped = False
        skip_to_tests = False
        reviewed = False
        feedback: list[str] = []
        stuck_on = "review"

        while True:
            # ---- deadlock check: out of revision rounds
            if wf.rounds >= limit:
                decision = self.arbitration.resolve(task, wf.history, wf.rounds, stuck_on)
                wf.log(f"arbitration -> {decision.decision}: {decision.rationale}")
                if decision.decision == "accept_work" and stuck_on == "review":
                    review_skipped = skip_to_tests = True      # override the reviewer, go straight to tests
                elif decision.decision == "coder_must_fix" and not extra_used:
                    extra_used = True
                    limit += 2
                    feedback = [f"Arbiter instruction: {decision.instruction or decision.rationale}"]
                else:
                    self._escalate(task, wf, decision.rationale or f"stuck on {stuck_on}")
                    wf.fail()
                    return False

            # ---- code (+ review)
            if not skip_to_tests:
                wf.start_round()
                self.stats["rounds"] += 1
                reviewed = False
                self._say(f"  {task.id} round {wf.rounds}: coding")
                assignment = TaskAssignment(task=task, round=wf.rounds, feedback=feedback)
                review_request = self._ask(
                    Message.create(MessageType.TASK_ASSIGNMENT, "orchestrator", "coder", assignment, task.id)
                )

                if cfg.enable_reviewer and not review_skipped:
                    wf.begin_review()
                    self._say(f"  {task.id} round {wf.rounds}: reviewing")
                    result: ReviewResult = self._collect(self._ask(review_request))
                    if result.verdict == "request_changes":
                        feedback = [_fmt_comment(c) for c in result.comments] or [result.summary]
                        stuck_on = "review"
                        self.stats["review_rejections"] += 1
                        wf.log(f"reviewer requested changes: {result.summary}")
                        continue
                    reviewed = True
            skip_to_tests = False

            # ---- test
            wf.begin_testing()
            self._say(f"  {task.id} round {wf.rounds}: testing")
            tester_assignment = TaskAssignment(task=task, round=wf.rounds)
            report: TestReport = self._collect(self._ask(
                Message.create(MessageType.TASK_ASSIGNMENT, "orchestrator", "tester", tester_assignment, task.id)
            ))
            if report.passed:
                wf.complete()
                return True

            stuck_on = "tests"
            feedback = [f"Tests failed: {report.summary}\n{report.output_tail}"]
            wf.log(f"tests failed: {report.summary}")
            if reviewed:
                self.stats["test_failures_after_review"] += 1

    def _escalate(self, task: TaskSpec, wf: TaskWorkflow, reason: str) -> None:
        notice = EscalationNotice(
            task_id=task.id, reason=reason, rounds_used=wf.rounds, history=wf.history[-10:]
        )
        self.bus.send(Message.create(MessageType.ESCALATION_NOTICE, "orchestrator", "human", notice, task.id))
        self.logger.event("orchestrator", "escalation", {"task": task.id, "reason": reason})
        self._say(f"ESCALATION for {task.id}: {reason}")

    # ------------------------------------------------------------------ reporting
    def _write_report(self, request: str, plan, integration, summary: RunSummary) -> None:
        status = self.scheduler.status if self.scheduler else {}
        lines = [
            f"# Build report: {self.run_id}", "",
            "## Request", request, "",
            f"## Result: {'SUCCESS' if summary.success else 'INCOMPLETE'}", "",
        ]
        if summary.stopped_reason:
            lines += [f"Stopped early: {summary.stopped_reason}", ""]
        if plan:
            lines += ["## Plan", plan.summary, "", "## Tasks",
                      "| ID | Title | Status | Rounds |", "|----|-------|--------|--------|"]
            for t in plan.tasks:
                lines.append(f"| {t.id} | {t.title} | {status.get(t.id, 'n/a')} | {self.task_rounds.get(t.id, 0)} |")
            lines.append("")
        lines += [
            "## Integration tests",
            f"{'PASSED' if integration.passed else 'FAILED'}: {integration.summary}", "",
            "## Decisions", self.decisions.render(limit=50) or "(none)", "",
            "## Open issues",
        ]
        issues = False
        if plan:
            for t in plan.tasks:
                if status.get(t.id) in ("failed", "blocked", "pending"):
                    issues = True
                    last = self.task_history.get(t.id, ["no details"])[-1]
                    lines.append(f"- {t.id} ({status[t.id]}): {last}")
        if not integration.passed:
            issues = True
            lines.append(f"- Integration tests failing:\n\n{integration.output_tail[-1500:]}")
        if not issues:
            lines.append("None.")
        lines += ["", "## Cost", self.cost.summary(), ""]
        (self.run_dir / "report.md").write_text("\n".join(lines))