from pathlib import Path

import pytest
from docx import Document

from app.exporters import export_tailored_docx
from app.schemas import Claim, Evidence, EvidenceMap, JobAnalysis, JobRequirement, TailoringResult
from app.schemas.models import RequirementCategory, SupportStatus


def _result(status: SupportStatus = SupportStatus.SUPPORTED) -> TailoringResult:
    requirement = JobRequirement(
        requirement_id="req-1",
        text="Build Python APIs",
        category=RequirementCategory.MUST_HAVE,
        skills=["python", "api"],
        priority=5,
    )
    evidence = Evidence(
        source_id="project#chunk-1",
        source_path="README.md",
        excerpt="Built Python APIs with validation.",
        confidence=1,
    )
    return TailoringResult(
        analysis=JobAnalysis(requirements=[requirement]),
        evidence_map=[EvidenceMap(requirement=requirement, evidence=[evidence])],
        claims=[
            Claim(
                text="Built Python APIs with validation.",
                evidence_ids=["project#chunk-1"],
                support_status=status,
            )
        ],
        blocked_claims=[],
        application_summary="Evidence-supported experience relevant to this role.",
        cover_letter="Dear Hiring Team,\n\nI built supported APIs.",
    )


def test_docx_export_contains_claim_and_audit_evidence(tmp_path: Path) -> None:
    output = tmp_path / "tailored-claims.docx"

    summary = export_tailored_docx(_result(), output)
    document = Document(output)
    text = "\n".join(paragraph.text for paragraph in document.paragraphs)

    assert summary.claim_count == 1
    assert summary.evidence_count == 1
    assert "Built Python APIs with validation." in text
    assert "project#chunk-1" in text
    assert "Source: README.md" in text
    assert "Application Summary" in text
    assert "Dear Hiring Team" in text


def test_docx_export_rejects_unapproved_claims(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="supported status"):
        export_tailored_docx(
            _result(SupportStatus.PARTIAL),
            tmp_path / "unsafe.docx",
        )
