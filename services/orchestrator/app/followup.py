"""Follow-up tracker: time-in-step targets, computed follow-up flags and the ownership guarantee.

Flags are computed from the ledger on every read and re-checked by the background tick:

- overdue: the case has been in its current step longer than the step's target (SLA).
- missed_visit: the patient did not attend (NoShow, a booked visit whose time has passed with no attendance,
  or a rebooking still pending after a no-show).
- result_delayed: an expected result has not arrived in time (attended but no outcome document, or a data
  query on the incoming result still unresolved).
- unowned: no named, accountable owner.

The tracker never moves a case between states and never closes one: it raises queue items and assigns owners.
Times use the demo clock so "Advance +15m" on the board moves them too. Targets are illustrative and can be
overridden with RABT_FOLLOWUP_SLA_MINUTES (JSON, e.g. {"Owned": 120}) and the RABT_*_MINUTES variables below.
"""

from __future__ import annotations

import json
import os
from typing import Any

from app import demo_clock

CLOSED_STATES = {"Closed", "ClosedByHuman"}

# Demo-friendly targets, in minutes, for how long a case may sit in each step. None = no target (the step is
# timed another way, e.g. Booked runs to the appointment time, or waits on the patient's own choice).
DEFAULT_SLA_MINUTES: dict[str, float | None] = {
    "New": 10,
    "DataQuery": 30,
    "Triaged": 10,
    "Escalated": 15,
    "AwaitingOwner": 30,
    "Owned": 60,
    "PatientNotified": 120,
    "Unreachable": 30,
    "HumanCallback": 60,
    "Understood": 120,
    "Referred": 240,
    "ReferralRejected": 60,
    "Booked": None,
    "NoShow": 30,
    "Attended": 60,
    "ClosurePending": 60,
    "Transferred": 60,
    "OnHoldConsent": None,
}

FLAGS = ("overdue", "missed_visit", "result_delayed", "unowned")

FLAG_TITLES = {
    "overdue": "Follow-up: case overdue in its current step",
    "missed_visit": "Follow-up: missed visit, help the patient rebook",
    "result_delayed": "Follow-up: result delayed, chase the outcome",
    "unowned": "Follow-up: no accountable owner",
}

# Who is assigned when the guarantee has to step in.
ON_CALL = {"owner_id": "Practitioner/supervisor-oncall", "owner_name": "On-call supervisor"}
COORDINATOR_ON_DUTY = {"owner_id": "Practitioner/coordinator-sara", "owner_name": "Coordinator Sara"}

# Demo personas who can take or be given a case.
OWNERS: dict[str, dict[str, str]] = {
    "human:coordinator-sara": COORDINATOR_ON_DUTY,
    "human:gp-aisha": {"owner_id": "Practitioner/gp-aisha", "owner_name": "Dr Aisha (Family Physician)"},
    "human:gp-khan": {"owner_id": "Practitioner/gp-khan", "owner_name": "Dr Khan (Family Physician)"},
    "human:supervisor": ON_CALL,
}


def _minutes(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return default


def result_due_minutes() -> float:
    """After attendance, how long until a missing outcome counts as a delayed result."""
    return _minutes("RABT_RESULT_DUE_MINUTES", 60)


def missed_visit_grace_minutes() -> float:
    """How long after the appointment time a booked visit with no attendance counts as missed."""
    return _minutes("RABT_MISSED_VISIT_GRACE_MINUTES", 60)


def unowned_grace_minutes() -> float:
    """How long a non-critical case may stay unowned before the coordinator on duty is assigned."""
    return _minutes("RABT_UNOWNED_GRACE_MINUTES", 30)


def sla_minutes() -> dict[str, float | None]:
    out = dict(DEFAULT_SLA_MINUTES)
    raw = os.environ.get("RABT_FOLLOWUP_SLA_MINUTES", "").strip()
    if raw:
        try:
            for k, v in json.loads(raw).items():
                if k in out:
                    out[k] = None if v is None else float(v)
        except (ValueError, AttributeError, TypeError):
            pass
    return out


def is_open(case: dict[str, Any]) -> bool:
    return case.get("state") not in CLOSED_STATES


def state_since(case: dict[str, Any]) -> float:
    """When the case entered its current step: the last transition time, else when it was opened."""
    for rec in reversed(case.get("provenance") or []):
        if isinstance(rec, dict) and rec.get("to") == case.get("state") and rec.get("at"):
            return float(rec["at"])
    return float(case.get("created_at") or demo_clock.now())


def compute_flags(case: dict[str, Any], now: float | None = None) -> list[dict[str, Any]]:
    """Follow-up flags for one case. Closed cases have none."""
    if not is_open(case):
        return []
    now = demo_clock.now() if now is None else now
    state = case.get("state") or ""
    ev = case.get("evidence") or {}
    since = state_since(case)
    in_state = max(0.0, now - since)
    flags: list[dict[str, Any]] = []

    sla = sla_minutes().get(state)
    if sla is not None and in_state > sla * 60:
        flags.append({"flag": "overdue", "reason": "sla", "since": since + sla * 60, "sla_s": sla * 60})

    appt = ev.get("appointment_at")
    if state == "NoShow":
        flags.append({"flag": "missed_visit", "reason": "no_show", "since": since})
    elif state == "Booked" and appt and not ev.get("attended_encounter") and now > float(appt) + missed_visit_grace_minutes() * 60:
        flags.append({"flag": "missed_visit", "reason": "past_appointment", "since": float(appt)})
    elif int(ev.get("no_shows") or 0) > 0 and state in {"Referred", "ReferralRejected"}:
        flags.append({"flag": "missed_visit", "reason": "rebook_pending", "since": since})

    attended_at = ev.get("attended_at")
    if ev.get("attended_encounter") and not ev.get("outcome_document"):
        start = float(attended_at or since)
        if now - start > result_due_minutes() * 60:
            flags.append({"flag": "result_delayed", "reason": "no_outcome", "since": start + result_due_minutes() * 60})
    elif state == "DataQuery":
        due = sla_minutes().get("DataQuery") or 30
        if in_state > due * 60:
            flags.append({"flag": "result_delayed", "reason": "data_query", "since": since + due * 60})

    if not case.get("owner_id"):
        flags.append({"flag": "unowned", "reason": "no_owner", "since": float(case.get("created_at") or since)})
    return flags


def view(case: dict[str, Any], now: float | None = None) -> dict[str, Any]:
    """The follow-up fields the board shows for a case."""
    now = demo_clock.now() if now is None else now
    since = state_since(case)
    sla = sla_minutes().get(case.get("state") or "")
    ev = case.get("evidence") or {}
    return {
        "owner_id": case.get("owner_id"),
        "owner_name": case.get("owner_name"),
        "state_since": since,
        "time_in_state_s": int(max(0.0, now - since)),
        "sla_s": int(sla * 60) if sla is not None else None,
        "appointment_at": ev.get("appointment_at"),
        "flags": compute_flags(case, now),
        "now": now,
    }


def needs_on_call(case: dict[str, Any]) -> bool:
    return case.get("state") == "Escalated" or case.get("urgency") == "CRITICAL"
