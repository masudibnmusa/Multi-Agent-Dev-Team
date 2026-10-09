import time
import uuid
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from team.protocol import schemas as s


class MessageType(str, Enum):
    TASK_ASSIGNMENT = "task_assignment"
    REVIEW_REQUEST = "review_request"
    REVIEW_RESULT = "review_result"
    TEST_REPORT = "test_report"
    ESCALATION_NOTICE = "escalation_notice"


PAYLOAD_MODELS: dict[MessageType, type[BaseModel]] = {
    MessageType.TASK_ASSIGNMENT: s.TaskAssignment,
    MessageType.REVIEW_REQUEST: s.ReviewRequest,
    MessageType.REVIEW_RESULT: s.ReviewResult,
    MessageType.TEST_REPORT: s.TestReport,
    MessageType.ESCALATION_NOTICE: s.EscalationNotice,
}


class Message(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    type: MessageType
    sender: str
    recipient: str
    task_id: str | None = None
    payload: dict[str, Any]
    timestamp: float = Field(default_factory=time.time)

    @classmethod
    def create(
        cls,
        type: MessageType,
        sender: str,
        recipient: str,
        payload: BaseModel,
        task_id: str | None = None,
    ) -> "Message":
        expected = PAYLOAD_MODELS[type]
        if not isinstance(payload, expected):
            raise TypeError(f"{type.value} needs a {expected.__name__}, got {type(payload).__name__}")
        return cls(
            type=type,
            sender=sender,
            recipient=recipient,
            task_id=task_id,
            payload=payload.model_dump(),
        )

    def parse(self) -> BaseModel:
        """Validate and return the typed payload (raises pydantic.ValidationError if malformed)."""
        return PAYLOAD_MODELS[self.type].model_validate(self.payload)