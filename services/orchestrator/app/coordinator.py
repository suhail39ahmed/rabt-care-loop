"""Case coordinator — supervisor that delegates to agents and applies transitions."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import aiosqlite

# Ensure services/ is on path for agents package
_SERVICES = Path(__file__).resolve().parents[2]
if str(_SERVICES) not in sys.path:
    sys.path.insert(0, str(_SERVICES))

from agents.closure import verifier as closure_agent
from agents.comms import agent as comms_agent
from agents.data_quality import checks as dq_agent
from agents.econsult import agent as econsult_agent
from agents.escalation import ladder as escalation_agent
from agents.navigator import scoring as navigator_agent
from agents.ownership import assign as ownership_agent
from agents.reassurance import agent as reassurance_agent
from agents.triage import engine as triage_agent

from app import hitl
from app.contracts import TOOL_SCOPES, DelegationResult
from app.ledger import Ledger
from app.reference_data import PLANS, PROVIDERS
from app.state_machine import S, IllegalTransition, transition

MAX_STEPS = 8


class Coordinator:
    def __init__(self, ledger: Ledger) -> None:
        self.ledger = ledger

    async def open_from_observation(
        self, db: aiosqlite.Connection, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Ingest a result, run DQ → triage → ownership/escalation."""
        key = payload.get("idempotency_key") or (
            f"Observation/{payload.get('observation', {}).get('id', 'x')}/_history/1"
        )
        if not await self.ledger.mark_event(db, key):
            # already processed — return existing case if any
            cases = await self.ledger.list_cases(db)
            for c in cases:
                if c.get("result_code") == ((payload.get("observation") or {}).get("code") or {}).get(
                    "coding", [{}]
                )[0].get("code") and c.get("patient_id") == payload.get("patient_id"):
                    return c
            return {"duplicate": True, "key": key}

        from agents.triage.normalize import normalize_observation

        obs = normalize_observation(payload["observation"])
        patient = payload.get("patient") or {}
        plan_id = payload.get("plan_id") or patient.get("plan_id") or "plan-b"
        plan = PLANS.get(plan_id, PLANS["plan-b"])

        bp_display = None
        if obs.get("systolic") is not None or obs.get("diastolic") is not None:
            bp_display = f"{obs.get('systolic', '—')}/{obs.get('diastolic', '—')}"

        case = await self.ledger.create_case(
            db,
            {
                "patient_id": payload["patient_id"],
                "language": patient.get("language", "en"),
                "result_code": ((obs.get("code") or {}).get("coding") or [{}])[0].get("code"),
                "result_display": ((obs.get("code") or {}).get("coding") or [{}])[0].get(
                    "display", obs.get("code", {}).get("text", "Result")
                ),
                "result_value": str(
                    bp_display
                    or (obs.get("valueQuantity") or {}).get("value")
                    or obs.get("valueString")
                    or (obs.get("valueCodeableConcept") or {}).get("text")
                    or ""
                ),
                "result_unit": (obs.get("valueQuantity") or {}).get("unit"),
                "plan_id": plan_id,
                "plan_name": plan["name"],
                "consent_messaging": payload.get("consent_messaging", True),
            },
        )
        case_id = case["case_id"]

        # Data quality
        dq = DelegationResult.model_validate(
            await dq_agent.run(
                {
                    "case_id": case_id,
                    "inputs": {"observation": obs, "siblings": payload.get("siblings") or []},
                }
            )
        )
        if dq.proposed_transition == "DataQuery":
            await self._apply(db, case_id, S.NEW, S.DATA_QUERY, "agent:data_quality", "data query", dq.outputs)
            return await self.ledger.get_case(db, case_id)  # type: ignore[return-value]

        # Triage (New → Triaged)
        tri = DelegationResult.model_validate(
            await triage_agent.run({"case_id": case_id, "inputs": {"observation": obs}})
        )
        if tri.status != "ok":
            await hitl.enqueue(
                db, case_id, "needs_human_triage", "Unknown result needs human triage", urgency="NEEDS_HUMAN"
            )
            await self.ledger.append_timeline(
                db, case_id, kind="calculated", label="Needs human triage", detail=str(tri.outputs), actor="agent:triage"
            )
            return await self.ledger.get_case(db, case_id)  # type: ignore[return-value]

        await self._apply(db, case_id, S.NEW, S.TRIAGED, "agent:triage", tri.outputs.get("rule_id", "triage"), tri.outputs)
        await self.ledger.update_case(
            db,
            case_id,
            urgency=tri.outputs.get("urgency"),
            pathway=tri.outputs.get("pathway"),
        )

        next_after = tri.outputs.get("next_after_triaged", "AwaitingOwner")
        if next_after == "Escalated" or tri.outputs.get("urgency") == "CRITICAL":
            esc = DelegationResult.model_validate(
                await escalation_agent.run({"case_id": case_id, "inputs": {"ladder_step": 0}})
            )
            await self._apply(db, case_id, S.TRIAGED, S.ESCALATED, "agent:escalation", "critical ladder", esc.outputs)
            await self.ledger.update_case(db, case_id, ladder_step=1)
            await hitl.enqueue(
                db,
                case_id,
                "critical",
                esc.outputs.get("ladder", {}).get("title", "Critical escalation"),
                urgency="CRITICAL",
                detail="No result values sent on SMS. LLM was not used.",
                ladder_step=1,
            )
            # safe message without values
            msg = esc.outputs.get("safe_message", {})
            case = await self.ledger.get_case(db, case_id)
            messages = case["messages"]  # type: ignore[index]
            messages.append(
                {
                    "channel": "sms",
                    "text": msg.get("text_en"),
                    "text_ar": msg.get("text_ar"),
                    "includes_values": False,
                    "ai_generated": False,
                }
            )
            await self.ledger.update_case(db, case_id, messages=messages)
            return await self.ledger.get_case(db, case_id)  # type: ignore[return-value]

        # Ownership
        own = DelegationResult.model_validate(
            await ownership_agent.run(
                {
                    "case_id": case_id,
                    "inputs": {"patient": patient, "urgency": tri.outputs.get("urgency")},
                }
            )
        )
        await self._apply(
            db, case_id, S.TRIAGED, S.AWAITING_OWNER, "agent:ownership", "assign owner", own.outputs
        )
        await self.ledger.update_case(
            db,
            case_id,
            owner_id=own.outputs.get("owner_id"),
            owner_name=own.outputs.get("owner_name"),
        )
        return await self.ledger.get_case(db, case_id)  # type: ignore[return-value]

    async def accept_ownership(
        self, db: aiosqlite.Connection, case_id: str, actor: str
    ) -> dict[str, Any]:
        case = await self.ledger.get_case(db, case_id)
        if not case:
            raise KeyError(case_id)
        await self._apply(
            db, case_id, S(case["state"]), S.OWNED, actor, "owner accepted", {"handshake": True}
        )
        return await self.ledger.get_case(db, case_id)  # type: ignore[return-value]

    async def decline_ownership(
        self, db: aiosqlite.Connection, case_id: str, actor: str, reason: str
    ) -> dict[str, Any]:
        case = await self.ledger.get_case(db, case_id)
        if not case:
            raise KeyError(case_id)
        await self._apply(
            db,
            case_id,
            S(case["state"]),
            S.AWAITING_OWNER,
            actor,
            f"declined: {reason}",
            {"decline_reason": reason},
        )
        await hitl.enqueue(db, case_id, "ownership_declined", f"Ownership declined: {reason}", urgency=case.get("urgency"))
        return await self.ledger.get_case(db, case_id)  # type: ignore[return-value]

    async def notify_patient(self, db: aiosqlite.Connection, case_id: str) -> dict[str, Any]:
        case = await self.ledger.get_case(db, case_id)
        if not case:
            raise KeyError(case_id)
        if case["state"] != S.OWNED.value:
            raise IllegalTransition(f"notify from {case['state']}")
        if not case.get("consent_messaging", True):
            await self._apply(
                db, case_id, S.OWNED, S.ON_HOLD_CONSENT, "agent:comms", "consent withdrawn", {}
            )
            return await self.ledger.get_case(db, case_id)  # type: ignore[return-value]

        result_class = "hba1c_urgent"
        code = case.get("result_code") or ""
        if code in {"85354-9", "8480-6"}:
            result_class = "bp_critical" if case.get("urgency") == "CRITICAL" else "bp_urgent"
        elif code in {"2335-8", "29771-3"}:
            result_class = "fit_positive"
        elif "BI-RADS" in (case.get("result_value") or ""):
            result_class = "mammo_urgent"

        res = DelegationResult.model_validate(
            await comms_agent.run(
                {
                    "case_id": case_id,
                    "inputs": {
                        "language": case.get("language") or "en",
                        "result_class": result_class,
                        "urgency": case.get("urgency"),
                        "consent_messaging": case.get("consent_messaging", True),
                        "first_name_token": "Patient",
                        "next_step": "confirm understanding and book a follow-up",
                        "low_literacy": False,
                    },
                }
            )
        )
        await self._apply(
            db, case_id, S.OWNED, S.NOTIFIED, "agent:comms", "patient notified", res.outputs
        )
        messages = case["messages"]
        messages.append(
            {
                "channel": "app",
                "text": res.outputs.get("message"),
                "language": res.outputs.get("language"),
                "ai_generated": res.outputs.get("ai_generated", False),
                "banner": res.outputs.get("banner"),
                "teachback": res.outputs.get("teachback"),
            }
        )
        await self.ledger.update_case(db, case_id, messages=messages)
        return await self.ledger.get_case(db, case_id)  # type: ignore[return-value]

    async def submit_teachback(
        self, db: aiosqlite.Connection, case_id: str, answers: list[str]
    ) -> dict[str, Any]:
        case = await self.ledger.get_case(db, case_id)
        if not case:
            raise KeyError(case_id)
        questions = []
        for m in reversed(case["messages"]):
            if m.get("teachback"):
                questions = m["teachback"]
                break
        correct = True
        for q, a in zip(questions, answers):
            if a != q.get("correct"):
                correct = False
                break
        if correct and questions:
            await self._apply(
                db, case_id, S.NOTIFIED, S.UNDERSTOOD, "patient:teachback", "teach-back passed", {"answers": answers}
            )
            # auto-navigate
            return await self.navigate(db, case_id)

        fails = int(case.get("teachback_fails") or 0) + 1
        await self.ledger.update_case(db, case_id, teachback_fails=fails)
        if fails >= 2:
            await self._apply(
                db,
                case_id,
                S.NOTIFIED,
                S.HUMAN_CALLBACK,
                "agent:comms",
                "teach-back failed twice",
                {"fails": fails},
            )
            await hitl.enqueue(
                db, case_id, "callback", "Teach-back failed — human callback", urgency=case.get("urgency")
            )
        else:
            await self.ledger.append_timeline(
                db,
                case_id,
                kind="ai",
                label="Teach-back failed — retry",
                detail=f"Attempt {fails}",
                actor="agent:comms",
            )
        return await self.ledger.get_case(db, case_id)  # type: ignore[return-value]

    async def navigate(self, db: aiosqlite.Connection, case_id: str) -> dict[str, Any]:
        case = await self.ledger.get_case(db, case_id)
        if not case:
            raise KeyError(case_id)
        plan = PLANS.get(case.get("plan_id") or "plan-b", PLANS["plan-b"])
        res = DelegationResult.model_validate(
            await navigator_agent.run(
                {
                    "case_id": case_id,
                    "inputs": {
                        "pathway": case.get("pathway") or "gp_review",
                        "plan_network": {plan["network_id"]},
                        "providers": PROVIDERS,
                        "language": case.get("language") or "en",
                    },
                }
            )
        )
        if res.status != "ok":
            await hitl.enqueue(db, case_id, "navigation", "No in-network options", urgency=case.get("urgency"))
            return await self.ledger.get_case(db, case_id)  # type: ignore[return-value]

        # From Understood → Referred
        current = S(case["state"])
        if current is S.UNDERSTOOD:
            await self._apply(db, case_id, current, S.REFERRED, "agent:navigator", "options ranked", res.outputs)
        elif current is S.REF_REJECTED:
            await self._apply(db, case_id, current, S.REFERRED, "agent:navigator", "re-routed", res.outputs)
        await self.ledger.update_case(db, case_id, options=res.outputs.get("options") or [])
        return await self.ledger.get_case(db, case_id)  # type: ignore[return-value]

    async def book(
        self, db: aiosqlite.Connection, case_id: str, option_id: str
    ) -> dict[str, Any]:
        case = await self.ledger.get_case(db, case_id)
        if not case:
            raise KeyError(case_id)
        opt = next((o for o in case.get("options") or [] if o["id"] == option_id), None)
        if not opt:
            raise ValueError("unknown option")
        if not opt.get("in_network") and not opt.get("self_pay_ok"):
            raise ValueError("out_of_network_blocked")
        await self._apply(
            db, case_id, S(case["state"]), S.BOOKED, "patient:book", f"booked {option_id}", {"option": opt}
        )
        evidence = case.get("evidence") or {}
        evidence["booked_option"] = option_id
        await self.ledger.update_case(db, case_id, evidence=evidence)
        return await self.ledger.get_case(db, case_id)  # type: ignore[return-value]

    async def mark_attended(
        self, db: aiosqlite.Connection, case_id: str, outcome_note: str = "Follow-up completed"
    ) -> dict[str, Any]:
        case = await self.ledger.get_case(db, case_id)
        if not case:
            raise KeyError(case_id)
        await self._apply(db, case_id, S(case["state"]), S.ATTENDED, "human:clinic", "attended", {})
        evidence = case.get("evidence") or {}
        evidence["attended_encounter"] = True
        evidence["outcome_note"] = outcome_note
        evidence["outcome_document"] = True
        await self.ledger.update_case(db, case_id, evidence=evidence)
        await self._apply(
            db, case_id, S.ATTENDED, S.CLOSURE_PENDING, "system:flow", "closure pending", {}
        )
        return await self.try_close(db, case_id)

    async def try_close(
        self, db: aiosqlite.Connection, case_id: str, *, human: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        case = await self.ledger.get_case(db, case_id)
        if not case:
            raise KeyError(case_id)
        evidence = dict(case.get("evidence") or {})
        if human:
            evidence.update(human)
        res = DelegationResult.model_validate(
            await closure_agent.run({"case_id": case_id, "inputs": {"evidence": evidence}})
        )
        current = S(case["state"])
        if current is S.ATTENDED:
            await self._apply(db, case_id, current, S.CLOSURE_PENDING, "agent:closure", "verify", {})
            current = S.CLOSURE_PENDING
        if res.outputs.get("evidence", {}).get("closable"):
            mode = res.outputs["evidence"].get("mode")
            if mode == "human":
                # require 4-eyes via HITL — if already approved in human dict
                if evidence.get("four_eyes_ok"):
                    actor = f"human:{evidence.get('human_signer', 'physician')}"
                    await self._apply(
                        db,
                        case_id,
                        current,
                        S.CLOSED_BY_HUMAN if mode == "human" and not evidence.get("attended_encounter") else S.CLOSED,
                        actor,
                        evidence.get("human_reason_code", "human_close"),
                        {"closure_ok": True, **evidence},
                    )
                else:
                    token = await hitl.request_approval(
                        db, case_id, "exceptional_closure", approvers_required=2, evidence=evidence
                    )
                    await self.ledger.append_timeline(
                        db,
                        case_id,
                        kind="fact",
                        label="4-eyes closure requested",
                        detail=token,
                        actor="system:hitl",
                    )
            else:
                await self._apply(
                    db,
                    case_id,
                    current,
                    S.CLOSED,
                    "agent:closure",
                    "evidence verified",
                    {"closure_ok": True, **evidence},
                )
        else:
            if current is S.CLOSURE_PENDING:
                await self._apply(
                    db,
                    case_id,
                    current,
                    S.OWNED,
                    "agent:closure",
                    "blocked — missing evidence",
                    res.outputs,
                )
            else:
                await self.ledger.append_timeline(
                    db,
                    case_id,
                    kind="calculated",
                    label="Closure blocked",
                    detail=str(res.outputs.get("evidence", {}).get("missing")),
                    actor="agent:closure",
                )
        await self.ledger.update_case(db, case_id, evidence=evidence)
        return await self.ledger.get_case(db, case_id)  # type: ignore[return-value]

    async def reject_referral(
        self, db: aiosqlite.Connection, case_id: str, reason: str
    ) -> dict[str, Any]:
        case = await self.ledger.get_case(db, case_id)
        if not case:
            raise KeyError(case_id)
        await self._apply(
            db, case_id, S(case["state"]), S.REF_REJECTED, "human:specialist", reason, {"reject_reason": reason}
        )
        return await self.navigate(db, case_id)

    async def withdraw_consent(self, db: aiosqlite.Connection, case_id: str) -> dict[str, Any]:
        case = await self.ledger.get_case(db, case_id)
        if not case:
            raise KeyError(case_id)
        await self.ledger.update_case(db, case_id, consent_messaging=0)
        if case["state"] == S.OWNED.value:
            await self._apply(
                db, case_id, S.OWNED, S.ON_HOLD_CONSENT, "patient:consent", "consent withdrawn", {}
            )
        else:
            await self.ledger.append_timeline(
                db, case_id, kind="fact", label="Consent withdrawn", detail="Automation paused", actor="patient:consent"
            )
        await hitl.enqueue(db, case_id, "consent", "Consent withdrawn — human-only path", urgency=case.get("urgency"))
        return await self.ledger.get_case(db, case_id)  # type: ignore[return-value]

    async def reassure(
        self, db: aiosqlite.Connection, case_id: str, question: str
    ) -> dict[str, Any]:
        case = await self.ledger.get_case(db, case_id)
        if not case:
            raise KeyError(case_id)
        res = DelegationResult.model_validate(
            await reassurance_agent.run(
                {
                    "case_id": case_id,
                    "inputs": {"question": question, "language": case.get("language") or "en"},
                }
            )
        )
        await self.ledger.append_timeline(
            db,
            case_id,
            kind="ai",
            label="Reassurance answer",
            detail=res.outputs.get("answer", "")[:200],
            actor="agent:reassurance",
        )
        if res.proposed_transition == "HumanCallback" and case["state"] == S.NOTIFIED.value:
            await self._apply(
                db, case_id, S.NOTIFIED, S.HUMAN_CALLBACK, "agent:reassurance", "red flag", res.outputs
            )
        out = await self.ledger.get_case(db, case_id)
        out["reassurance"] = res.outputs  # type: ignore[index]
        return out  # type: ignore[return-value]

    async def econsult_packet(self, db: aiosqlite.Connection, case_id: str) -> dict[str, Any]:
        case = await self.ledger.get_case(db, case_id)
        if not case:
            raise KeyError(case_id)
        res = DelegationResult.model_validate(
            await econsult_agent.run({"case_id": case_id, "inputs": {"case": case}})
        )
        await self.ledger.append_timeline(
            db, case_id, kind="ai", label="E-consult packet drafted", detail="Awaiting clinician review", actor="agent:econsult"
        )
        out = await self.ledger.get_case(db, case_id)
        out["econsult"] = res.outputs  # type: ignore[index]
        return out  # type: ignore[return-value]

    async def human_handle_escalation(
        self, db: aiosqlite.Connection, case_id: str, actor: str
    ) -> dict[str, Any]:
        case = await self.ledger.get_case(db, case_id)
        if not case:
            raise KeyError(case_id)
        await self._apply(db, case_id, S(case["state"]), S.OWNED, actor, "human handled escalation", {})
        return await self.ledger.get_case(db, case_id)  # type: ignore[return-value]

    async def resolve_data_query(self, db: aiosqlite.Connection, case_id: str) -> dict[str, Any]:
        case = await self.ledger.get_case(db, case_id)
        if not case:
            raise KeyError(case_id)
        await self._apply(db, case_id, S.DATA_QUERY, S.NEW, "human:coordinator", "data fixed", {})
        return await self.ledger.get_case(db, case_id)  # type: ignore[return-value]

    async def _apply(
        self,
        db: aiosqlite.Connection,
        case_id: str,
        current: S,
        target: S,
        actor: str,
        reason: str,
        evidence: dict[str, Any],
    ) -> dict[str, Any]:
        rec = transition(current, target, actor=actor, reason=reason, evidence=evidence)
        case = await self.ledger.get_case(db, case_id)
        prov = case["provenance"]  # type: ignore[index]
        prov.append(rec)
        if actor.startswith(("agent:comms", "agent:reassurance", "agent:econsult")):
            kind = "ai"
        elif actor.startswith("agent:"):
            kind = "calculated"
        else:
            kind = "fact"
        await self.ledger.update_case(db, case_id, state=target.value, provenance=prov)
        await self.ledger.append_timeline(
            db, case_id, kind=kind, label=f"{current.value} → {target.value}", detail=reason, actor=actor
        )
        return rec
