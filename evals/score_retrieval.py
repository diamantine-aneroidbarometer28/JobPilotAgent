import argparse
import json
from pathlib import Path
from typing import Any

from app.schemas import EvidenceDocument, JobRequirement
from app.schemas.models import RequirementCategory
from app.services.parser import normalize_skills
from app.services.retrieval import build_evidence_map


def evaluate_fixture(path: Path, k: int = 5) -> dict[str, Any]:
    fixture = json.loads(path.read_text(encoding="utf-8"))
    documents = [EvidenceDocument.model_validate(item) for item in fixture["documents"]]
    hits = 0
    failures: list[dict[str, str]] = []
    for index, query in enumerate(fixture["queries"], start=1):
        requirement = JobRequirement(
            requirement_id=f"eval-{index:03d}",
            text=query["text"],
            category=RequirementCategory.MUST_HAVE,
            skills=normalize_skills(query["text"]),
            priority=5,
        )
        mapping = build_evidence_map([requirement], documents, limit=k)[0]
        retrieved_ids = {item.source_id.split("#", 1)[0] for item in mapping.evidence}
        if query["expected_source_id"] in retrieved_ids:
            hits += 1
        else:
            failures.append(
                {
                    "query": query["text"],
                    "expected": query["expected_source_id"],
                }
            )
    total = len(fixture["queries"])
    return {
        "k": k,
        "queries": total,
        "hits": hits,
        "recall_at_k": round(hits / total, 4) if total else 0,
        "failures": failures,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Score the labeled retrieval fixture.")
    parser.add_argument(
        "fixture",
        nargs="?",
        type=Path,
        default=Path("evals/fixtures/retrieval.json"),
    )
    parser.add_argument("-k", type=int, default=5)
    args = parser.parse_args()
    print(json.dumps(evaluate_fixture(args.fixture, args.k), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
