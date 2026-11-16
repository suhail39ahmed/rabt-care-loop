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
from app.state_machine import IllegalTransition, S, transition
from app.tools import ToolScopeError, assert_tool_allowed, invoke_tool

MAX_STEPS = 8


class Coordinator:
    def __init__(self, ledger: Ledger) -> None:
        self.ledger = ledger
        self._step_counts: dict[str, int] = {}

    def _begin_chain(self, case_id: str) -> None:
        """Reset delegation counter for one API request / tick chain."""
        self._step_counts[case_id] = 0

    def _bump_steps(self, case_id: str) -> None:
        n = self._step_counts.get(case_id, 0) + 1
        self._step_counts[case_id] = n
        if n > MAX_STEPS:
            raise RuntimeError(f"MAX_STEPS ({MAX_STEPS}) exceeded for {case_id}")

    async def _call_tool(self, db: aiosqlite.Connection, case_id: str, step: str, tool_name: str, fn, *args, **kwargs):
        try:
            return await invoke_tool(step, tool_name, fn, *args, **kwargs)
        except ToolScopeError as e:
            await self.ledger.append_timeline(
                db,
                case_id,
                kind="calculated",
                label="Tool refused (scope)",
                detail=str(e),
                actor="system:guardrails",
            )
            await hitl.enqueue(
                db,
                case_id,
                "tool_scope",
                f"Tool {tool_name} refused for {step}",
                urgency="URGENT",
                detail=str(e),
            )
            raise

    async def _delegate(self, db: aiosqlite.Connection, case_id: str, step: str, coro):
        """Run an agent step with MAX_STEPS + tool-scope bookkeeping."""
        try:
            self._bump_steps(case_id)
        except RuntimeError:
            if hasattr(coro, "close"):
                coro.close()
            await hitl.enqueue(
                db, case_id, "max_steps", "Delegation chain hit MAX_STEPS — human required"
            )
            await self.ledger.append_timeline(
                db,
                case_id,
                kind="calculated",
                label="MAX_STEPS exceeded",
                detail=str(MAX_STEPS),
                actor="system:coordinator",
            )
            return None
        # Agents may only use tools listed for this step
        assert_tool_allowed(step, (TOOL_SCOPES.get(step) or ["read_case_bundle"])[0])
        return await coro

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

        case_payload = {
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
        }
        if payload.get("case_id"):
            case_payload["case_id"] = payload["case_id"]
        # Keep a display name for board/patient chrome (synthetic only)
        if patient.get("name"):
            evidence0 = {"patient_display_name": str(patient["name"]).split("(")[0].strip()}
            case_payload["evidence"] = evidence0
        case = await self.ledger.create_case(db, case_payload)
        case_id = case["case_id"]
        self._begin_chain(case_id)

        # Data quality
        dq_raw = await self._delegate(
            db,
            case_id,
            "data_quality",
            dq_agent.run(
                {
                    "case_id": case_id,
                    "inputs": {"observation": obs, "siblings": payload.get("siblings") or []},
                }
            ),
        )
        if dq_raw is None:
            return await self.ledger.get_case(db, case_id)  # type: ignore[return-value]
        dq = DelegationResult.model_validate(dq_raw)
        if dq.proposed_transition == "DataQuery":
            await self._apply(db, case_id, S.NEW, S.DATA_QUERY, "agent:data_quality", "data query", dq.outputs)
            return await self.ledger.get_case(db, case_id)  # type: ignore[return-value]

        # Triage (New → Triaged)
        tri_raw = await self._delegate(
            db, case_id, "triage", triage_agent.run({"case_id": case_id, "inputs": {"observation": obs}})
        )
        if tri_raw is None:
            return await self.ledger.get_case(db, case_id)  # type: ignore[return-value]
        tri = DelegationResult.model_validate(tri_raw)
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

        # Ground-truth flag for KPI critical recall (seed / benchmark may also set it)
        ev = dict((await self.ledger.get_case(db, case_id) or {}).get("evidence") or {})
        if payload.get("ground_truth_critical") is True or tri.outputs.get("urgency") == "CRITICAL":
            ev["ground_truth_critical"] = True
            await self.ledger.update_case(db, case_id, evidence=ev)

        next_after = tri.outputs.get("next_after_triaged", "AwaitingOwner")
        if next_after == "Escalated" or tri.outputs.get("urgency") == "CRITICAL":
            return await self._enter_critical_ladder(db, case_id)

        # Ownership
        own_raw = await self._delegate(
            db,
            case_id,
            "ownership",
            ownership_agent.run(
                {
                    "case_id": case_id,
                    "inputs": {"patient": patient, "urgency": tri.outputs.get("urgency")},
                }
            ),
        )
        if own_raw is None:
            return await self.ledger.get_case(db, case_id)  # type: ignore[return-value]
        own = DelegationResult.model_validate(own_raw)
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
        self._begin_chain(case_id)
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
        self._begin_chain(case_id)
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

        display_name = (
            (case.get("evidence") or {}).get("patient_display_name")
            or "Patient"
        )
        urgency_raw = case.get("urgency") or "URGENT"
        next_by_lang = {
            "en": "confirm understanding and book a follow-up",
            "ar": "تأكيد الفهم وحجز متابعة",
        }
        urgency_by_lang = {
            "en": {"CRITICAL": "Critical", "URGENT": "Urgent", "ROUTINE": "Routine"}.get(
                urgency_raw, urgency_raw
            ),
            "ar": {"CRITICAL": "حرج", "URGENT": "عاجل", "ROUTINE": "روتيني"}.get(
                urgency_raw, urgency_raw
            ),
        }
        by_lang: dict[str, Any] = {}
        primary_lang = case.get("language") or "en"
        for lang in ("en", "ar"):
            res_raw = await self._delegate(
                db,
                case_id,
                "comms",
                comms_agent.run(
                    {
                        "case_id": case_id,
                        "inputs": {
                            "language": lang,
                            "result_class": result_class,
                            "urgency": urgency_by_lang[lang],
                            "consent_messaging": case.get("consent_messaging", True),
                            "first_name_token": display_name,
                            "next_step": next_by_lang[lang],
                            "low_literacy": False,
                        },
                    }
                ),
            )
            if res_raw is None:
                return await self.ledger.get_case(db, case_id)  # type: ignore[return-value]
            res = DelegationResult.model_validate(res_raw)
            by_lang[lang] = {
                "text": res.outputs.get("message"),
                "banner": res.outputs.get("banner"),
                "teachback": res.outputs.get("teachback"),
                "ai_generated": res.outputs.get("ai_generated", False),
                "language": lang,
            }
        primary = by_lang.get(primary_lang) or by_lang["en"]
        await self._apply(
            db, case_id, S.OWNED, S.NOTIFIED, "agent:comms", "patient notified", primary
        )
        messages = case["messages"]
        messages.append(
            {
                "channel": "app",
                "text": primary.get("text"),
                "language": primary_lang,
                "ai_generated": primary.get("ai_generated", False),
                "banner": primary.get("banner"),
                "teachback": primary.get("teachback"),
                "by_lang": by_lang,
            }
        )
        await self.ledger.update_case(db, case_id, messages=messages)
        return await self.ledger.get_case(db, case_id)  # type: ignore[return-value]

    async def mark_unreachable(self, db: aiosqlite.Connection, case_id: str) -> dict[str, Any]:
        """Patient did not engage after notification — escalate to human ladder."""
        self._begin_chain(case_id)
        case = await self.ledger.get_case(db, case_id)
        if not case:
            raise KeyError(case_id)
        await self._apply(
            db, case_id, S(case["state"]), S.UNREACHABLE, "agent:comms", "unreachable", {}
        )
        await hitl.enqueue(
            db, case_id, "unreachable", "Patient unreachable — escalate", urgency=case.get("urgency")
        )
        esc_raw = await self._delegate(
            db,
            case_id,
            "escalation",
            escalation_agent.run(
                {"case_id": case_id, "inputs": {"ladder_step": int(case.get("ladder_step") or 0)}}
            ),
        )
        if esc_raw is None:
            return await self.ledger.get_case(db, case_id)  # type: ignore[return-value]
        esc = DelegationResult.model_validate(esc_raw)
        await self._apply(
            db, case_id, S.UNREACHABLE, S.ESCALATED, "agent:escalation", "unreachable ladder", esc.outputs
        )
        step = (esc.outputs.get("ladder") or {}).get("step") or 1
        await self.ledger.update_case(db, case_id, ladder_step=step)
        return await self.ledger.get_case(db, case_id)  # type: ignore[return-value]

    async def submit_teachback(
        self, db: aiosqlite.Connection, case_id: str, answers: list[str]
    ) -> dict[str, Any]:
        self._begin_chain(case_id)
        case = await self.ledger.get_case(db, case_id)
        if not case:
            raise KeyError(case_id)
        questions = []
        candidates: list[list[dict[str, Any]]] = []
        for m in reversed(case["messages"]):
            if m.get("teachback"):
                candidates.append(m["teachback"])
            by_lang = m.get("by_lang") or {}
            for loc in by_lang.values():
                if loc.get("teachback"):
                    candidates.append(loc["teachback"])
            if candidates:
                break
        # Match any language variant; require one answer per question (#26, #32)
        correct = False
        questions = candidates[0] if candidates else []
        for candidate in candidates:
            if (
                candidate
                and len(answers) == len(candidate)
                and all(a == q.get("correct") for q, a in zip(candidate, answers))
            ):
                correct = True
                questions = candidate
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
        # May be nested under teachback chain — do not reset if already counting
        if self._step_counts.get(case_id, 0) == 0:
            self._begin_chain(case_id)
        case = await self.ledger.get_case(db, case_id)
        if not case:
            raise KeyError(case_id)
        plan = PLANS.get(case.get("plan_id") or "plan-b", PLANS["plan-b"])
        res_raw = await self._delegate(
            db,
            case_id,
            "navigate",
            navigator_agent.run(
                {
                    "case_id": case_id,
                    "inputs": {
                        "pathway": case.get("pathway") or "gp_review",
                        "plan_network": {plan["network_id"]},
                        "providers": PROVIDERS,
                        "language": case.get("language") or "en",
                    },
                }
            ),
        )
        if res_raw is None:
            return await self.ledger.get_case(db, case_id)  # type: ignore[return-value]
        res = DelegationResult.model_validate(res_raw)
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
        self, db: aiosqlite.Connection, case_id: str, note: str = "Encounter completed"
    ) -> dict[str, Any]:
        """Record attendance only — outcome document is a separate step (#3)."""
        case = await self.ledger.get_case(db, case_id)
        if not case:
            raise KeyError(case_id)
        await self._apply(db, case_id, S(case["state"]), S.ATTENDED, "human:clinic", "attended", {})
        evidence = dict(case.get("evidence") or {})
        evidence["attended_encounter"] = True
        evidence["attendance_note"] = note
        # Do not set outcome_document here — requires POST /outcome
        await self.ledger.update_case(db, case_id, evidence=evidence)
        await self._apply(
            db, case_id, S.ATTENDED, S.CLOSURE_PENDING, "system:flow", "closure pending", {}
        )
        return await self.try_close(db, case_id)

    async def record_outcome(
        self,
        db: aiosqlite.Connection,
        case_id: str,
        *,
        outcome_ref: str,
        outcome_note: str = "",
    ) -> dict[str, Any]:
        case = await self.ledger.get_case(db, case_id)
        if not case:
            raise KeyError(case_id)
        evidence = dict(case.get("evidence") or {})
        evidence["outcome_document"] = True
        evidence["outcome_ref"] = outcome_ref
        if outcome_note:
            evidence["outcome_note"] = outcome_note
        await self.ledger.update_case(db, case_id, evidence=evidence)
        await self.ledger.append_timeline(
            db,
            case_id,
            kind="fact",
            label="Outcome documented",
            detail=outcome_ref,
            actor="human:clinic",
        )
        # Move toward closure if still owned/attended after a prior block
        current = S(case["state"])
        if current is S.OWNED or current is S.ATTENDED:
            await self._apply(
                db, case_id, current, S.CLOSURE_PENDING, "human:clinic", "outcome ready", {}
            )
        return await self.try_close(db, case_id)

    async def try_close(
        self, db: aiosqlite.Connection, case_id: str, *, human: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        from app.state_machine import _OPEN_TO_CLOSURE_PENDING

        if self._step_counts.get(case_id, 0) == 0:
            self._begin_chain(case_id)
        case = await self.ledger.get_case(db, case_id)
        if not case:
            raise KeyError(case_id)
        current = S(case["state"])
        if current in {S.CLOSED, S.CLOSED_BY_HUMAN}:
            raise IllegalTransition(f"case already {current.value}")

        evidence = dict(case.get("evidence") or {})
        if human:
            # four_eyes_ok is ignored — two-person approval is the only override path
            cleaned = {k: v for k, v in human.items() if k != "four_eyes_ok"}
            evidence.update(cleaned)
        res_raw = await self._delegate(
            db,
            case_id,
            "closure",
            closure_agent.run({"case_id": case_id, "inputs": {"evidence": evidence}}),
        )
        if res_raw is None:
            return await self.ledger.get_case(db, case_id)  # type: ignore[return-value]
        res = DelegationResult.model_validate(res_raw)
        current = S(case["state"])
        if current is S.ATTENDED:
            await self._apply(db, case_id, current, S.CLOSURE_PENDING, "agent:closure", "verify", {})
            current = S.CLOSURE_PENDING
        if res.outputs.get("evidence", {}).get("closable"):
            mode = res.outputs["evidence"].get("mode")
            if mode == "human":
                if evidence.get("two_person_approved"):
                    # Ensure we are on a state that can close by human
                    if current is not S.CLOSURE_PENDING and current is not S.ON_HOLD_CONSENT:
                        if current in _OPEN_TO_CLOSURE_PENDING:
                            await self._apply(
                                db,
                                case_id,
                                current,
                                S.CLOSURE_PENDING,
                                "system:hitl",
                                "ready for two-person close",
                                {},
                            )
                            current = S.CLOSURE_PENDING
                    approvers = evidence.get("approvers") or []
                    actor = approvers[0] if approvers and str(approvers[0]).startswith("human:") else (
                        f"human:{approvers[0]}" if approvers else "human:board"
                    )
                    await self._apply(
                        db,
                        case_id,
                        current,
                        S.CLOSED_BY_HUMAN,
                        actor,
                        evidence.get("human_reason_code", "human_close"),
                        {"closure_ok": True, **evidence},
                    )
                else:
                    requester = evidence.get("human_signer") or evidence.get("requested_by") or "human:requester"
                    if not str(requester).startswith("human:"):
                        requester = f"human:{requester}"
                    # Move any open state into ClosurePending before creating the approval (#25)
                    if current is not S.CLOSURE_PENDING:
                        if current not in _OPEN_TO_CLOSURE_PENDING and current is not S.ON_HOLD_CONSENT:
                            raise IllegalTransition(f"{current.value} -> ClosurePending")
                        if current is S.ON_HOLD_CONSENT or current in _OPEN_TO_CLOSURE_PENDING:
                            await self._apply(
                                db,
                                case_id,
                                current,
                                S.CLOSURE_PENDING,
                                "system:hitl",
                                "awaiting two-person approval",
                                {},
                            )
                            current = S.CLOSURE_PENDING
                    token = await hitl.request_approval(
                        db,
                        case_id,
                        "exceptional_closure",
                        approvers_required=2,
                        evidence=evidence,
                        requested_by=requester,
                    )
                    evidence["pending_approval_token"] = token
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
            if current is S.CLOSURE_PENDING and not evidence.get("pending_approval_token"):
                # Bounce only when blocked for missing evidence, not while awaiting votes.
                # Keep Attended when encounter exists so board shows "outcome needed" (#53).
                bounce_to = (
                    S.ATTENDED if evidence.get("attended_encounter") else S.OWNED
                )
                await self._apply(
                    db,
                    case_id,
                    current,
                    bounce_to,
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

    async def complete_approved_closure(
        self,
        db: aiosqlite.Connection,
        case_id: str,
        *,
        approvers: list[str],
        evidence: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Resume closure after two distinct non-requester approvals."""
        case = await self.ledger.get_case(db, case_id)
        if not case:
            raise KeyError(case_id)
        merged = dict(case.get("evidence") or {})
        if evidence:
            merged.update(evidence)
        merged["two_person_approved"] = True
        merged["approvers"] = approvers
        merged["four_eyes_ok"] = True  # internal marker after real dual approval only
        if not merged.get("human_reason_code"):
            merged["human_reason_code"] = "exceptional_closure"
        if not merged.get("human_signer"):
            merged["human_signer"] = approvers[0] if approvers else "board"
        await self.ledger.update_case(db, case_id, evidence=merged)
        await self.ledger.append_timeline(
            db,
            case_id,
            kind="fact",
            label="Two-person closure approved",
            detail=", ".join(approvers),
            actor="system:hitl",
        )
        return await self.try_close(db, case_id, human={"two_person_approved": True, "approvers": approvers})

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
        self._begin_chain(case_id)
        case = await self.ledger.get_case(db, case_id)
        if not case:
            raise KeyError(case_id)
        res_raw = await self._delegate(
            db,
            case_id,
            "reassurance",
            reassurance_agent.run(
                {
                    "case_id": case_id,
                    "inputs": {"question": question, "language": case.get("language") or "en"},
                }
            ),
        )
        if res_raw is None:
            return await self.ledger.get_case(db, case_id)  # type: ignore[return-value]
        res = DelegationResult.model_validate(res_raw)
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
        self._begin_chain(case_id)
        case = await self.ledger.get_case(db, case_id)
        if not case:
            raise KeyError(case_id)
        res_raw = await self._delegate(
            db,
            case_id,
            "econsult",
            econsult_agent.run({"case_id": case_id, "inputs": {"case": case}}),
        )
        if res_raw is None:
            return await self.ledger.get_case(db, case_id)  # type: ignore[return-value]
        res = DelegationResult.model_validate(res_raw)
        await self.ledger.append_timeline(
            db, case_id, kind="ai", label="E-consult packet drafted", detail="Awaiting clinician review", actor="agent:econsult"
        )
        out = await self.ledger.get_case(db, case_id)
        out["econsult"] = res.outputs  # type: ignore[index]
        return out  # type: ignore[return-value]

    async def _enter_critical_ladder(self, db: aiosqlite.Connection, case_id: str) -> dict[str, Any]:
        from app import demo_clock

        esc_raw = await self._delegate(
            db,
            case_id,
            "escalation",
            escalation_agent.run({"case_id": case_id, "inputs": {"ladder_step": 0}}),
        )
        if esc_raw is None:
            return await self.ledger.get_case(db, case_id)  # type: ignore[return-value]
        esc = DelegationResult.model_validate(esc_raw)
        await self._apply(db, case_id, S.TRIAGED, S.ESCALATED, "agent:escalation", "critical ladder", esc.outputs)
        started = demo_clock.now()
        case = await self.ledger.get_case(db, case_id)
        evidence = dict((case or {}).get("evidence") or {})
        evidence.update(
            {
                "ladder_started_at": started,
                "ladder_stopped": False,
                "ground_truth_critical": True,
            }
        )
        await self.ledger.update_case(db, case_id, ladder_step=1, evidence=evidence)
        await hitl.enqueue(
            db,
            case_id,
            "critical",
            esc.outputs.get("ladder", {}).get("title", "Critical escalation"),
            urgency="CRITICAL",
            detail="No result values sent on SMS. LLM was not used.",
            ladder_step=1,
        )
        # SLA toward step 2 (15 min illustrative)
        step2 = next((x for x in escalation_agent.LADDER if x["step"] == 2), None)
        sla = int((step2 or {}).get("delay_min", 15)) * 60
        await hitl.request_approval(
            db,
            case_id,
            "critical",
            approvers_required=1,
            sla_seconds=max(sla, 1),
            evidence={"ladder_step": 1},
            requested_by="system:escalation",
        )
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

    async def advance_ladder(self, db: aiosqlite.Connection, case_id: str) -> dict[str, Any] | None:
        """Move one ladder step. Never closes the case."""
        self._begin_chain(case_id)
        case = await self.ledger.get_case(db, case_id)
        if not case:
            return None
        evidence = dict(case.get("evidence") or {})
        if evidence.get("ladder_stopped"):
            return case
        if case["state"] != S.ESCALATED.value:
            return case
        current_step = int(case.get("ladder_step") or 0)
        nxt = escalation_agent.next_step(current_step)
        if not nxt:
            await self.ledger.append_timeline(
                db,
                case_id,
                kind="calculated",
                label="Ladder exhausted — still open for human",
                detail="Timeouts never auto-close",
                actor="agent:escalation",
            )
            return case
        new_step = nxt["step"]
        await self.ledger.update_case(db, case_id, ladder_step=new_step)
        await hitl.enqueue(
            db,
            case_id,
            "critical",
            nxt["title"],
            urgency="CRITICAL",
            detail=f"Ladder step {new_step} ({nxt['role']})",
            ladder_step=new_step,
        )
        await self.ledger.append_timeline(
            db,
            case_id,
            kind="calculated",
            label=f"Escalation ladder → step {new_step}",
            detail=nxt["title"],
            actor="agent:escalation",
        )
        # Schedule next timeout if another step remains
        following = escalation_agent.next_step(new_step)
        if following:
            from app import demo_clock

            started = float(evidence.get("ladder_started_at") or demo_clock.now())
            due_in = max(int(following["delay_min"] * 60 - (demo_clock.now() - started)), 1)
            await hitl.request_approval(
                db,
                case_id,
                "critical",
                approvers_required=1,
                sla_seconds=due_in,
                evidence={"ladder_step": new_step},
                requested_by="system:escalation",
            )
        return await self.ledger.get_case(db, case_id)

    async def stop_ladder(self, db: aiosqlite.Connection, case_id: str) -> None:
        case = await self.ledger.get_case(db, case_id)
        if not case:
            return
        evidence = dict(case.get("evidence") or {})
        evidence["ladder_stopped"] = True
        await self.ledger.update_case(db, case_id, evidence=evidence)
        await db.execute(
            "UPDATE approvals SET status = 'cancelled' WHERE case_id = ? AND action = 'critical' AND status = 'pending'",
            (case_id,),
        )
        await db.commit()

    async def tick(self, db: aiosqlite.Connection) -> dict[str, Any]:
        """Sweep HITL timeouts and apply safe defaults (never auto-close)."""
        timed_out = await hitl.sweep_timeouts(db)
        advanced: list[str] = []
        kept_open: list[str] = []
        for item in timed_out:
            action = item["action"]
            case_id = item["case_id"]
            safe = item.get("safe_default")
            if action == "critical" or safe == "next_ladder_step":
                await self.advance_ladder(db, case_id)
                advanced.append(case_id)
            elif action == "exceptional_closure" or safe == "keep_open":
                # Timeouts never close a case
                kept_open.append(case_id)
                await self.ledger.append_timeline(
                    db,
                    case_id,
                    kind="calculated",
                    label="Approval timed out — kept open",
                    detail=item.get("token", ""),
                    actor="system:hitl",
                )
            else:
                kept_open.append(case_id)
        return {"timed_out": timed_out, "ladder_advanced": advanced, "kept_open": kept_open}

    async def human_handle_escalation(
        self, db: aiosqlite.Connection, case_id: str, actor: str
    ) -> dict[str, Any]:
        case = await self.ledger.get_case(db, case_id)
        if not case:
            raise KeyError(case_id)
        await self.stop_ladder(db, case_id)
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
