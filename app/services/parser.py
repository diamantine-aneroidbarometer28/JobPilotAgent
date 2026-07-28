import re

from app.schemas import JobAnalysis, JobRequirement
from app.schemas.models import RequirementCategory

SKILL_ALIASES: dict[str, set[str]] = {
    "python": {"python"},
    "fastapi": {"fastapi"},
    "sql": {"sql", "sqlite", "postgresql", "postgres", "mysql", "数据库"},
    "rag": {"rag", "retrieval augmented generation", "检索增强生成", "检索增强"},
    "llm": {"llm", "large language model", "大语言模型", "大模型"},
    "langgraph": {"langgraph"},
    "docker": {"docker", "container", "containers", "容器", "容器化"},
    "git": {"git", "github", "版本控制"},
    "testing": {"pytest", "testing", "unit test", "unit tests", "测试", "单元测试"},
    "pydantic": {"pydantic"},
    "machine-learning": {"machine learning", "机器学习"},
    "nlp": {"nlp", "natural language processing", "自然语言处理"},
    "api": {"api", "apis", "rest", "接口"},
    "aws": {"aws", "amazon web services"},
    "azure": {"azure"},
    "ci-cd": {"ci/cd", "continuous integration", "github actions", "持续集成"},
}

PREFERRED_MARKERS = ("preferred", "nice to have", "bonus", "优先", "加分")
RESPONSIBILITY_MARKERS = ("responsible", "you will", "responsibilities", "职责", "负责")
REQUIREMENT_MARKERS = ("require", "must", "need", "要求", "需要", "必备")


def normalize_skills(text: str) -> list[str]:
    lowered = text.casefold()
    return [
        canonical
        for canonical, aliases in SKILL_ALIASES.items()
        if any(_contains_alias(lowered, alias.casefold()) for alias in aliases)
    ]


def _contains_alias(text: str, alias: str) -> bool:
    if alias.isascii():
        return re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", text) is not None
    return alias in text


def _category(line: str) -> RequirementCategory:
    lowered = line.casefold()
    if any(marker in lowered for marker in PREFERRED_MARKERS):
        return RequirementCategory.PREFERRED
    if any(marker in lowered for marker in RESPONSIBILITY_MARKERS):
        return RequirementCategory.RESPONSIBILITY
    return RequirementCategory.MUST_HAVE


def parse_job_description(text: str) -> JobAnalysis:
    raw_lines = [line.strip(" \t-*•") for line in text.splitlines()]
    lines = [line for line in raw_lines if len(line) >= 8]
    if len(lines) <= 1:
        lines = [
            segment.strip()
            for segment in re.split(r"(?<=[。.!?；;])\s*", text)
            if len(segment.strip()) >= 8
        ]

    requirements = []
    for index, line in enumerate(lines[:30], start=1):
        skills = normalize_skills(line)
        if skills or any(
            marker in line.casefold()
            for marker in (*PREFERRED_MARKERS, *RESPONSIBILITY_MARKERS, *REQUIREMENT_MARKERS)
        ):
            category = _category(line)
            requirements.append(
                JobRequirement(
                    requirement_id=f"req-{index:03d}",
                    text=line,
                    category=category,
                    skills=skills,
                    priority=3 if category == RequirementCategory.PREFERRED else 5,
                )
            )

    if not requirements:
        requirements.append(
            JobRequirement(
                requirement_id="req-001",
                text=text.strip()[:500],
                category=RequirementCategory.MUST_HAVE,
                skills=normalize_skills(text),
                priority=5,
            )
        )
    return JobAnalysis(requirements=requirements)
