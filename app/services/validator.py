import re

from app.schemas import Claim, Evidence
from app.schemas.models import SupportStatus

METRIC_PATTERN = re.compile(r"\b\d+(?:\.\d+)?%|\b\d+(?:\.\d+)?\s*(?:x|倍|分钟|hours?)\b", re.I)


def validate_claim(text: str, evidence: list[Evidence]) -> Claim:
    if not evidence:
        return Claim(
            text=text,
            support_status=SupportStatus.UNSUPPORTED,
            review_reason="No evidence was retrieved for this claim.",
        )

    evidence_text = " ".join(item.excerpt for item in evidence).casefold()
    claim_metrics = METRIC_PATTERN.findall(text)
    missing_metrics = [metric for metric in claim_metrics if metric.casefold() not in evidence_text]
    if missing_metrics:
        return Claim(
            text=text,
            evidence_ids=[item.source_id for item in evidence],
            support_status=SupportStatus.PARTIAL,
            review_reason=f"Metrics absent from evidence: {', '.join(missing_metrics)}",
        )

    return Claim(
        text=text,
        evidence_ids=[item.source_id for item in evidence],
        support_status=SupportStatus.SUPPORTED,
    )
