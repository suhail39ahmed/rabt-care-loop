"""Case state machine — deterministic backbone of Rabt (§5.5)."""

from __future__ import annotations

from enum import Enum
from typing import Any


class S(str, Enum):
    NEW = "New"
    DATA_QUERY = "DataQuery"
    TRIAGED = "Triaged"
    ESCALATED = "Escalated"
    AWAITING_OWNER = "AwaitingOwner"
    OWNED = "Owned"
    NOTIFIED = "PatientNotified"
    UNREACHABLE = "Unreachable"
    HUMAN_CALLBACK = "HumanCallback"
    UNDERSTOOD = "Understood"
    REFERRED = "Referred"
    REF_REJECTED = "ReferralRejected"
    BOOKED = "Booked"
    NO_SHOW = "NoShow"
    ATTENDED = "Attended"
    CLOSURE_PENDING = "ClosurePending"
    CLOSED = "Closed"
    TRANSFERRED = "Transferred"
    ON_HOLD_CONSENT = "OnHoldConsent"
    CLOSED_BY_HUMAN = "ClosedByHuman"


# Open states may enter ClosurePending for exceptional two-person close (#25).
_OPEN_TO_CLOSURE_PENDING = {
    S.DATA_QUERY,
    S.AWAITING_OWNER,
    S.OWNED,
    S.NOTIFIED,
    S.UNREACHABLE,
    S.HUMAN_CALLBACK,
    S.UNDERSTOOD,
    S.REFERRED,
    S.REF_REJECTED,
    S.BOOKED,
    S.NO_SHOW,
    S.ATTENDED,
    S.ESCALATED,
    S.TRANSFERRED,
    S.ON_HOLD_CONSENT,
}

ALLOWED: dict[S, set[S]] = {
    S.NEW: {S.DATA_QUERY, S.TRIAGED},
    S.DATA_QUERY: {S.NEW, S.CLOSURE_PENDING},
    S.TRIAGED: {S.ESCALATED, S.AWAITING_OWNER},
    S.AWAITING_OWNER: {S.OWNED, S.AWAITING_OWNER, S.CLOSURE_PENDING},
    S.OWNED: {S.NOTIFIED, S.TRANSFERRED, S.ON_HOLD_CONSENT, S.CLOSURE_PENDING},
    S.NOTIFIED: {S.UNREACHABLE, S.UNDERSTOOD, S.HUMAN_CALLBACK, S.ON_HOLD_CONSENT, S.CLOSURE_PENDING},
    S.UNREACHABLE: {S.ESCALATED, S.CLOSURE_PENDING},
    S.HUMAN_CALLBACK: {S.UNDERSTOOD, S.OWNED, S.CLOSURE_PENDING},
    S.UNDERSTOOD: {S.REFERRED, S.CLOSURE_PENDING},
    S.REFERRED: {S.REF_REJECTED, S.BOOKED, S.CLOSURE_PENDING},
    S.REF_REJECTED: {S.REFERRED, S.CLOSURE_PENDING},
    S.BOOKED: {S.ATTENDED, S.NO_SHOW, S.CLOSURE_PENDING},
    S.NO_SHOW: {S.NOTIFIED, S.CLOSURE_PENDING},
    S.ATTENDED: {S.CLOSURE_PENDING},
    # Restore on reject/timeout (#51); Attended included for missing-outcome bounce (#53).
    S.CLOSURE_PENDING: {
        S.CLOSED,
        S.OWNED,
        S.ATTENDED,
        S.ON_HOLD_CONSENT,
        S.CLOSED_BY_HUMAN,
        *_OPEN_TO_CLOSURE_PENDING,
    },
    S.ESCALATED: {S.OWNED, S.CLOSURE_PENDING},
    S.TRANSFERRED: {S.AWAITING_OWNER, S.CLOSURE_PENDING},
    S.ON_HOLD_CONSENT: {S.OWNED, S.CLOSED_BY_HUMAN, S.CLOSURE_PENDING},
    S.CLOSED: set(),
    S.CLOSED_BY_HUMAN: set(),
}

FHIR_STATUS: dict[S, str] = {
    S.NEW: "requested",
    S.DATA_QUERY: "on-hold",
    S.TRIAGED: "requested",
    S.ESCALATED: "in-progress",
    S.AWAITING_OWNER: "requested",
    S.OWNED: "accepted",
    S.NOTIFIED: "in-progress",
    S.UNREACHABLE: "in-progress",
    S.HUMAN_CALLBACK: "in-progress",
    S.UNDERSTOOD: "in-progress",
    S.REFERRED: "in-progress",
    S.REF_REJECTED: "in-progress",
    S.BOOKED: "in-progress",
    S.NO_SHOW: "in-progress",
    S.ATTENDED: "in-progress",
    S.CLOSURE_PENDING: "in-progress",
    S.TRANSFERRED: "requested",
    S.ON_HOLD_CONSENT: "on-hold",
    S.CLOSED: "completed",
    S.CLOSED_BY_HUMAN: "cancelled",
}


class IllegalTransition(Exception):
    """Raised when a transition is not allowed by the state machine."""


def transition(
    current: S,
    target: S,
    *,
    actor: str,
    reason: str,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a transition record or raise IllegalTransition."""
    if target not in ALLOWED[current]:
        raise IllegalTransition(f"{current.value} -> {target.value}")
    if target is S.CLOSED and not (evidence or {}).get("closure_ok"):
        raise IllegalTransition("closure requires verified evidence")
    if target is S.CLOSED_BY_HUMAN and not actor.startswith("human:"):
        raise IllegalTransition("only a human can close without evidence")
    return {
        "from": current.value,
        "to": target.value,
        "actor": actor,
        "reason": reason,
        "fhir_status": FHIR_STATUS[target],
        "evidence": evidence or {},
    }


def can_transition(current: S, target: S) -> bool:
    return target in ALLOWED[current]
