from langgraph.checkpoint.memory import InMemorySaver

from app.agents.workflow import build_workflow
from app.agents.writer import (
    EvidenceWriter,
    GeneratedClaim,
    GeneratedClaims,
    TokenUsage,
)


class WorkflowBackend:
    def generate(self, prompt: str, language: str) -> tuple[GeneratedClaims, TokenUsage]:
        return (
            GeneratedClaims(
                claims=[
                    GeneratedClaim(
                        text="Built Python FastAPI endpoints with validation.",
                        evidence_ids=["project#chunk-1"],
                    )
                ]
            ),
            TokenUsage(
                model="test-model",
                input_tokens=80,
                output_tokens=15,
                total_tokens=95,
                estimated_cost_usd=0.001,
            ),
        )


def test_workflow_exposes_writer_usage_before_approval() -> None:
    writer = EvidenceWriter(WorkflowBackend())
    graph = build_workflow(InMemorySaver(), writer=writer)
    paused = graph.invoke(
        {
            "request": {
                "job_description": "We require Python and FastAPI experience.",
                "documents": [
                    {
                        "source_id": "project",
                        "source_path": "README.md",
                        "content": "Built Python FastAPI endpoints with validation.",
                    }
                ],
                "language": "en",
            }
        },
        config={"configurable": {"thread_id": "writer-workflow-test"}},
    )

    assert paused["token_usage"]["total_tokens"] == 95
    assert paused["writer_attempts"] == 1
    assert paused["__interrupt__"][0].value["token_usage"]["model"] == "test-model"
