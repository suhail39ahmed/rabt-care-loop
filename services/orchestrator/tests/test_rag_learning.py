"""RAG retrieval, grounded answers, caching, Azure Search query shape, learning loop, ingestion plan."""

from __future__ import annotations

import shutil
from pathlib import Path

import httpx
import pytest
from agents.common import ai_metrics, llm_client, semantic_cache
from agents.rag import answer as answer_mod
from agents.rag import retrieve as retrieve_mod
from agents.rag.retrieve import local_search

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(autouse=True)
def _iso(monkeypatch, tmp_path):
    kb = tmp_path / "kb"
    shutil.copytree(ROOT / "data" / "kb", kb, ignore=shutil.ignore_patterns("_pending"))
    monkeypatch.setenv("KB_DIR", str(kb))
    monkeypatch.setenv("AI_ENABLED", "false")
    monkeypatch.delenv("AZURE_SEARCH_ENDPOINT", raising=False)
    monkeypatch.delenv("CONTENT_SAFETY_ENDPOINT", raising=False)
    semantic_cache.clear()
    ai_metrics.reset()
    yield kb
    semantic_cache.clear()


def test_local_bm25_language_aware():
    en = local_search("What does a positive FIT mean?", language="en")
    assert en and en[0]["doc_id"] == "fit_positive"
    ar = local_search("ما هو السكري التراكمي؟", language="ar")
    assert ar and ar[0]["doc_id"] == "hba1c_ar"
    pay = local_search("how do I claim reimbursement invoice", language="en")
    assert pay[0]["doc_id"] in {"insurance_claim_documents", "paying_for_your_visit"}


async def test_extractive_answer_cites_and_caches():
    out = await answer_mod.answer("What does a positive FIT mean?", language="en")
    assert out["method"] == "rag_extractive" and out["citations"][0]["id"] == "fit_positive"
    assert not out["ai_generated"] and "not a diagnosis" in out["answer"]
    again = await answer_mod.answer("what does a positive FIT mean", language="en")
    assert again["cache"]["layer"] == "app"
    assert ai_metrics.snapshot()["counters"]["app_cache_hit"] == 1


async def test_gap_and_crisis():
    gap = await answer_mod.answer("Can I park my car at the zoo?", language="en")
    assert gap["gap"] is True and gap["citations"] == []
    crisis = await answer_mod.answer("I want to kill myself", language="en")
    assert crisis["hand_off"] and crisis["method"] == "crisis_rule"


async def test_llm_answer_must_be_grounded(monkeypatch):
    monkeypatch.setenv("AI_ENABLED", "true")

    async def no_embed(_t):
        return None

    replies = iter(["A positive FIT means more checks may be recommended [1].", "You need 5 tests now."])

    async def fake_chat(**kw):
        assert kw["task"] == "rag_answer" and kw["documents"] and kw["cache_scope"].startswith("en|")
        return next(replies)

    monkeypatch.setattr(llm_client, "embed", no_embed)
    monkeypatch.setattr(llm_client, "chat_completion", fake_chat)
    good = await answer_mod.answer("What does a positive FIT mean?", language="en")
    assert good["method"] == "rag_llm_grounded" and good["ai_generated"]
    semantic_cache.clear()
    bad = await answer_mod.answer("What does a positive FIT mean?", language="en")  # no citation, new number
    assert bad["method"] == "rag_extractive"


def test_azure_search_query_shape(monkeypatch):
    seen = {}

    def post(url, json=None, headers=None, timeout=None):
        seen.update(url=url, body=json, headers=headers)
        return httpx.Response(200, json={"value": [{"id": "fit_positive--0", "doc_id": "fit_positive",
                                                    "title": "FIT", "content": "text", "language": "en",
                                                    "@search.score": 3.2}]}, request=httpx.Request("POST", url))

    monkeypatch.setenv("AZURE_SEARCH_ENDPOINT", "https://apim-rabt-pilot-sea.azure-api.net/search")
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setattr(retrieve_mod.httpx, "post", post)
    hits = retrieve_mod.azure_search("positive FIT", language="ar", vector=[0.1, 0.2])
    assert seen["url"].endswith("/search/indexes/rabt-kb-v2/docs/search?api-version=2024-07-01")
    assert seen["body"]["filter"] == "approved eq true and language eq 'ar'"
    assert seen["body"]["vectorQueries"][0]["fields"] == "content_vector"
    assert seen["headers"]["api-key"] == "k" and hits[0]["source"] == "azure_search"


def test_azure_search_falls_back_to_local(monkeypatch):
    def boom(*a, **k):
        raise httpx.ConnectError("down")

    monkeypatch.setenv("AZURE_SEARCH_ENDPOINT", "https://x/search")
    monkeypatch.setattr(retrieve_mod.httpx, "post", boom)
    assert retrieve_mod.azure_search("positive FIT", language="en")[0]["source"] == "local"


def test_learning_loop_api(_iso):
    from app.main import app
    from fastapi.testclient import TestClient

    coord = {"X-Rabt-Persona": "human:coordinator-sara"}
    gp = {"X-Rabt-Persona": "human:gp-aisha"}
    with TestClient(app) as c:
        v0 = c.get("/kb").json()["index_version"]
        body = {"title": "Can I drive after a colonoscopy?", "language": "en",
                "content": "Most clinics ask you not to drive for the rest of the day. Call +971 50 123 4567."}
        assert c.post("/kb/suggestions", json=body, headers={"X-Rabt-Persona": "patient:fatima"}).status_code == 403
        r = c.post("/kb/suggestions", json=body, headers=coord)
        assert r.status_code == 200 and "[PHONE]" in r.json()["content"]
        sid = r.json()["id"]
        assert [p["id"] for p in c.get("/kb/pending").json()] == [sid]
        assert c.post(f"/kb/pending/{sid}/approve", headers=coord).status_code == 403
        ok = c.post(f"/kb/pending/{sid}/approve", headers=gp)
        assert ok.status_code == 200 and ok.json()["approved_by"] == "human:gp-aisha"
        kb = c.get("/kb").json()
        assert kb["index_version"] != v0 and sid in [d["id"] for d in kb["docs"]]
        assert c.get("/kb/pending").json() == []
    text = (_iso / f"{sid}.md").read_text(encoding="utf-8")
    assert text.startswith("---\n") and "clinical_review_status: approved" in text and "reviewer: human:gp-aisha" in text


def test_ingest_plan_and_schema():
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    import rag_ingest

    rows = rag_ingest.build_docs(rag_ingest.local_sources())
    assert len({r["id"] for r in rows}) == len(rows)
    assert {"ar", "en"} <= {r["language"] for r in rows} and all(r["approved"] for r in rows)
    schema = rag_ingest.index_schema("rabt-kb")
    vec = next(f for f in schema["fields"] if f["name"] == "content_vector")
    assert vec["dimensions"] == 1536 and schema["semantic"]["configurations"][0]["name"] == "rabt-semantic"


def test_question_language_follows_the_script_the_patient_typed():
    from app.coordinator import question_language

    assert question_language("كيف أستعد لتنظير القولون؟", "en") == "ar"
    assert question_language("How do I prepare for a colonoscopy?", "ar") == "en"
    assert question_language("FIT ايجابي ماذا يعني", "en") == "ar"
    assert question_language("123", "ar") == "ar"
    assert question_language("hello", "fr") == "en"
