from app.agents.writer import (
    EvidenceWriter,
    GeneratedClaim,
    GeneratedClaims,
    RetryableWriterError,
    TokenUsage,
)
from app.schemas import Evidence, EvidenceMap, JobRequirement
from app.schemas.models import RequirementCategory, SupportStatus


def _mapping() -> EvidenceMap:
    return EvidenceMap(
        requirement=JobRequirement(
            requirement_id="req-1",
            text="Build Python APIs",
            category=RequirementCategory.MUST_HAVE,
            skills=["python", "api"],
            priority=5,
        ),
        evidence=[
            Evidence(
                source_id="project#chunk-1",
                source_path="README.md",
                excerpt="Built Python APIs with request validation.",
                skills=["python", "api"],
                confidence=1,
            )
        ],
    )


class SuccessfulBackend:
    def generate(self, prompt: str, language: str) -> tuple[GeneratedClaims, TokenUsage]:
        assert "project#chunk-1" in prompt
        assert language == "en"
        return (
            GeneratedClaims(
                claims=[
                    GeneratedClaim(
                        text="Built Python APIs with request validation.",
                        evidence_ids=["project#chunk-1"],
                    )
                ]
            ),
            TokenUsage(
                model="test-model",
                input_tokens=100,
                output_tokens=20,
                total_tokens=120,
            ),
        )


class FlakyBackend(SuccessfulBackend):
    def __init__(self) -> None:
        self.calls = 0

    def generate(self, prompt: str, language: str) -> tuple[GeneratedClaims, TokenUsage]:
        self.calls += 1
        if self.calls < 3:
            raise RetryableWriterError("temporary failure")
        return super().generate(prompt, language)


class HallucinatingBackend(SuccessfulBackend):
    def generate(self, prompt: str, language: str) -> tuple[GeneratedClaims, TokenUsage]:
        claims, usage = super().generate(prompt, language)
        claims.claims[0].evidence_ids = ["invented#chunk-9"]
        return claims, usage


def test_writer_returns_locally_validated_claims() -> None:
    result = EvidenceWriter(SuccessfulBackend()).write([_mapping()])

    assert result.claims[0].support_status == SupportStatus.SUPPORTED
    assert result.usage.total_tokens == 120
    assert result.attempts == 1


def test_writer_retries_transient_failures_with_exponential_backoff() -> None:
    backend = FlakyBackend()
    sleeps: list[float] = []

    result = EvidenceWriter(backend, sleeper=sleeps.append).write([_mapping()])

    assert result.attempts == 3
    assert sleeps == [0.25, 0.5]


def test_writer_blocks_unknown_evidence_ids() -> None:
    result = EvidenceWriter(HallucinatingBackend()).write([_mapping()])

    assert result.claims == []
    assert result.blocked_claims[0].support_status == SupportStatus.UNSUPPORTED
    assert "invented#chunk-9" in (result.blocked_claims[0].review_reason or "")
