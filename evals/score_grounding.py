import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from app.schemas import Evidence
from app.schemas.models import SupportStatus
from app.services.validator import validate_claim


def evaluate_grounding_fixture(path: Path) -> dict[str, Any]:
    fixture = json.loads(path.read_text(encoding="utf-8"))
    confusion: Counter[tuple[str, str]] = Counter()
    failures: list[dict[str, str]] = []
    predicted_supported = 0
    correctly_supported = 0
    leaked_unsupported = 0

    for case in fixture["cases"]:
        evidence = [Evidence.model_validate(item) for item in case["evidence"]]
        prediction = validate_claim(case["claim"], evidence).support_status.value
        expected = case["expected_status"]
        confusion[(expected, prediction)] += 1
        if prediction == SupportStatus.SUPPORTED:
            predicted_supported += 1
            if expected == SupportStatus.SUPPORTED:
                correctly_supported += 1
            else:
                leaked_unsupported += 1
        if prediction != expected:
            failures.append(
                {"case_id": case["case_id"], "expected": expected, "predicted": prediction}
            )

    total = len(fixture["cases"])
    precision = correctly_supported / predicted_supported if predicted_supported else 0
    return {
        "cases": total,
        "accuracy": round((total - len(failures)) / total, 4) if total else 0,
        "grounding_precision": round(precision, 4),
        "unsupported_claim_rate": round(leaked_unsupported / total, 4) if total else 0,
        "confusion": {
            f"{expected}->{predicted}": count
            for (expected, predicted), count in sorted(confusion.items())
        },
        "failures": failures,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Score claim-level grounding labels.")
    parser.add_argument(
        "fixture",
        nargs="?",
        type=Path,
        default=Path("evals/fixtures/grounding.json"),
    )
    args = parser.parse_args()
    result = evaluate_grounding_fixture(args.fixture)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
