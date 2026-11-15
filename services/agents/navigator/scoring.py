"""Insurance-aware navigator — deterministic scoring + optional LLM rationale."""

from __future__ import annotations

from typing import Any

SPECIALTY_FOR_PATHWAY = {
    "confirmatory_test": "family_medicine",
    "gp_review": "family_medicine",
    "gp_review_critical": "family_medicine",
    "specialist_gastro": "gastroenterology",
    "specialist_gyn": "gynaecology",
    "specialist_breast": "breast",
    "human_triage": "family_medicine",
}


def score_options(
    pathway: str,
    plan_network: set[str],
    providers: list[dict[str, Any]],
    language: str = "en",
) -> list[dict[str, Any]]:
    specialty = SPECIALTY_FOR_PATHWAY.get(pathway, "family_medicine")
    ranked: list[dict[str, Any]] = []
    for p in providers:
        if p.get("specialty") != specialty:
            continue
        in_network = p.get("network_id") in plan_network or p.get("id") in plan_network
        if not in_network and not p.get("self_pay_ok"):
            continue  # exclude out-of-network unless self-pay
        score = 0.0
        score += 40 if in_network else 10
        score += max(0, 30 - float(p.get("distance_km", 10)))
        score += max(0, 20 - float(p.get("earliest_days", 7)))
        if language in (p.get("languages") or []):
            score += 10
        ranked.append(
            {
                **p,
                "in_network": in_network,
                "score": round(score, 2),
                "rationale_en": (
                    f"{'In-network' if in_network else 'Self-pay'} · "
                    f"{p.get('distance_km', '?')} km · earliest in {p.get('earliest_days', '?')} days"
                ),
                "rationale_ar": (
                    f"{'ضمن الشبكة' if in_network else 'دفع ذاتي'} · "
                    f"{p.get('distance_km', '?')} كم · أقرب موعد خلال {p.get('earliest_days', '?')} أيام"
                ),
            }
        )
    ranked.sort(key=lambda x: x["score"], reverse=True)
    return ranked[:3]


async def run(req: dict[str, Any]) -> dict[str, Any]:
    inputs = req.get("inputs", {})
    pathway = inputs.get("pathway") or "gp_review"
    plan_network = set(inputs.get("plan_network") or [])
    providers = inputs.get("providers") or []
    language = inputs.get("language") or "en"
    options = score_options(pathway, plan_network, providers, language)
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
        "outputs": {"options": options, "llm_changed_ranking": False},
        "evidence_refs": [o["id"] for o in options],
    }
