"""Payment paths for navigator options: cashless at a network hospital, or pay-and-claim.

Deterministic and rule-based (synthetic plan data). No LLM decides how a patient pays.

Modes, in order of preference:
  cashless       In-network and the provider bills the insurer directly. Patient pays only the co-pay.
  reimbursement  Patient pays the provider, then claims back from the insurer (pay-and-claim).
  self_pay       No insurer support for this option; patient pays in full. Explicit opt-in only.
"""

from __future__ import annotations

from typing import Any, Literal

PaymentMode = Literal["cashless", "reimbursement", "self_pay"]

# Preference weight used by the navigator score. Cashless network hospitals win ties by design.
MODE_WEIGHT: dict[str, float] = {"cashless": 40.0, "reimbursement": 20.0, "self_pay": 10.0}

# Default fee estimate (AED) used when a provider has no list price in the synthetic directory.
DEFAULT_VISIT_FEE_AED = 300

CLAIM_STATUSES = (
    "not_started",
    "documents_ready",
    "submitted",
    "approved",
    "rejected",
    "paid",
)
# Who may move a claim to each status: the patient handles paperwork; the insurer decision is
# recorded by staff (coordinator / physician / supervisor) from the insurer reply.
PATIENT_CLAIM_STATUSES = frozenset({"documents_ready", "submitted"})
CLAIM_TRANSITIONS: dict[str, frozenset[str]] = {
    "not_started": frozenset({"documents_ready"}),
    "documents_ready": frozenset({"submitted"}),
    "submitted": frozenset({"approved", "rejected"}),
    "approved": frozenset({"paid"}),
    "rejected": frozenset({"documents_ready"}),  # fix paperwork and resubmit
    "paid": frozenset(),
}

REQUIRED_DOCUMENTS: list[dict[str, str]] = [
    {"id": "invoice", "en": "Itemised invoice from the provider (stamped)", "ar": "فاتورة مفصلة من مقدم الخدمة (مختومة)"},
    {"id": "receipt", "en": "Payment receipt", "ar": "إيصال الدفع"},
    {"id": "referral", "en": "Referral letter from your doctor (Rabt adds this to your case)", "ar": "خطاب التحويل من طبيبك (يضيفه ربط إلى ملفك)"},
    {"id": "report", "en": "Medical report or visit summary from the provider", "ar": "تقرير طبي أو ملخص الزيارة من مقدم الخدمة"},
    {"id": "claim_form", "en": "Insurer claim form, signed", "ar": "نموذج المطالبة من شركة التأمين موقّعًا"},
    {"id": "emirates_id", "en": "Emirates ID and insurance card copy", "ar": "نسخة من الهوية الإماراتية وبطاقة التأمين"},
]


def payment_path(
    plan: dict[str, Any],
    provider: dict[str, Any],
    in_network: bool,
    *,
    allow_self_pay: bool = False,
) -> dict[str, Any] | None:
    """Return the payment path for one provider under one plan, or None if the option is not allowed.

    Out-of-network options stay excluded unless the provider accepts self-pay AND either the plan
    reimburses out-of-network care (pay-and-claim) or the patient explicitly opted in to self-pay.
    """
    fee = int(provider.get("fee_aed") or DEFAULT_VISIT_FEE_AED)
    copay_pct = int(plan.get("copay_pct", 0))
    reimb = plan.get("reimbursement") or {}
    reimb_in = bool(reimb.get("in_network"))
    reimb_oon = bool(reimb.get("out_of_network"))
    reimb_pct = int(reimb.get("pct", 0))

    if in_network and provider.get("cashless", True) and plan.get("cashless", True):
        mode: PaymentMode = "cashless"
        upfront = round(fee * copay_pct / 100)
        expected_back = 0
    elif in_network and reimb_in:
        mode = "reimbursement"
        upfront = fee
        expected_back = round(fee * reimb_pct / 100)
    elif not in_network and provider.get("self_pay_ok") and (reimb_oon or allow_self_pay):
        if reimb_oon:
            mode = "reimbursement"
            upfront = fee
            expected_back = round(fee * reimb_pct / 100)
        else:
            mode = "self_pay"
            upfront = fee
            expected_back = 0
    else:
        return None

    return {
        "mode": mode,
        "fee_aed": fee,
        "patient_upfront_aed": upfront,
        "expected_reimbursement_aed": expected_back,
        "patient_net_cost_aed": upfront - expected_back,
        "reimbursement_pct": reimb_pct if mode == "reimbursement" else 0,
        "claim_window_days": int(reimb.get("claim_window_days", 30)) if mode == "reimbursement" else None,
    }


def reimbursement_guide(path: dict[str, Any], plan_name: str = "your plan") -> dict[str, Any]:
    """Plain-language steps + documents for a pay-and-claim option (EN/AR)."""
    window = path.get("claim_window_days") or 30
    pct = path.get("reimbursement_pct") or 0
    upfront = path.get("patient_upfront_aed")
    back = path.get("expected_reimbursement_aed")
    return {
        "summary_en": (
            f"You pay about AED {upfront} at the visit, then claim from {plan_name}. "
            f"It usually pays back {pct}% (about AED {back}). Submit within {window} days."
        ),
        "summary_ar": (
            f"تدفع حوالي {upfront} درهم عند الزيارة ثم تقدّم مطالبة إلى شركة التأمين. "
            f"عادةً يُسترد {pct}% (حوالي {back} درهم). قدّم المطالبة خلال {window} يومًا."
        ),
        "steps_en": [
            "Book and attend the visit; pay the provider.",
            "Ask the provider for an itemised invoice, receipt and visit report.",
            f"Send the documents to the insurer within {window} days (Rabt tracks this for you).",
            "Rabt records the insurer decision and tells you when money is paid back.",
        ],
        "steps_ar": [
            "احجز موعدك واحضره وادفع لمقدم الخدمة.",
            "اطلب فاتورة مفصلة وإيصال الدفع وتقرير الزيارة.",
            f"أرسل المستندات إلى شركة التأمين خلال {window} يومًا (يتابعها ربط معك).",
            "يسجّل ربط قرار شركة التأمين ويخبرك عند استرداد المبلغ.",
        ],
        "documents": REQUIRED_DOCUMENTS,
    }


def new_claim(option: dict[str, Any], path: dict[str, Any], plan_name: str) -> dict[str, Any]:
    """Claim task created when a patient books a reimbursement option."""
    return {
        "option_id": option.get("id"),
        "provider_name": option.get("name"),
        "status": "not_started",
        "amount_claimed_aed": path.get("patient_upfront_aed"),
        "expected_reimbursement_aed": path.get("expected_reimbursement_aed"),
        "claim_window_days": path.get("claim_window_days"),
        "documents": [{"id": d["id"], "label": d["en"], "provided": False} for d in REQUIRED_DOCUMENTS],
        "guide": reimbursement_guide(path, plan_name),
        "history": [],
    }


def advance_claim(claim: dict[str, Any], to_status: str, *, actor_role: str) -> dict[str, Any]:
    """Validate and apply a claim status change. Raises ValueError on an illegal move."""
    if to_status not in CLAIM_STATUSES:
        raise ValueError(f"unknown claim status: {to_status}")
    current = claim.get("status", "not_started")
    if to_status not in CLAIM_TRANSITIONS.get(current, frozenset()):
        raise ValueError(f"claim cannot move {current} -> {to_status}")
    if actor_role == "patient" and to_status not in PATIENT_CLAIM_STATUSES:
        raise PermissionError("insurer decisions are recorded by staff")
    out = dict(claim)
    out["status"] = to_status
    if to_status == "documents_ready":
        out["documents"] = [{**d, "provided": True} for d in claim.get("documents") or []]
    return out
