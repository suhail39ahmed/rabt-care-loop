"""Prompt-injection benchmark and the gateway (layer 2) refusal path."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[3]


def _bench():
    spec = importlib.util.spec_from_file_location("run_safety", ROOT / "benchmark" / "safety" / "run_safety.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def test_every_attack_blocked_and_no_benign_question_blocked():
    report = _bench().run()
    assert report["attack_block_rate"] == 1.0
    assert report["false_positive_rate"] == 0.0
    assert report["passed"] == report["total"] >= 14


@pytest.mark.asyncio
async def test_gateway_403_is_counted_and_not_failed_over(monkeypatch):
    from agents.common import ai_metrics, llm_client

    monkeypatch.setenv("AI_ENABLED", "true")
    monkeypatch.setenv("LLM_PROVIDER", "azure")
    monkeypatch.setenv("LLM_BASE_URL", "https://apim.example")
    monkeypatch.setenv("LLM_MODEL_SMALL", "chat-small")
    monkeypatch.setenv("LLM_MODEL_STRONG", "chat-strong")
    monkeypatch.setenv("LANGUAGE_PII_ENABLED", "false")
    monkeypatch.delenv("CONTENT_SAFETY_ENDPOINT", raising=False)
    calls = []

    async def fake_post(client, provider, model, headers, payload):
        calls.append(model)
        req = httpx.Request("POST", "https://apim.example")
        raise httpx.HTTPStatusError("blocked", request=req, response=httpx.Response(403, request=req))

    monkeypatch.setattr(llm_client, "_post_chat", fake_post)
    before = ai_metrics.snapshot()["counters"].get("gateway_safety_blocks", 0)
    out = await llm_client.chat_completion(system="s", user="hello there", task="comms_rewrite")
    assert out is None
    assert calls == ["chat-small"]
    assert ai_metrics.snapshot()["counters"]["gateway_safety_blocks"] == before + 1


def test_safety_endpoint_reports_benchmark_and_live_counters():
    from app.main import app
    from fastapi.testclient import TestClient

    _bench().main()
    with TestClient(app) as c:
        data = c.get("/benchmark/safety").json()
    assert data["benchmark"]["attack_block_rate"] == 1.0
    assert set(data["live"]) >= {"injection_blocks", "prompt_shield_blocks", "gateway_safety_blocks"}
