from types import SimpleNamespace

import pytest

from team.agents.base_agent import AgentError
from team.agents.reviewer_agent import ReviewerAgent
from team.protocol.messages import Message, MessageType
from team.protocol.schemas import ReviewRequest, TaskSpec

TASK = TaskSpec(id="T1", title="t", description="d", acceptance_criteria=["ok"])


@pytest.mark.parametrize("out", [
    {"summary": "no verdict"},
    {"verdict": "approve", "comments": [{"comment": "x", "severity": "critical"}]},
])
def test_malformed_review_raises_agent_error(monkeypatch, out):
    agent = ReviewerAgent(SimpleNamespace(store=SimpleNamespace(get_task=lambda _id: TASK)))
    monkeypatch.setattr(agent, "context_block", lambda task: "")
    monkeypatch.setattr(agent, "run_loop", lambda *a: out)
    msg = Message.create(MessageType.REVIEW_REQUEST, "coder", "reviewer",
                         ReviewRequest(task_id="T1", round=1, summary="s"), "T1")
    with pytest.raises(AgentError):
        agent.handle(msg)
