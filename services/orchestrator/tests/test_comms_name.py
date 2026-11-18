"""The patient's name is kept out of the model prompt and put back in the drafted message."""

from __future__ import annotations

import pytest
from agents.common import llm_client
from agents.comms import agent as comms
from agents.comms.agent import fill_name


def test_fill_name_replaces_scrubber_placeholders():
    assert fill_name("[NAME], please book.", "Ravi") == "Ravi, please book."
    assert fill_name("Hi [NAME_1] / [PERSON_2]", "Ravi") == "Hi Ravi / Ravi"
    assert fill_name("No placeholder here", "Ravi") == "No placeholder here"


@pytest.mark.asyncio
async def test_comms_never_sends_name_and_restores_it(monkeypatch):
    seen: dict[str, str] = {}

    async def fake_chat_completion(*, system, user, **_kw):
        seen["user"] = user
        return user.replace("needs a confirmatory next step", "needs one more check")

    monkeypatch.setattr(llm_client, "chat_completion", fake_chat_completion)
    out = await comms.run(
        {
            "case_id": "c1",
            "inputs": {"language": "en", "result_class": "fit_positive", "first_name_token": "Ravi"},
        }
    )
    msg = out["outputs"]["message"]
    assert "Ravi" not in seen["user"] and "[NAME]" in seen["user"]
    assert msg.startswith("Ravi,") and "[NAME" not in msg


@pytest.mark.asyncio
async def test_template_fallback_also_has_the_name(monkeypatch):
    monkeypatch.setenv("AI_ENABLED", "false")
    out = await comms.run(
        {"case_id": "c1", "inputs": {"language": "ar", "result_class": "fit_positive", "first_name_token": "رافي"}}
    )
    msg = out["outputs"]["message"]
    assert msg.startswith("رافي") and "[NAME" not in msg
