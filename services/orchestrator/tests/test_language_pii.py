"""Azure AI Language PII layered after the regex scrubber: offline mock of analyze-text, fail closed."""

from __future__ import annotations

import httpx
import pytest
from agents import translation
from agents.common import ai_metrics, language_pii, llm_client
from agents.common.pii import pseudonymize_layered, restore, scrub, scrub_layered

NAMES = {"Fatima", "Omar", "Aisha Al Mansouri", "فاطمة", "12 Corniche Road"}
CATEGORY = {"12 Corniche Road": "Address"}


def fake_language(calls: list[dict]):
    """Mimic analyze-text: return Person / Address entities for known values in each document."""

    def post(url, json=None, headers=None, timeout=None):
        calls.append({"url": url, "body": json, "headers": headers})
        docs = []
        for d in json["analysisInput"]["documents"]:
            ents = [{"text": n, "category": CATEGORY.get(n, "Person"), "offset": d["text"].index(n), "length": len(n),
                     "confidenceScore": 0.93} for n in NAMES if n in d["text"]]
            if "low-confidence" in d["text"]:
                ents.append({"text": "Sam", "category": "Person", "offset": 0, "length": 3, "confidenceScore": 0.2})
            docs.append({"id": d["id"], "entities": ents, "warnings": [], "redactedText": ""})
        return httpx.Response(200, json={"kind": "PiiEntityRecognitionResults",
                                         "results": {"documents": docs, "errors": [], "modelVersion": "x"}},
                              request=httpx.Request("POST", url))

    return post


@pytest.fixture()
def lang_on(monkeypatch):
    monkeypatch.setenv("LANGUAGE_PII_ENABLED", "true")
    monkeypatch.setenv("LANGUAGE_ENDPOINT", "https://apim-rabt-pilot-sea.azure-api.net")
    monkeypatch.setenv("LLM_API_KEY", "sub-key")
    ai_metrics.reset()
    calls: list[dict] = []
    monkeypatch.setattr(language_pii.httpx, "post", fake_language(calls))
    return calls


def test_regex_alone_misses_bare_first_names():
    assert "Fatima" in scrub("Fatima is scared of the colonoscopy, call 050 123 4567").text


def test_layered_catches_bare_names_after_regex(lang_on):
    (out,) = scrub_layered(["Fatima is scared of the colonoscopy, call 050 123 4567. Omar will drive."])
    assert "Fatima" not in out.text and "Omar" not in out.text
    assert "[PHONE]" in out.text and out.text.count("[NAME]") == 2
    assert out.counts["LANGUAGE"] == 2
    body = lang_on[0]["body"]
    assert body["kind"] == "PiiEntityRecognition" and "050 123 4567" not in body["analysisInput"]["documents"][0]["text"]
    assert lang_on[0]["url"].endswith("/language/:analyze-text?api-version=2024-11-01")
    assert lang_on[0]["headers"]["Ocp-Apim-Subscription-Key"] == "sub-key"


def test_language_aware_arabic_and_threshold(lang_on):
    (ar,) = scrub_layered(["فاطمة قلقة من النتيجة"], language="ar")
    assert "فاطمة" not in ar.text and lang_on[-1]["body"]["analysisInput"]["documents"][0]["language"] == "ar"
    (low,) = scrub_layered(["Sam low-confidence mention"], language="tl")  # unsupported -> sent as en
    assert "Sam" in low.text and lang_on[-1]["body"]["analysisInput"]["documents"][0]["language"] == "en"


def test_pseudonymize_layered_restores_locally(lang_on):
    p = pseudonymize_layered("Aisha Al Mansouri lives at 12 Corniche Road, Fatima's sister.")
    assert "Aisha" not in p.text and "Corniche" not in p.text and "[ADDRESS_1]" in p.text
    assert restore(p.text, p.mapping) == "Aisha Al Mansouri lives at 12 Corniche Road, Fatima's sister."


def test_long_text_is_windowed_and_batched(lang_on):
    scrub_layered(["Omar " + "x" * 12000, "Fatima", "a", "b", "c", "d"])
    assert len(lang_on) == 2  # 3 windows + 5 short docs = 8 documents -> batches of 5
    assert all(len(d["text"]) <= 5000 for c in lang_on for d in c["body"]["analysisInput"]["documents"])


def test_disabled_means_regex_only(monkeypatch):
    monkeypatch.setenv("LANGUAGE_PII_ENABLED", "false")
    (out,) = scrub_layered(["Fatima, MRN: AB-12345"])
    assert "[MRN]" in out.text and "Fatima" in out.text


async def test_model_call_fails_closed_when_language_errors(monkeypatch, lang_on):
    def down(*a, **k):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(language_pii.httpx, "post", down)
    monkeypatch.setenv("AI_ENABLED", "true")
    monkeypatch.setenv("LLM_BASE_URL", "https://apim-rabt-pilot-sea.azure-api.net")
    monkeypatch.setenv("LLM_PROVIDER", "azure")
    monkeypatch.setenv("LLM_MODEL", "chat-small")

    async def never(*a, **k):
        raise AssertionError("model must not be called")

    monkeypatch.setattr(llm_client, "_post_chat", never)
    out = await llm_client.chat_completion(system="s", user="Fatima asks about her FIT", task="comms_rewrite")
    assert out is None
    assert ai_metrics.snapshot()["counters"]["pii_fail_closed"] == 1
    assert await llm_client.embed(["Fatima"]) is None


async def test_model_sees_only_layered_text(monkeypatch, lang_on):
    monkeypatch.setenv("AI_ENABLED", "true")
    monkeypatch.setenv("LLM_BASE_URL", "https://apim-rabt-pilot-sea.azure-api.net")
    monkeypatch.setenv("LLM_PROVIDER", "azure")
    monkeypatch.setenv("LLM_MODEL", "chat-small")
    seen = {}

    async def fake_post(client, provider, model, headers, payload):
        seen["payload"] = payload
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}], "usage": {}},
                              request=httpx.Request("POST", "https://x"))

    monkeypatch.setattr(llm_client, "_post_chat", fake_post)
    assert await llm_client.chat_completion(system="s", user="Omar missed his visit", task="comms_rewrite") == "ok"
    assert "Omar" not in str(seen["payload"])


async def test_translation_unavailable_when_language_down(monkeypatch, lang_on):
    def down(*a, **k):
        raise httpx.ReadTimeout("slow")

    monkeypatch.setattr(language_pii.httpx, "post", down)
    out = await translation.translate("Fatima will come tomorrow with her husband", "ar")
    assert out["method"] == "unavailable" and out["text"] is None
