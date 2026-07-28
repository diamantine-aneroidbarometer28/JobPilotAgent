from app.services.parser import parse_job_description


def test_parser_extracts_categories_and_skills() -> None:
    result = parse_job_description(
        """
        We require strong Python and FastAPI experience.
        Preferred: experience with LangGraph and RAG.
        You will build testing and validation workflows.
        """
    )

    assert len(result.requirements) == 3
    assert result.requirements[0].skills == ["python", "fastapi"]
    assert result.requirements[1].category.value == "preferred"
    assert "langgraph" in result.requirements[1].skills
