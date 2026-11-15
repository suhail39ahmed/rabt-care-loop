"""Typed agent contracts (delegation request / result)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class DelegationRequest(BaseModel):
    case_id: str
    step: Literal[
        "data_quality",
        "triage",
        "ownership",
        "navigate",
        "comms",
        "reassurance",
        "econsult",
        "escalation",
        "closure",
    ]
    depth: int = Field(ge=0, le=2)
    allowed_tools: list[str] = []
    inputs: dict[str, Any] = {}


class DelegationResult(BaseModel):
    case_id: str
    step: str
    status: Literal["ok", "needs_human", "error"]
    proposed_transition: str | None = None
    outputs: dict[str, Any] = {}
    evidence_refs: list[str] = []


TOOL_SCOPES: dict[str, list[str]] = {
    "data_quality": ["read_case_bundle"],
    "triage": ["read_case_bundle"],
    "ownership": ["read_case_bundle", "update_task_state"],
    "navigate": ["read_case_bundle", "search_slots", "list_providers"],
    "comms": ["read_case_bundle", "write_communication"],
    "reassurance": ["read_case_bundle", "search_kb"],
    "econsult": ["read_case_bundle"],
    "escalation": ["update_task_state", "send_message"],
    "closure": ["read_case_bundle"],
}
