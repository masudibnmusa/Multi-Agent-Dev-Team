import pytest
from pydantic import ValidationError

from team.protocol.message_bus import MessageBus
from team.protocol.messages import Message, MessageType
from team.protocol.schemas import ReviewResult, TaskAssignment, TaskSpec


def _assignment(task_id="T1") -> Message:
    task = TaskSpec(id=task_id, title="t", description="d", acceptance_criteria=["works"])
    return Message.create(MessageType.TASK_ASSIGNMENT, "orchestrator", "coder", TaskAssignment(task=task), task_id)


def test_fifo_delivery():
    bus = MessageBus()
    first, second = _assignment("T1"), _assignment("T2")
    bus.send(first)
    bus.send(second)
    assert bus.pending("coder") == 2
    assert bus.receive("coder").id == first.id
    assert bus.receive("coder").id == second.id
    assert bus.receive("coder") is None


def test_inboxes_are_isolated():
    bus = MessageBus()
    bus.send(_assignment())
    assert bus.receive("reviewer") is None
    assert bus.pending("coder") == 1


def test_invalid_payload_rejected():
    bus = MessageBus()
    bad = Message(type=MessageType.TASK_ASSIGNMENT, sender="x", recipient="coder", payload={"nope": 1})
    with pytest.raises(ValidationError):
        bus.send(bad)
    assert bus.pending("coder") == 0


def test_wrong_payload_type_rejected_at_creation():
    result = ReviewResult(task_id="T1", verdict="approve")
    with pytest.raises(TypeError):
        Message.create(MessageType.TASK_ASSIGNMENT, "a", "b", result)


def test_listener_and_history():
    bus = MessageBus()
    seen = []
    bus.subscribe(seen.append)
    msg = _assignment()
    bus.send(msg)
    assert seen == [msg]
    assert bus.history == [msg]


def test_roundtrip_parse():
    msg = _assignment("T7")
    assert msg.parse().task.id == "T7"