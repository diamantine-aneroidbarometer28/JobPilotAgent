from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from app.agents.workflow import build_workflow


def _request() -> dict[str, object]:
    return {
        "job_description": "We require Python and FastAPI experience to build APIs.",
        "documents": [
            {
                "source_id": "project",
                "source_path": "README.md",
                "content": "Built Python FastAPI endpoints with Pydantic validation.",
            }
        ],
        "language": "en",
    }


def test_workflow_interrupts_and_resumes_after_approval() -> None:
    graph = build_workflow(InMemorySaver())
    config = {"configurable": {"thread_id": "approval-test"}}

    paused = graph.invoke({"request": _request()}, config=config)

    assert paused["__interrupt__"]
    completed = graph.invoke(Command(resume={"approved": True}), config=config)
    assert completed["approval_status"] == "approved"
    assert completed["result"]["claims"]
    assert "Evidence-supported experience" in completed["result"]["application_summary"]
    assert "Dear Hiring Team" in completed["result"]["cover_letter"]


def test_workflow_rejection_removes_exportable_claims() -> None:
    graph = build_workflow(InMemorySaver())
    config = {"configurable": {"thread_id": "rejection-test"}}
    graph.invoke({"request": _request()}, config=config)

    completed = graph.invoke(Command(resume={"approved": False}), config=config)

    assert completed["approval_status"] == "rejected"
    assert completed["result"]["claims"] == []
    assert completed["result"]["application_summary"] is None
    assert completed["result"]["cover_letter"] is None
