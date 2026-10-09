from __future__ import annotations

from team.agents.base_agent import BaseAgent
from team.protocol.messages import Message, MessageType
from team.protocol.schemas import ReviewRequest, TaskAssignment
from team.tools import git_tools


class CoderAgent(BaseAgent):
    role = "coder"

    def handle(self, msg: Message) -> Message:
        d = self.deps
        assignment: TaskAssignment = msg.parse()
        task = assignment.task

        parts = [self.context_block(task)]
        notes = d.scratch.render(self.role, task.id)
        if notes:
            parts.append(f"## Your notes from earlier rounds\n{notes}")
        if assignment.feedback:
            parts.append(
                f"## Feedback to address (round {assignment.round})\n"
                + "\n".join(f"- {f}" for f in assignment.feedback)
            )
        parts.append("Implement this task, then call submit_implementation.")

        out = self.run_loop("coder", "\n\n".join(parts), "submit_implementation")

        ws, base = d.ctx.workspace, d.ctx.base_branch
        diff = git_tools.diff_against(ws, base)
        files = git_tools.changed_files(ws, base)
        summary = out.get("summary", "")
        d.scratch.add(self.role, f"round {assignment.round}: {summary}", task.id)
        d.store.add_artifact(task.id, "last_diff", diff)

        request = ReviewRequest(
            task_id=task.id, round=assignment.round, summary=summary,
            files_changed=files, diff=diff[: d.config.max_diff_chars],
        )
        return Message.create(MessageType.REVIEW_REQUEST, self.name, "reviewer", request, task.id)