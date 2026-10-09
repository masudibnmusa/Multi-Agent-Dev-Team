from typing import Literal

from pydantic import BaseModel, Field


class TaskSpec(BaseModel):
    id: str
    title: str
    description: str
    files: list[str] = Field(default_factory=list)
    interfaces: list[str] = Field(default_factory=list)  # exact signatures / import paths
    acceptance_criteria: list[str]
    depends_on: list[str] = Field(default_factory=list)


class Plan(BaseModel):
    summary: str
    conventions: list[str] = Field(default_factory=list)
    tasks: list[TaskSpec]


class TaskAssignment(BaseModel):
    task: TaskSpec
    round: int = 1
    feedback: list[str] = Field(default_factory=list)


class ReviewRequest(BaseModel):
    task_id: str
    round: int
    summary: str
    files_changed: list[str] = Field(default_factory=list)
    diff: str = ""


class ReviewComment(BaseModel):
    file: str = ""
    line: int | None = None
    severity: Literal["blocker", "major", "minor", "nit"] = "major"
    comment: str


class ReviewResult(BaseModel):
    task_id: str
    verdict: Literal["approve", "request_changes"]
    summary: str = ""
    comments: list[ReviewComment] = Field(default_factory=list)


class TestReport(BaseModel):
    task_id: str
    passed: bool
    summary: str = ""
    tests_written: list[str] = Field(default_factory=list)
    output_tail: str = ""


class EscalationNotice(BaseModel):
    task_id: str
    reason: str
    rounds_used: int
    history: list[str] = Field(default_factory=list)


class ArbitrationDecision(BaseModel):
    decision: Literal["accept_work", "coder_must_fix", "escalate"]
    rationale: str = ""
    instruction: str = ""