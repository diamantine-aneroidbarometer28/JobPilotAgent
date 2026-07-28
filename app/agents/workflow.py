from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import interrupt

from app.agents.writer import EvidenceWriter
from app.schemas import (
    Claim,
    EvidenceMap,
    JobAnalysis,
    TailoringRequest,
    TailoringResult,
)
from app.schemas.models import SupportStatus
from app.services.parser import parse_job_description
from app.services.retrieval import build_evidence_map
from app.services.validator import validate_claim


class JobPilotState(TypedDict, total=False):
    request: dict[str, Any]
    analysis: dict[str, Any]
    evidence_map: list[dict[str, Any]]
    claims: list[dict[str, Any]]
    blocked_claims: list[dict[str, Any]]
    token_usage: dict[str, Any]
    writer_attempts: int
    approval_status: str
    result: dict[str, Any]
    application_summary: str
    cover_letter: str


def parse_node(state: JobPilotState) -> JobPilotState:
    request = TailoringRequest.model_validate(state["request"])
    analysis = parse_job_description(request.job_description)
    return {"analysis": analysis.model_dump(mode="json")}


def retrieve_node(state: JobPilotState) -> JobPilotState:
    request = TailoringRequest.model_validate(state["request"])
    analysis = JobAnalysis.model_validate(state["analysis"])
    mappings = build_evidence_map(analysis.requirements, request.documents)
    return {"evidence_map": [mapping.model_dump(mode="json") for mapping in mappings]}


def deterministic_draft_node(state: JobPilotState) -> JobPilotState:
    request = TailoringRequest.model_validate(state["request"])
    mappings = [EvidenceMap.model_validate(item) for item in state["evidence_map"]]
    claims: list[Claim] = []
    blocked: list[Claim] = []
    for mapping in mappings:
        if request.language == "zh":
            skill_text = "、".join(mapping.requirement.skills) or "相关能力"
            draft = f"运用{skill_text}完成与“{mapping.requirement.text}”相关的项目工作。"
        else:
            skill_text = ", ".join(mapping.requirement.skills) or "relevant skills"
            draft = (
                f'Applied {skill_text} in project work aligned with "{mapping.requirement.text}".'
            )
        claim = validate_claim(draft, mapping.evidence)
        target = claims if claim.support_status == SupportStatus.SUPPORTED else blocked
        target.append(claim)
    return {
        "claims": [claim.model_dump(mode="json") for claim in claims],
        "blocked_claims": [claim.model_dump(mode="json") for claim in blocked],
    }


def model_draft_node(state: JobPilotState, writer: EvidenceWriter) -> JobPilotState:
    request = TailoringRequest.model_validate(state["request"])
    mappings = [EvidenceMap.model_validate(item) for item in state["evidence_map"]]
    result = writer.write(mappings, request.language)
    return {
        "claims": [claim.model_dump(mode="json") for claim in result.claims],
        "blocked_claims": [claim.model_dump(mode="json") for claim in result.blocked_claims],
        "token_usage": result.usage.model_dump(mode="json"),
        "writer_attempts": result.attempts,
    }


def approval_node(state: JobPilotState) -> JobPilotState:
    decision = interrupt(
        {
            "type": "claim_review",
            "claims": state.get("claims", []),
            "blocked_claims": state.get("blocked_claims", []),
            "token_usage": state.get("token_usage"),
            "instruction": "Approve or reject the evidence-grounded claims.",
        }
    )
    approved = decision is True or (isinstance(decision, dict) and decision.get("approved") is True)
    return {"approval_status": "approved" if approved else "rejected"}


def finalize_node(state: JobPilotState) -> JobPilotState:
    approved = state.get("approval_status") == "approved"
    request = TailoringRequest.model_validate(state["request"])
    approved_claims = (
        [Claim.model_validate(item) for item in state.get("claims", [])] if approved else []
    )
    application_summary: str | None = None
    cover_letter: str | None = None
    if approved_claims:
        claim_text = " ".join(claim.text for claim in approved_claims)
        if request.language == "zh":
            application_summary = f"与岗位相关的证据支持经历：{claim_text}"
            cover_letter = (
                "您好：\n\n我希望申请该岗位。以下经历均来自可核验的项目材料："
                f"{claim_text}\n\n期待进一步交流这些经历与岗位需求的匹配方式。"
            )
        else:
            application_summary = (
                f"Evidence-supported experience relevant to this role: {claim_text}"
            )
            cover_letter = (
                "Dear Hiring Team,\n\nI am applying for this role with the following "
                f"evidence-supported experience: {claim_text}\n\nI would welcome the opportunity "
                "to discuss how this experience aligns with your requirements."
            )
    result = TailoringResult(
        analysis=JobAnalysis.model_validate(state["analysis"]),
        evidence_map=[EvidenceMap.model_validate(item) for item in state["evidence_map"]],
        claims=approved_claims,
        blocked_claims=[Claim.model_validate(item) for item in state.get("blocked_claims", [])],
        application_summary=application_summary,
        cover_letter=cover_letter,
    )
    return {
        "application_summary": application_summary or "",
        "cover_letter": cover_letter or "",
        "result": result.model_dump(mode="json"),
    }


def build_workflow(
    checkpointer: BaseCheckpointSaver[Any],
    *,
    writer: EvidenceWriter | None = None,
) -> CompiledStateGraph[JobPilotState, None, JobPilotState, JobPilotState]:
    builder = StateGraph(JobPilotState)
    builder.add_node("parse", parse_node)
    builder.add_node("retrieve", retrieve_node)
    if writer is None:
        builder.add_node("draft", deterministic_draft_node)
    else:
        builder.add_node("draft", lambda state: model_draft_node(state, writer))
    builder.add_node("approval", approval_node)
    builder.add_node("finalize", finalize_node)
    builder.add_edge(START, "parse")
    builder.add_edge("parse", "retrieve")
    builder.add_edge("retrieve", "draft")
    builder.add_edge("draft", "approval")
    builder.add_edge("approval", "finalize")
    builder.add_edge("finalize", END)
    return builder.compile(checkpointer=checkpointer)


@contextmanager
def sqlite_workflow(
    path: str | Path,
    *,
    writer: EvidenceWriter | None = None,
) -> Iterator[CompiledStateGraph[JobPilotState, None, JobPilotState, JobPilotState]]:
    with SqliteSaver.from_conn_string(str(path)) as checkpointer:
        yield build_workflow(checkpointer, writer=writer)
