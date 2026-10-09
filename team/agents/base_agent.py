from __future__ import annotations

from dataclasses import dataclass

from team.config import Config
from team.llm.llm_client import LLMClient
from team.memory.agent_scratchpads import Scratchpads
from team.memory.decision_log import DecisionLog
from team.memory.repo_context import RepoContext
from team.memory.shared_store import SharedStore
from team.observability.conversation_logger import ConversationLogger
from team.protocol.messages import Message
from team.protocol.schemas import TaskSpec
from team.tools.registry import ToolContext, ToolRegistry


class AgentError(RuntimeError):
    pass


@dataclass
class AgentDeps:
    config: Config
    llm: LLMClient
    registry: ToolRegistry
    ctx: ToolContext
    store: SharedStore
    decisions: DecisionLog
    scratch: Scratchpads
    repo: RepoContext
    logger: ConversationLogger | None = None


def format_task(task: TaskSpec) -> str:
    def bullets(items: list[str]) -> str:
        return "\n".join(f"- {i}" for i in items) if items else "- (none)"

    return (
        f"## Task {task.id}: {task.title}\n{task.description}\n\n"
        f"### Files\n{bullets(task.files)}\n\n"
        f"### Interfaces\n{bullets(task.interfaces)}\n\n"
        f"### Acceptance criteria\n{bullets(task.acceptance_criteria)}"
    )


class BaseAgent:
    """Shared plumbing: prompt loading, scoped context, and the tool loop."""

    role = "base"

    def __init__(self, deps: AgentDeps) -> None:
        self.deps = deps
        self.name = self.role

    @property
    def system_prompt(self) -> str:
        return (self.deps.config.prompts_dir / f"{self.role}.md").read_text()

    def context_block(self, task: TaskSpec | None = None, include_repo: bool = True) -> str:
        """A compact, role-scoped view of shared memory (not the whole store)."""
        d = self.deps
        parts: list[str] = []
        if d.store.plan:
            parts.append(f"## Plan summary\n{d.store.plan.summary}")
        if d.repo.conventions:
            parts.append("## Conventions\n" + "\n".join(f"- {c}" for c in d.repo.conventions))
        if include_repo:
            parts.append(f"## Repo map\n{d.repo.render()}")
        decisions = d.decisions.render(limit=10)
        if decisions:
            parts.append(f"## Decisions so far\n{decisions}")
        if task:
            parts.append(format_task(task))
        return "\n\n".join(parts)

    def run_loop(self, profile: str, user_message: str, terminal: str) -> dict:
        d = self.deps
        result = d.llm.run_loop(
            agent=self.name,
            model=d.config.models[self.role],
            system=self.system_prompt,
            user_message=user_message,
            tools=d.registry.schemas(profile),
            execute=lambda name, args: d.registry.execute(profile, name, args),
            terminal_tools={terminal},
            max_turns=d.config.max_agent_turns,
        )
        if result.terminal_input is None:
            raise AgentError(f"{self.name} ended without calling {terminal} ({result.turns} turns)")
        return result.terminal_input

    def handle(self, msg: Message) -> Message:
        raise NotImplementedError