import re

from app.schemas import JobAnalysis, JobRequirement
from app.schemas.models import RequirementCategory

SKILL_ALIASES = {
    "python": {"python"},
    "fastapi": {"fastapi"},
    "sql": {"sql", "sqlite", "postgresql", "mysql"},
    "rag": {"rag", "retrieval augmented generation", "检索增强"},
    "llm": {"llm", "large language model", "大语言模型", "大模型"},
    "langgraph": {"langgraph"},
    "docker": {"docker", "container", "容器"},
    "git": {"git", "github"},
    "testing": {"pytest", "testing", "unit test", "测试"},
}

PREFERRED_MARKERS = ("preferred", "nice to have", "bonus", "优先", "加分")
RESPONSIBILITY_MARKERS = ("responsible", "you will", "职责", "负责")


def normalize_skills(text: str) -> list[str]:
    lowered = text.casefold()
    return [
        canonical
        for canonical, aliases in SKILL_ALIASES.items()
        if any(alias.casefold() in lowered for alias in aliases)
    ]


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
            for marker in (*PREFERRED_MARKERS, *RESPONSIBILITY_MARKERS, "require", "需要")
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
