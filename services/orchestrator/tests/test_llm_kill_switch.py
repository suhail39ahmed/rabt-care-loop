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
