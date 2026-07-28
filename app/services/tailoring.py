from app.schemas import Claim, TailoringRequest, TailoringResult
from app.schemas.models import SupportStatus
from app.services.parser import parse_job_description
from app.services.retrieval import build_evidence_map
from app.services.validator import validate_claim


def tailor(request: TailoringRequest) -> TailoringResult:
    analysis = parse_job_description(request.job_description)
    evidence_map = build_evidence_map(analysis.requirements, request.documents)
    claims: list[Claim] = []
    blocked: list[Claim] = []

    for mapping in evidence_map:
        if request.language == "zh":
            skill_text = "、".join(mapping.requirement.skills) or "相关能力"
            draft = f"运用{skill_text}完成与“{mapping.requirement.text}”相关的项目工作。"
        else:
            skill_text = ", ".join(mapping.requirement.skills) or "relevant skills"
            draft = (
                f'Applied {skill_text} in project work aligned with "{mapping.requirement.text}".'
            )
        claim = validate_claim(draft, mapping.evidence)
        (claims if claim.support_status == SupportStatus.SUPPORTED else blocked).append(claim)

    return TailoringResult(
        analysis=analysis,
        evidence_map=evidence_map,
        claims=claims,
        blocked_claims=blocked,
    )
