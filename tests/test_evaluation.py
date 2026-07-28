from pathlib import Path

from evals.score_retrieval import evaluate_fixture


def test_labeled_retrieval_fixture_meets_target() -> None:
    result = evaluate_fixture(Path("evals/fixtures/retrieval.json"))

    assert result["queries"] == 30
    assert result["recall_at_k"] >= 0.85
