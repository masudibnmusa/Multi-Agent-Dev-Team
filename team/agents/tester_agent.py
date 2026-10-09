from __future__ import annotations

from team.agents.base_agent import AgentError, BaseAgent
from team.protocol.messages import Message, MessageType
from team.protocol.schemas import TaskAssignment, TaskSpec, TestReport
from team.tools.test_runner import run_tests


class TesterAgent(BaseAgent):
    role = "tester"

    def __init__(self, deps) -> None:
        super().__init__(deps)
        self._written: dict[str, list[str]] = {}

    def handle(self, msg: Message) -> Message:
        d = self.deps
        assignment: TaskAssignment = msg.parse()
        task = assignment.task

        # Tests are written once per task (blind, from acceptance criteria), then re-run every round.
        if task.id not in self._written:
            self._written[task.id] = self._write_tests(task)
        files = self._written[task.id]

        prompt = (
            f"{self.context_block(task)}\n\n"
            f"Test files for this task: {', '.join(files)}\n\n"
            "Run the whole tests directory. Fix mistakes in the TESTS if there are any, but never weaken "
            "an assertion. Report real implementation failures honestly. Then call submit_test_report."
        )
        out = self.run_loop("tester_run", prompt, "submit_test_report")

        # Authoritative result: a fresh full run, not the LLM's claim.
        final = run_tests(d.ctx.sandbox, d.ctx.workspace, "tests")
        report = TestReport(
            task_id=task.id,
            passed=final.passed,
            summary=f"{final.summary}. {out.get('summary', '')}".strip(),
            tests_written=files,
            output_tail=final.output_tail,
        )
        return Message.create(MessageType.TEST_REPORT, self.name, "orchestrator", report, task.id)

    def _write_tests(self, task: TaskSpec) -> list[str]:
        d = self.deps
        blind = d.config.blind_tests
        profile = "tester_write" if blind else "tester_write_open"
        context = self.context_block(task, include_repo=not blind)
        prompt = (
            f"{context}\n\n"
            + ("You cannot see the implementation. " if blind else "")
            + f"Write pytest tests in tests/test_{task.id.lower()}.py from the acceptance criteria and "
            "interfaces, then call submit_tests_written."
        )
        out = self.run_loop(profile, prompt, "submit_tests_written")
        files = out.get("files") or []
        if not files:
            raise AgentError(f"Tester wrote no test files for {task.id}")
        return files