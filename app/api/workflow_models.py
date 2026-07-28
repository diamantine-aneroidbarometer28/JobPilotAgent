from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas import TailoringRequest


class WorkflowStartRequest(TailoringRequest):
    thread_id: UUID | None = None


class WorkflowDecision(BaseModel):
    approved: bool


class WorkflowRunResponse(BaseModel):
    thread_id: UUID
    status: str
    claims: list[dict[str, Any]] = Field(default_factory=list)
    blocked_claims: list[dict[str, Any]] = Field(default_factory=list)
    token_usage: dict[str, Any] | None = None
    review: list[dict[str, Any]] = Field(default_factory=list)
    result: dict[str, Any] | None = None
