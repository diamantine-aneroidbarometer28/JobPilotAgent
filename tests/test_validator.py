from app.schemas import Evidence
from app.schemas.models import SupportStatus
from app.services.validator import validate_claim


def test_validator_blocks_invented_metric() -> None:
    evidence = Evidence(
        source_id="project#chunk-1",
        source_path="README.md",
        excerpt="Built a job parsing pipeline.",
        skills=["python"],
        confidence=1,
    )

    claim = validate_claim("Reduced processing time by 50%.", [evidence])

    assert claim.support_status == SupportStatus.PARTIAL
    assert "50%" in (claim.review_reason or "")


def test_supported_claim_requires_evidence() -> None:
    claim = validate_claim(
        "Built a job parsing pipeline.",
        [
            Evidence(
                source_id="project#chunk-1",
                source_path="README.md",
                excerpt="Built a job parsing pipeline.",
                confidence=1,
            )
        ],
    )
    assert claim.support_status == SupportStatus.SUPPORTED
    assert claim.evidence_ids
