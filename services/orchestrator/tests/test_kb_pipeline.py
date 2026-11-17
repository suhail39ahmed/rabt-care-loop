"""Simulated KB metadata, heading-aware chunking, offline ingestion pipeline and the RAG eval set."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import httpx
import pytest
from agents.rag import pipeline
from agents.rag.chunking import chunk_document, estimate_tokens, parse_doc
from agents.rag.retrieve import local_search, search_filter

ROOT = Path(__file__).resolve().parents[3]
KB = ROOT / "data" / "kb"
REQUIRED = ("id", "title", "language", "topic", "audience", "clinical_review_status", "reviewer", "version",
            "last_reviewed", "source")


@pytest.fixture()
def kb(monkeypatch, tmp_path):
    d = tmp_path / "kb"
    shutil.copytree(KB, d, ignore=shutil.ignore_patterns("_pending"))
    monkeypatch.setenv("KB_DIR", str(d))
    monkeypatch.setenv("AI_ENABLED", "false")
    monkeypatch.delenv("AZURE_SEARCH_ENDPOINT", raising=False)
    return d


def _sources(d: Path) -> dict[str, str]:
    return {p.name: p.read_text(encoding="utf-8") for p in sorted(d.glob("*.md"))}


def test_every_doc_has_front_matter_and_demo_label():
    import yaml

    docs = sorted(KB.glob("*.md"))
    assert len(docs) >= 25
    for p in docs:
        text = p.read_text(encoding="utf-8")
        assert text.startswith("---\n"), p.name
        meta = yaml.safe_load(text[4 : text.index("\n---\n", 4)])
        assert all(k in meta for k in REQUIRED), p.name
        assert meta["id"] == p.stem and meta["language"] in ("en", "ar")
        assert meta["clinical_review_status"] in ("approved", "draft")
        assert meta["source"] == "simulated demo content, not medical advice"
    langs = {parse_doc(p.read_text(encoding="utf-8"), p.stem)["language"] for p in docs}
    assert langs == {"en", "ar"}


def test_heading_aware_token_chunks_with_overlap():
    para = " ".join(f"Sentence number {i} explains one small step of the bowel preparation." for i in range(60))
    body = f"# Prep\n\n## Day before\n\n{para}\n\n## On the day\n\nBring your medicines list."
    chunks = chunk_document(body, title="Prep", max_tokens=120, overlap_tokens=30)
    assert {c["heading"] for c in chunks} == {"Prep > Day before", "Prep > On the day"}
    assert all(c["tokens"] <= 120 for c in chunks)
    day = [c for c in chunks if c["heading"] == "Prep > Day before"]
    assert len(day) > 2
    last_sentence = day[0]["text"].split("\n\n")[-1]
    assert day[1]["text"].split("\n\n")[1] == last_sentence  # overlap carried into the next chunk
    assert all(c["text"].startswith(c["heading"]) for c in chunks)
    assert estimate_tokens("نتيجة فحص إيجابية") > estimate_tokens("positive test result") - 2


def test_legacy_comment_counts_as_approved_and_plain_doc_as_draft():
    legacy = parse_doc("<!-- approved_by: human:gp-aisha at 2026-11-16T00:00Z -->\n# T\n\nBody", "x")
    assert legacy["approved"] and legacy["reviewer"] == "human:gp-aisha"
    assert not parse_doc("# T\n\nBody", "y")["approved"]


def test_drafts_are_never_retrievable(kb):
    assert (kb / "insurance_dental_draft.md").exists()
    for q in ("dental cover draft", "sedation options draft clinic"):
        assert all("draft" not in h["doc_id"] for h in local_search(q, language="en", k=10))


def test_metadata_filters():
    hits = local_search("what documents do I need", language="en", k=5, topic="insurance")
    assert hits and {h["topic"] for h in hits} == {"insurance"}
    f = search_filter("ar", topic="insurance", audience="patient")
    assert f == "approved eq true and language eq 'ar' and topic eq 'insurance' and audience eq 'patient'"


def test_offline_sync_is_idempotent_and_tracks_changes(kb, tmp_path):
    store = pipeline.LocalIndexStore(tmp_path / "idx.json")
    emb = pipeline.HashEmbedder(dims=64)
    first = pipeline.sync(_sources(kb), store, emb)
    assert first["uploaded"] == first["chunks"] > first["approved_documents"] >= 25
    assert first["skipped_not_approved"] == ["colonoscopy_sedation_draft", "insurance_dental_draft"]
    assert {r["doc_id"] for r in store.rows()}.isdisjoint(first["skipped_not_approved"])
    assert all(len(r["content_vector"]) == 64 and r["approved"] for r in store.rows())

    again = pipeline.sync(_sources(kb), store, emb)
    assert (again["uploaded"], again["deleted"], again["unchanged"]) == (0, 0, first["chunks"])

    (kb / "teach_back.md").write_text((kb / "teach_back.md").read_text(encoding="utf-8") + "\nOne more line.\n",
                                      encoding="utf-8")
    (kb / "fit_negative.md").unlink()
    p = kb / "insurance_copay.md"
    p.write_text(p.read_text(encoding="utf-8").replace("clinical_review_status: approved",
                                                      "clinical_review_status: draft"), encoding="utf-8")
    changed = pipeline.sync(_sources(kb), store, emb)
    docs = {r["doc_id"] for r in store.rows()}
    assert "fit_negative" not in docs and "insurance_copay" not in docs and "teach_back" in docs
    assert changed["uploaded"] >= 1 and changed["deleted"] >= 2


def test_plan_sync_removes_shrunk_chunks():
    rows = [{"id": "a--0", "doc_id": "a", "doc_hash": "h2"}]
    existing = [{"id": "a--0", "doc_id": "a", "doc_hash": "h1"}, {"id": "a--1", "doc_id": "a", "doc_hash": "h1"}]
    upload, delete = pipeline.plan_sync(rows, existing)
    assert [r["id"] for r in upload] == ["a--0"] and delete == ["a--1"]


def test_gateway_embedder_calls_apim(monkeypatch):
    seen = {}

    def post(url, headers=None, json=None, timeout=None):
        seen.update(url=url, headers=headers, body=json)
        data = [{"index": i, "embedding": [float(i)]} for i in range(len(json["input"]))]
        return httpx.Response(200, json={"data": data}, request=httpx.Request("POST", url))

    monkeypatch.setattr(pipeline.httpx, "post", post)
    emb = pipeline.GatewayEmbedder("https://apim-rabt-pilot-sea.azure-api.net", "embed", api_key="k",
                                   api_version="2024-10-21")
    assert emb(["a", "b"]) == [[0.0], [1.0]]
    assert seen["url"] == ("https://apim-rabt-pilot-sea.azure-api.net/openai/deployments/embed/embeddings"
                           "?api-version=2024-10-21")
    assert seen["headers"]["api-key"] == "k" and seen["headers"]["x-rabt-task"] == "kb-ingest"


def test_index_schema_versioned_with_metadata_filters():
    schema = pipeline.index_schema()
    assert schema["name"] == "rabt-kb-v2"
    fields = {f["name"]: f for f in schema["fields"]}
    for f in ("language", "topic", "audience", "clinical_review_status", "approved", "doc_hash"):
        assert fields[f]["filterable"]
    assert fields["content_vector"]["dimensions"] == 1536


def test_rag_eval_offline(kb):
    sys.path.insert(0, str(ROOT / "scripts"))
    import rag_eval

    rep = rag_eval.run()
    assert rep["retrieval"]["n"] >= 40
    assert rep["retrieval"]["hit@3"] >= 0.9 and rep["retrieval"]["hit@1"] >= 0.8
    assert rep["escalation"]["pass_rate"] == 1.0 and rep["drafts_leaked"] == 0
