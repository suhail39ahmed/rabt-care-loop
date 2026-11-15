import pytest
from agents.common.guardrails import grounded_numbers, scrub_pii
from app.contracts import TOOL_SCOPES
from app.coordinator import MAX_STEPS
from app.tools import ToolScopeError, assert_tool_allowed


def test_scrub_pii_redacts_phone():
    assert "[PHONE]" in scrub_pii("Call me at 050-123-4567 please")


def test_grounded_numbers_rejects_unknown():
    assert grounded_numbers("Your value is 7.2", ["7.2"]) is True
    assert grounded_numbers("Your value is 9.9", ["7.2"]) is False


def test_tool_scope_refuses_out_of_scope():
    assert_tool_allowed("triage", "read_case_bundle")
    with pytest.raises(ToolScopeError):
        assert_tool_allowed("triage", "send_message")


def test_max_steps_constant_and_tool_scopes_defined():
    assert MAX_STEPS == 8
    assert "comms" in TOOL_SCOPES
    assert "send_message" in TOOL_SCOPES["escalation"]
