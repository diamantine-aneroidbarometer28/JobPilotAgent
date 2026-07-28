from types import SimpleNamespace
from typing import Any, cast

from openai import OpenAI

from app.agents.writer import (
    GeneratedClaim,
    GeneratedClaims,
    OpenAIResponsesBackend,
)


class FakeResponses:
    def parse(self, **kwargs: Any) -> SimpleNamespace:
        assert kwargs["model"] == "gpt-5.6-terra"
        assert kwargs["text_format"] is GeneratedClaims
        return SimpleNamespace(
            output_parsed=GeneratedClaims(
                claims=[
                    GeneratedClaim(
                        text="Built a validated API.",
                        evidence_ids=["project#chunk-1"],
                    )
                ]
            ),
            usage=SimpleNamespace(
                input_tokens=80,
                output_tokens=20,
                total_tokens=100,
            ),
        )


class FakeOpenAI:
    responses = FakeResponses()


def test_openai_backend_parses_usage_and_estimates_cost() -> None:
    backend = OpenAIResponsesBackend(
        model="gpt-5.6-terra",
        client=cast(OpenAI, FakeOpenAI()),
    )

    claims, usage = backend.generate("Evidence payload", "en")

    assert claims.claims[0].evidence_ids == ["project#chunk-1"]
    assert usage.total_tokens == 100
    assert usage.estimated_cost_usd == 0.0005
