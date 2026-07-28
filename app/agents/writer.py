import json
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from openai import (
    APIConnectionError,
    APITimeoutError,
    InternalServerError,
    OpenAI,
    RateLimitError,
)
from pydantic import BaseModel, Field

from app.schemas import Claim, Evidence, EvidenceMap
from app.schemas.models import SupportStatus
from app.services.validator import validate_claim


class GeneratedClaim(BaseModel):
    text: str = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)


class GeneratedClaims(BaseModel):
    claims: list[GeneratedClaim]


class TokenUsage(BaseModel):
    model: str
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    estimated_cost_usd: float | None = Field(default=None, ge=0)


class WriterResult(BaseModel):
    claims: list[Claim]
    blocked_claims: list[Claim]
    usage: TokenUsage
    attempts: int = Field(ge=1)


@dataclass(frozen=True)
class ModelPricing:
    input_usd_per_million: float
    output_usd_per_million: float


MODEL_PRICING = {
    "gpt-5.6-sol": ModelPricing(5.0, 30.0),
    "gpt-5.6": ModelPricing(5.0, 30.0),
    "gpt-5.6-terra": ModelPricing(2.5, 15.0),
    "gpt-5.6-luna": ModelPricing(1.0, 6.0),
}


class RetryableWriterError(RuntimeError):
    """A transient model-provider error that may succeed on retry."""


class StructuredWriterBackend(Protocol):
    def generate(self, prompt: str, language: str) -> tuple[GeneratedClaims, TokenUsage]: ...


class OpenAIResponsesBackend:
    def __init__(
        self,
        *,
        model: str | None = None,
        api_key: str | None = None,
        client: OpenAI | None = None,
    ) -> None:
        self.model = model or os.getenv("JOBPILOT_MODEL") or "gpt-5.6-terra"
        self.client = client or OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))

    def generate(self, prompt: str, language: str) -> tuple[GeneratedClaims, TokenUsage]:
        system_prompt = (
            "Write concise resume claims using only the supplied evidence. "
            "Every claim must cite one or more exact evidence IDs. "
            "Never invent metrics, employers, responsibilities, tools, or outcomes. "
            f"Write in {'Chinese' if language == 'zh' else 'English'}."
        )
        try:
            response = self.client.responses.parse(
                model=self.model,
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                text_format=GeneratedClaims,
            )
        except (
            APIConnectionError,
            APITimeoutError,
            InternalServerError,
            RateLimitError,
        ) as error:
            raise RetryableWriterError(str(error)) from error

        parsed = response.output_parsed
        if parsed is None:
            raise RuntimeError("The model response did not contain parsed claims.")
        usage = response.usage
        if usage is None:
            raise RuntimeError("The model response did not include token usage.")
        input_tokens = usage.input_tokens
        output_tokens = usage.output_tokens
        pricing = MODEL_PRICING.get(self.model)
        estimated_cost = None
        if pricing is not None:
            estimated_cost = round(
                (
                    input_tokens * pricing.input_usd_per_million
                    + output_tokens * pricing.output_usd_per_million
                )
                / 1_000_000,
                8,
            )
        return parsed, TokenUsage(
            model=self.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=usage.total_tokens,
            estimated_cost_usd=estimated_cost,
        )


def build_evidence_prompt(mappings: list[EvidenceMap]) -> str:
    payload = [
        {
            "requirement": mapping.requirement.model_dump(mode="json"),
            "evidence": [
                {
                    "evidence_id": evidence.source_id,
                    "source_path": evidence.source_path,
                    "excerpt": evidence.excerpt,
                }
                for evidence in mapping.evidence
            ],
        }
        for mapping in mappings
    ]
    return (
        "Create resume claims for the following requirement-to-evidence mappings. "
        "Omit requirements that lack sufficient evidence.\n"
        + json.dumps(payload, ensure_ascii=False)
    )


class EvidenceWriter:
    def __init__(
        self,
        backend: StructuredWriterBackend,
        *,
        max_attempts: int = 3,
        initial_backoff_seconds: float = 0.25,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        self.backend = backend
        self.max_attempts = max_attempts
        self.initial_backoff_seconds = initial_backoff_seconds
        self.sleeper = sleeper

    def write(self, mappings: list[EvidenceMap], language: str = "en") -> WriterResult:
        prompt = build_evidence_prompt(mappings)
        generated: GeneratedClaims | None = None
        usage: TokenUsage | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                generated, usage = self.backend.generate(prompt, language)
                break
            except RetryableWriterError:
                if attempt == self.max_attempts:
                    raise
                self.sleeper(self.initial_backoff_seconds * (2 ** (attempt - 1)))

        if generated is None or usage is None:
            raise RuntimeError("Writer completed without a result.")

        evidence_by_id: dict[str, Evidence] = {
            evidence.source_id: evidence for mapping in mappings for evidence in mapping.evidence
        }
        claims: list[Claim] = []
        blocked: list[Claim] = []
        for item in generated.claims:
            unknown_ids = [
                evidence_id
                for evidence_id in item.evidence_ids
                if evidence_id not in evidence_by_id
            ]
            if unknown_ids:
                blocked.append(
                    Claim(
                        text=item.text,
                        evidence_ids=[
                            evidence_id
                            for evidence_id in item.evidence_ids
                            if evidence_id in evidence_by_id
                        ],
                        support_status=SupportStatus.UNSUPPORTED,
                        review_reason=f"Unknown evidence IDs: {', '.join(unknown_ids)}",
                    )
                )
                continue
            claim = validate_claim(
                item.text,
                [evidence_by_id[evidence_id] for evidence_id in item.evidence_ids],
            )
            (claims if claim.support_status == SupportStatus.SUPPORTED else blocked).append(claim)
        return WriterResult(
            claims=claims,
            blocked_claims=blocked,
            usage=usage,
            attempts=attempt,
        )
