import re

from app.schemas import Claim, Evidence
from app.schemas.models import SupportStatus
from app.services.retrieval import tokenize

METRIC_PATTERN = re.compile(
    r"\b\d[\d,]*(?:\.\d+)?\s*"
    r"(?:%|x|倍|minutes?|分钟|hours?|小时|million|billion|thousand|k|m)",
    re.I,
)

STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "built",
    "created",
    "developed",
    "for",
    "implemented",
    "in",
    "led",
    "of",
    "on",
    "the",
    "to",
    "using",
    "with",
}


def _meaningful_tokens(text: str) -> set[str]:
    return {token for token in tokenize(text) if token not in STOPWORDS and len(token) > 1}


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

    claim_tokens = _meaningful_tokens(text)
    evidence_tokens = _meaningful_tokens(evidence_text)
    if claim_tokens and not claim_tokens.intersection(evidence_tokens):
        return Claim(
            text=text,
            evidence_ids=[item.source_id for item in evidence],
            support_status=SupportStatus.UNSUPPORTED,
            review_reason="Claim has no meaningful lexical overlap with its evidence.",
        )

    return Claim(
        text=text,
        evidence_ids=[item.source_id for item in evidence],
        support_status=SupportStatus.SUPPORTED,
    )
