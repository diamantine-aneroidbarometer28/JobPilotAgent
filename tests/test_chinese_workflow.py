from langgraph.checkpoint.memory import InMemorySaver

from app.agents.workflow import build_workflow


def test_deterministic_workflow_preserves_chinese_text() -> None:
    graph = build_workflow(InMemorySaver())
    config = {"configurable": {"thread_id": "chinese-test"}}
    paused = graph.invoke(
        {
            "request": {
                "job_description": "岗位要求：需要使用 Python 和 FastAPI 开发接口。",
                "documents": [
                    {
                        "source_id": "project",
                        "source_path": "项目说明.md",
                        "content": "使用 Python 和 FastAPI 开发了带数据校验的接口。",
                    }
                ],
                "language": "zh",
            }
        },
        config=config,
    )

    claim_text = paused["claims"][0]["text"]
    assert "运用" in claim_text
    assert "相关的项目工作" in claim_text
