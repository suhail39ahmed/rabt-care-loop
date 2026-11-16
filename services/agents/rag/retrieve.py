"""Retrieval over the approved KB: Azure AI Search (hybrid) when configured, local BM25 otherwise (#92).

Azure: AZURE_SEARCH_ENDPOINT is the APIM `/search` API (read-only, KB index only; Terraform default)
or a search service URL. Query = keyword + vector (embedding of the question through the gateway when AI
is on), filtered to approved chunks in the patient's language, semantic ranker when available.
Local: BM25 over chunks of KB_DIR/*.md (approved docs only; `_pending` is never searched).
"""

from __future__ import annotations

import logging
import math
import os
from collections import Counter
from typing import Any

import httpx

from agents.rag.chunking import chunk_markdown, detect_language, title_of, tokenize
from agents.rag.kb import kb_dir

log = logging.getLogger("rabt.rag")
SEARCH_API_VERSION = os.environ.get("AZURE_SEARCH_API_VERSION", "2024-07-01")


def search_configured() -> bool:
    return bool(os.environ.get("AZURE_SEARCH_ENDPOINT", "").strip())


def _local_chunks() -> list[dict[str, Any]]:
    rows = []
    for path in sorted(kb_dir().glob("*.md")):
        text = path.read_text(encoding="utf-8")
        lang = detect_language(text)
        title = title_of(text, path.stem)
        for i, c in enumerate(chunk_markdown(text)):
            rows.append({"id": f"{path.stem}#{i}", "doc_id": path.stem, "title": title, "text": c, "language": lang})
    return rows


def local_search(question: str, *, language: str, k: int = 3) -> list[dict[str, Any]]:
    chunks = [c for c in _local_chunks() if c["language"] == language] or _local_chunks()
    q = tokenize(question)
    if not q or not chunks:
        return []
    docs = [tokenize(c["title"] + " " + c["text"]) for c in chunks]
    avg = sum(len(d) for d in docs) / len(docs)
    df = Counter(t for d in docs for t in set(d))
    n = len(docs)
    out = []
    for c, d in zip(chunks, docs, strict=True):
        tf = Counter(d)
        score = 0.0
        for t in q:
            if t not in tf:
                continue
            idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
            score += idf * tf[t] * 2.2 / (tf[t] + 1.2 * (0.25 + 0.75 * len(d) / avg))
        if score > 0:
            out.append(c | {"score": round(score, 3), "source": "local"})
    out.sort(key=lambda h: h["score"], reverse=True)
    return out[:k]


def azure_search(question: str, *, language: str, k: int = 3, vector: list[float] | None = None) -> list[dict[str, Any]]:
    base = os.environ["AZURE_SEARCH_ENDPOINT"].rstrip("/")
    index = os.environ.get("AZURE_SEARCH_INDEX", "rabt-kb")
    key = os.environ.get("AZURE_SEARCH_API_KEY") or os.environ.get("LLM_API_KEY") or ""
    body: dict[str, Any] = {
        "search": question,
        "top": k,
        "filter": f"approved eq true and language eq '{'ar' if language == 'ar' else 'en'}'",
        "select": "id,doc_id,title,content,language",
    }
    if os.environ.get("AZURE_SEARCH_SEMANTIC_CONFIG"):
        body |= {"queryType": "semantic", "semanticConfiguration": os.environ["AZURE_SEARCH_SEMANTIC_CONFIG"]}
    if vector:
        body["vectorQueries"] = [{"kind": "vector", "vector": vector, "fields": "content_vector", "k": k}]
    try:
        r = httpx.post(
            f"{base}/indexes/{index}/docs/search?api-version={SEARCH_API_VERSION}",
            json=body,
            headers={"api-key": key, "Content-Type": "application/json"},
            timeout=10,
        )
        r.raise_for_status()
        hits = r.json().get("value", [])
    except Exception as e:
        log.warning("azure_search_failed err=%s; falling back to local KB", type(e).__name__)
        return local_search(question, language=language, k=k)
    return [
        {
            "id": h.get("id"),
            "doc_id": h.get("doc_id"),
            "title": h.get("title"),
            "text": h.get("content", ""),
            "language": h.get("language"),
            "score": h.get("@search.rerankerScore") or h.get("@search.score"),
            "source": "azure_search",
        }
        for h in hits
    ]


async def retrieve(question: str, *, language: str = "en", k: int = 3) -> list[dict[str, Any]]:
    if not search_configured():
        return local_search(question, language=language, k=k)
    from agents.common.llm_client import embed

    vec = await embed([question])
    return azure_search(question, language=language, k=k, vector=vec[0] if vec else None)
