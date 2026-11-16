"""Insurance navigator mock A2A (#74–#77, #107)."""

from app.insurer import ALLOWED_FIELDS, check_coverage


def test_consent_required():
    out = check_coverage(plan_id="plan-a", provider_id="p1", consent=False)
    assert out["reason_code"] == "CONSENT_REQUIRED"


def test_allowlisted_fields_only():
    out = check_coverage(plan_id="plan-a", provider_id="p1", consent=True)
    assert set(out) <= ALLOWED_FIELDS


def test_preauth_scenario():
    out = check_coverage(plan_id="plan-b", provider_id="p1", consent=True)
    assert out["preauth_required"] is True
    assert out["preauth_status"] == "pending"
