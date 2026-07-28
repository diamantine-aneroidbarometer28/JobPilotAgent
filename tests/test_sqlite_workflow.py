from pathlib import Path

from langgraph.types import Command

from app.agents.workflow import sqlite_workflow


def test_sqlite_checkpoint_resumes_in_a_new_graph_process(tmp_path: Path) -> None:
    checkpoint_path = tmp_path / "checkpoints.db"
    config = {"configurable": {"thread_id": "durable-test"}}
    request = {
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

    with sqlite_workflow(checkpoint_path) as graph:
        paused = graph.invoke({"request": request}, config=config)
        assert paused["__interrupt__"]

    with sqlite_workflow(checkpoint_path) as restored_graph:
        completed = restored_graph.invoke(
            Command(resume={"approved": True}),
            config=config,
        )

    assert completed["approval_status"] == "approved"
    assert completed["result"]["claims"]
