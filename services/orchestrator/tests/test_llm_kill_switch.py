"""LLM path respects AI_ENABLED kill switch (#68, #105)."""

from __future__ import annotations

import pytest
from agents.common.llm_client import ai_enabled, chat_completion
from agents.comms.agent import draft_message


@pytest.mark.asyncio
async def test_kill_switch_blocks_network(monkeypatch):
    monkeypatch.setenv("AI_ENABLED", "false")
    monkeypatch.setenv("LLM_PROVIDER", "openai_compatible")
    monkeypatch.setenv("LLM_BASE_URL", "https://example.invalid/v1")
    monkeypatch.setenv("LLM_MODEL", "gpt-test")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    assert ai_enabled() is False
    assert await chat_completion(system="s", user="u") is None


@pytest.mark.asyncio
async def test_draft_falls_back_to_template(monkeypatch):
    monkeypatch.setenv("AI_ENABLED", "false")
    text, used = await draft_message("Hello patient", "en")
    assert text == "Hello patient"
    assert used is False


def test_azure_url_through_apim_gateway(monkeypatch):
    from agents.common.llm_client import build_chat_url

    monkeypatch.setenv("AZURE_OPENAI_API_VERSION", "2024-10-21")
    gw = "https://apim-rabt-pilot-uaen.azure-api.net"
    want = f"{gw}/openai/deployments/chat-small/chat/completions?api-version=2024-10-21"
    assert build_chat_url("azure", gw, "chat-small") == want
    assert build_chat_url("azure", gw + "/openai/", "chat-small") == want
    assert build_chat_url("azure", gw + "/openai/deployments/chat-small", "x") == want
    assert build_chat_url("openai_compatible", "https://api.example.com/v1/", "m") == (
        "https://api.example.com/v1/chat/completions"
    )


@pytest.mark.asyncio
async def test_azure_sends_api_key_header_only(monkeypatch):
    import httpx
    from agents.common import llm_client

    seen: dict = {}

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, headers=None, json=None):
            seen.update(url=url, headers=headers)
            return httpx.Response(
                200,
                json={"choices": [{"message": {"content": "ok"}}]},
                request=httpx.Request("POST", url),
            )

    monkeypatch.setenv("AI_ENABLED", "true")
    monkeypatch.setenv("LLM_PROVIDER", "azure")
    monkeypatch.setenv("LLM_BASE_URL", "https://apim-rabt-pilot-uaen.azure-api.net")
    monkeypatch.setenv("LLM_MODEL", "chat-small")
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setattr(llm_client.httpx, "AsyncClient", FakeClient)
    assert await llm_client.chat_completion(system="s", user="u") == "ok"
    assert seen["headers"]["api-key"] == "k"
    assert "Authorization" not in seen["headers"]
    assert "/openai/deployments/chat-small/chat/completions?api-version=" in seen["url"]
