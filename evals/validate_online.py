import argparse
import json
import os
from pathlib import Path

from app.agents.writer import EvidenceWriter, OpenAIResponsesBackend
from app.schemas import TailoringRequest
from app.services.parser import parse_job_description
from app.services.retrieval import build_evidence_map


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run one explicit, privacy-scrubbed online writer validation."
    )
    parser.add_argument(
        "--fixture",
        type=Path,
        default=Path("evals/fixtures/workflow_benchmark.json"),
    )
    parser.add_argument(
        "--confirm-spend",
        action="store_true",
        help="Required acknowledgement that this command makes a billable API call.",
    )
    args = parser.parse_args()
    if not args.confirm_spend:
        parser.error("--confirm-spend is required")
    if not os.getenv("OPENAI_API_KEY"):
        parser.error("OPENAI_API_KEY is not configured")

    fixture = json.loads(args.fixture.read_text(encoding="utf-8"))
    request = TailoringRequest.model_validate(fixture["cases"][0])
    analysis = parse_job_description(request.job_description)
    mappings = build_evidence_map(analysis.requirements, request.documents)
    result = EvidenceWriter(OpenAIResponsesBackend(), max_attempts=1).write(
        mappings,
        request.language,
    )
    print(
        json.dumps(
            {
                "model": result.usage.model,
                "attempts": result.attempts,
                "claims": len(result.claims),
                "blocked_claims": len(result.blocked_claims),
                "input_tokens": result.usage.input_tokens,
                "output_tokens": result.usage.output_tokens,
                "estimated_cost_usd": result.usage.estimated_cost_usd,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
