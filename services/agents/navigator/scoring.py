"""Insurance-aware navigator — deterministic scoring + optional LLM rationale.

Each option carries a payment path (cashless at a network hospital, pay-and-claim reimbursement,
or explicit self-pay). Cashless network options score highest; the LLM never changes the ranking.
"""

from __future__ import annotations

from typing import Any

from agents.navigator.payment import MODE_WEIGHT, payment_path, reimbursement_guide

MODE_LABEL = {
    "cashless": ("Cashless (network)", "بدون دفع مسبق (ضمن الشبكة)"),
    "reimbursement": ("Pay & claim back", "ادفع ثم استرد"),
    "self_pay": ("Self-pay", "دفع ذاتي"),
}

SPECIALTY_FOR_PATHWAY = {
    "confirmatory_test": "family_medicine",
    "gp_review": "family_medicine",
    "gp_review_critical": "family_medicine",
    "specialist_gastro": "gastroenterology",
    "specialist_gyn": "gynaecology",
    "specialist_breast": "breast",
    "human_triage": "family_medicine",
}



def _days_en(n: object) -> str:
    if not isinstance(n, int):
        return "? days"
    return "1 day" if n == 1 else f"{n} days"


def _days_ar(n: object) -> str:
    if not isinstance(n, int):
        return "? أيام"
    if n == 1:
        return "يوم واحد"
    if n == 2:
        return "يومين"
    return f"{n} أيام" if 3 <= n <= 10 else f"{n} يومًا"

def score_options(
    pathway: str,
    plan_network: set[str],
    providers: list[dict[str, Any]],
    language: str = "en",
    plan: dict[str, Any] | None = None,
    allow_self_pay: bool = False,
) -> list[dict[str, Any]]:
    specialty = SPECIALTY_FOR_PATHWAY.get(pathway, "family_medicine")
    plan = plan or {}
    plan_name = str(plan.get("name") or "your plan")
    ranked: list[dict[str, Any]] = []
    for p in providers:
        if p.get("specialty") != specialty:
            continue
        in_network = p.get("network_id") in plan_network or p.get("id") in plan_network
        path = payment_path(plan, p, in_network, allow_self_pay=allow_self_pay)
        if path is None:
            continue  # out-of-network is excluded unless explicitly self-pay
        mode = path["mode"]
        score = MODE_WEIGHT[mode]
        score += max(0, 30 - float(p.get("distance_km", 10)))
        score += max(0, 20 - float(p.get("earliest_days", 7)))
        if language in (p.get("languages") or []):
            score += 10
        label_en, label_ar = MODE_LABEL[mode]
        option = {
            **p,
            "in_network": in_network,
            "payment": path,
            "score": round(score, 2),
            "rationale_en": (
                f"{label_en} · pay AED {path['patient_upfront_aed']} at visit · "
                f"{p.get('distance_km', '?')} km · earliest in {_days_en(p.get('earliest_days'))}"
            ),
            "rationale_ar": (
                f"{label_ar} · تدفع {path['patient_upfront_aed']} درهم عند الزيارة · "
                f"{p.get('distance_km', '?')} كم · أقرب موعد خلال {_days_ar(p.get('earliest_days'))}"
            ),
        }
        if mode == "reimbursement":
            option["reimbursement_guide"] = reimbursement_guide(path, plan_name)
        ranked.append(option)
    # Deterministic: score, then cashless first, then provider id as a stable tie-break.
    ranked.sort(key=lambda x: (-x["score"], -MODE_WEIGHT[x["payment"]["mode"]], str(x.get("id"))))
    return ranked[:3]


async def run(req: dict[str, Any]) -> dict[str, Any]:
    inputs = req.get("inputs", {})
    pathway = inputs.get("pathway") or "gp_review"
    plan_network = set(inputs.get("plan_network") or [])
    providers = inputs.get("providers") or []
    language = inputs.get("language") or "en"
    plan = inputs.get("plan") or {}
    allow_self_pay = bool(inputs.get("allow_self_pay"))
    options = score_options(pathway, plan_network, providers, language, plan, allow_self_pay)
    if not options:
        return {
            "case_id": req["case_id"],
            "step": "navigate",
            "status": "needs_human",
            "proposed_transition": None,
            "outputs": {"options": [], "error": "no_in_network_options"},
            "evidence_refs": [],
        }
    return {
        "case_id": req["case_id"],
        "step": "navigate",
        "status": "ok",
        "proposed_transition": "Referred",
        "outputs": {
            "options": options,
            "llm_changed_ranking": False,
            "payment_modes": [o["payment"]["mode"] for o in options],
        },
        "evidence_refs": [o["id"] for o in options],
    }
