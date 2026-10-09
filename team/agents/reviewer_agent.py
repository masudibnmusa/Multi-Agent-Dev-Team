from __future__ import annotations

from team.agents.base_agent import BaseAgent
from team.protocol.messages import Message, MessageType
from team.protocol.schemas import ReviewComment, ReviewRequest, ReviewResult


class ReviewerAgent(BaseAgent):
    role = "reviewer"

    def handle(self, msg: Message) -> Message:
        d = self.deps
        request: ReviewRequest = msg.parse()
        task = d.store.get_task(request.task_id)

        prompt = (
            f"{self.context_block(task)}\n\n"
            f"## Submission (round {request.round})\n"
            f"Coder's summary: {request.summary}\n"
            f"Files changed: {', '.join(request.files_changed) or '(none)'}\n\n"
            f"<diff>\n{request.diff}\n</diff>\n\n"
            "Review this against the acceptance criteria and interfaces, then call submit_review."
        )
        out = self.run_loop("reviewer", prompt, "submit_review")

        result = ReviewResult(
            task_id=request.task_id,
            verdict=out["verdict"],
            summary=out.get("summary", ""),
            comments=[ReviewComment(**c) for c in out.get("comments", [])],
        )
        # A reviewer can't approve while listing a blocker.
        if result.verdict == "approve" and any(c.severity == "blocker" for c in result.comments):
            result.verdict = "request_changes"
        return Message.create(MessageType.REVIEW_RESULT, self.name, "orchestrator", result, request.task_id)