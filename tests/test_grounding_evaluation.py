from pathlib import Path

from evals.score_grounding import evaluate_grounding_fixture


def test_grounding_fixture_meets_acceptance_targets() -> None:
    result = evaluate_grounding_fixture(Path("evals/fixtures/grounding.json"))

    assert result["cases"] == 20
    assert result["grounding_precision"] >= 0.90
    assert result["unsupported_claim_rate"] < 0.02
    assert result["failures"] == []
