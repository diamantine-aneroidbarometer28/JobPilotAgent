import argparse
import json
import statistics
import time
from pathlib import Path
from typing import Any

from app.schemas import TailoringRequest
from app.services.tailoring import tailor


def benchmark_fixture(path: Path, *, runs: int = 3) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = payload["cases"]
    timings: list[float] = []
    claim_counts: list[int] = []
    for _ in range(runs):
        for case in cases:
            request = TailoringRequest.model_validate(case)
            started = time.perf_counter()
            result = tailor(request)
            timings.append((time.perf_counter() - started) * 1000)
            claim_counts.append(len(result.claims))
    return {
        "mode": "deterministic",
        "fixture": str(path),
        "cases": len(cases),
        "runs": runs,
        "samples": len(timings),
        "latency_ms": {
            "mean": round(statistics.mean(timings), 3),
            "median": round(statistics.median(timings), 3),
            "max": round(max(timings), 3),
        },
        "mean_exportable_claims": round(statistics.mean(claim_counts), 2),
        "estimated_cost_usd": 0.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark privacy-scrubbed workflow fixtures.")
    parser.add_argument(
        "fixture",
        nargs="?",
        type=Path,
        default=Path("evals/fixtures/workflow_benchmark.json"),
    )
    parser.add_argument("--runs", type=int, default=3)
    args = parser.parse_args()
    if args.runs < 1:
        parser.error("--runs must be positive")
    print(json.dumps(benchmark_fixture(args.fixture, runs=args.runs), indent=2))


if __name__ == "__main__":
    main()
