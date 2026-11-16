"""FHIR R4 evidence pack builder (#60)."""

from __future__ import annotations

from typing import Any
from uuid import uuid4


def build_evidence_pack(case: dict[str, Any]) -> dict[str, Any]:
    cid = case["case_id"]
    entries: list[dict[str, Any]] = []
    obs = case.get("observation") or (case.get("evidence") or {}).get("observation") or {}
    obs_id = obs.get("id") or f"obs-{cid}"
    entries.append(
        {
            "fullUrl": f"urn:uuid:{obs_id}",
            "resource": {
                "resourceType": "Observation",
                "id": obs_id,
                "status": "final",
                "code": obs.get("code") or {"text": case.get("result_display") or "screening"},
                "valueQuantity": {
                    "value": case.get("result_value"),
                    "unit": case.get("result_unit"),
                }
                if case.get("result_value") is not None
                else None,
            },
        }
    )
    task_id = f"task-{cid}"
    entries.append(
        {
            "fullUrl": f"urn:uuid:{task_id}",
            "resource": {
                "resourceType": "Task",
                "id": task_id,
                "status": case.get("state"),
                "intent": "order",
                "for": {"reference": f"Patient/{case.get('patient_id')}"},
            },
        }
    )
    for i, p in enumerate(case.get("provenance") or []):
        pid = f"prov-{cid}-{i}"
        agents = [{"who": {"display": p.get("actor")}}]
        entries.append(
            {
                "fullUrl": f"urn:uuid:{pid}",
                "resource": {
                    "resourceType": "Provenance",
                    "id": pid,
                    "recorded": str(p.get("at")),
                    "activity": {"text": f"{p.get('from')} → {p.get('to')}"},
                    "agent": agents,
                    "reason": [{"text": p.get("reason")}],
                    "entity": [
                        {
                            "role": "source",
                            "what": {
                                "display": f"rule {((p.get('evidence') or {}).get('rule_id')) or 'n/a'}"
                            },
                        }
                    ],
                },
            }
        )
    if case.get("state") == "ClosedByHuman":
        approvers = (case.get("evidence") or {}).get("approvers") or []
        pid = f"prov-close-{cid}"
        entries.append(
            {
                "fullUrl": f"urn:uuid:{pid}",
                "resource": {
                    "resourceType": "Provenance",
                    "id": pid,
                    "activity": {"text": "ClosedByHuman"},
                    "agent": [{"who": {"display": a}} for a in approvers],
                },
            }
        )
    for i, m in enumerate(case.get("messages") or []):
        mid = f"comm-{cid}-{i}"
        entries.append(
            {
                "fullUrl": f"urn:uuid:{mid}",
                "resource": {
                    "resourceType": "Communication",
                    "id": mid,
                    "status": "completed",
                    "payload": [
                        {"contentString": m.get("text") or m.get("text_en") or ""},
                        {"contentString": m.get("text_ar") or ""},
                    ],
                    "extension": [
                        {
                            "url": "https://rabt.demo/ai_generated",
                            "valueBoolean": bool(m.get("ai_generated")),
                        }
                    ],
                },
            }
        )
    return {
        "resourceType": "Bundle",
        "type": "collection",
        "id": str(uuid4()),
        "entry": entries,
    }
