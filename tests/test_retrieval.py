from app.schemas import EvidenceDocument, JobRequirement
from app.schemas.models import RequirementCategory
from app.services.retrieval import build_evidence_map


def test_retrieval_preserves_source_path() -> None:
    requirement = JobRequirement(
        requirement_id="req-1",
        text="Build Python FastAPI services",
        category=RequirementCategory.MUST_HAVE,
        skills=["python", "fastapi"],
        priority=5,
    )
    document = EvidenceDocument(
        source_id="resume",
        source_path="resume.md",
        content="Built a Python FastAPI service with validated request schemas.",
    )

    mapping = build_evidence_map([requirement], [document])

    assert mapping[0].evidence[0].source_path == "resume.md"
    assert mapping[0].evidence[0].source_id.startswith("resume#chunk-")
