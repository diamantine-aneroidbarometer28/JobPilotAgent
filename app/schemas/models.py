from datetime import UTC, date, datetime
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class RequirementCategory(StrEnum):
    MUST_HAVE = "must_have"
    PREFERRED = "preferred"
    RESPONSIBILITY = "responsibility"


class SupportStatus(StrEnum):
    SUPPORTED = "supported"
    PARTIAL = "partial"
    UNSUPPORTED = "unsupported"


class EvidenceDocument(BaseModel):
    source_id: str = Field(min_length=1)
    source_path: str = Field(min_length=1)
    content: str = Field(min_length=1)


class Evidence(BaseModel):
    source_id: str
    source_path: str
    excerpt: str
    skills: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)


class Claim(BaseModel):
    text: str = Field(min_length=1)
    evidence_ids: list[str] = Field(default_factory=list)
    support_status: SupportStatus
    review_reason: str | None = None

    @model_validator(mode="after")
    def supported_claim_has_evidence(self) -> "Claim":
        if self.support_status == SupportStatus.SUPPORTED and not self.evidence_ids:
            raise ValueError("supported claims require at least one evidence ID")
        return self


class JobRequirement(BaseModel):
    requirement_id: str
    text: str
    category: RequirementCategory
    skills: list[str] = Field(default_factory=list)
    priority: int = Field(ge=1, le=5)


class JobAnalysis(BaseModel):
    title: str | None = None
    company: str | None = None
    requirements: list[JobRequirement]


class EvidenceMap(BaseModel):
    requirement: JobRequirement
    evidence: list[Evidence]


class TailoringRequest(BaseModel):
    job_description: str = Field(min_length=20)
    documents: list[EvidenceDocument] = Field(min_length=1)
    language: str = Field(default="en", pattern="^(en|zh)$")


class TailoringResult(BaseModel):
    analysis: JobAnalysis
    evidence_map: list[EvidenceMap]
    claims: list[Claim]
    blocked_claims: list[Claim]
    application_summary: str | None = None
    cover_letter: str | None = None


class ApplicationCreate(BaseModel):
    company: str = Field(min_length=1)
    role: str = Field(min_length=1)
    status: str = "draft"
    next_action: str | None = None
    due_date: date | None = None


class ApplicationRead(ApplicationCreate):
    id: int
    created_at: datetime


def utc_now() -> datetime:
    return datetime.now(UTC)
