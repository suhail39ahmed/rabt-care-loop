"""KB ingestion pipeline: parse -> filter approved -> chunk -> embed -> idempotent upsert -> delete removed.

Pure and backend-agnostic so the same code runs in three modes:
- offline: a JSON file index + a deterministic hashing embedder (tests, template demo, no Azure);
- Azure push: AI Search REST + embeddings through the APIM AI gateway (or Azure OpenAI with Entra ID);
- dry run: the plan only.

Idempotency: chunk ids are deterministic (`<doc_id>--<n>`) and every row carries the doc's content hash.
A doc whose hash is already indexed is skipped (no embedding cost). Rows of changed, demoted (draft) or
deleted docs are removed. Re-running with the same inputs uploads and deletes nothing.
The index name carries the schema version (`rabt-kb-v2`); a schema change means a new index, so
an existing index is never mutated in an incompatible way.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any, Protocol

import httpx

from agents.rag.chunking import chunk_document, content_hash, parse_doc
from agents.rag.retrieve import DEFAULT_INDEX, INDEX_SCHEMA_VERSION

SEARCH_API = "2024-07-01"
DIMENSIONS = 1536  # text-embedding-3-small
FILTERABLE = ("doc_id", "language", "topic", "audience", "clinical_review_status", "reviewer", "version",
              "last_reviewed", "doc_hash")

__all__ = ["DEFAULT_INDEX", "INDEX_SCHEMA_VERSION", "build_rows", "index_schema", "plan_sync", "sync"]


def index_schema(name: str = DEFAULT_INDEX) -> dict[str, Any]:
    fields: list[dict[str, Any]] = [
        {"name": "id", "type": "Edm.String", "key": True, "filterable": True, "sortable": True},
        {"name": "title", "type": "Edm.String", "searchable": True},
        {"name": "heading", "type": "Edm.String", "searchable": True},
        {"name": "content", "type": "Edm.String", "searchable": True},
        {"name": "approved", "type": "Edm.Boolean", "filterable": True},
        {"name": "source", "type": "Edm.String", "filterable": False},
        {"name": "chunk", "type": "Edm.Int32", "sortable": True},
        {"name": "tokens", "type": "Edm.Int32"},
    ]
    fields += [{"name": f, "type": "Edm.String", "filterable": True, "facetable": f in ("topic", "language")}
               for f in FILTERABLE]
    fields.append({
        "name": "content_vector",
        "type": "Collection(Edm.Single)",
        "searchable": True,
        "retrievable": False,
        "dimensions": DIMENSIONS,
        "vectorSearchProfile": "rabt-hnsw",
    })
    return {
        "name": name,
        "fields": fields,
        "vectorSearch": {
            "algorithms": [{"name": "hnsw", "kind": "hnsw"}],
            "profiles": [{"name": "rabt-hnsw", "algorithm": "hnsw"}],
        },
        "semantic": {
            "configurations": [{
                "name": "rabt-semantic",
                "prioritizedFields": {
                    "titleField": {"fieldName": "title"},
                    "prioritizedContentFields": [{"fieldName": "content"}],
                    "prioritizedKeywordsFields": [{"fieldName": "heading"}],
                },
            }]
        },
    }


def build_rows(sources: dict[str, str], *, max_tokens: int = 320, overlap_tokens: int = 48) -> tuple[list[dict[str, Any]], list[str]]:
    """Index rows (no vectors) for approved docs, plus the ids of docs skipped as not approved."""
    rows: list[dict[str, Any]] = []
    skipped: list[str] = []
    for name, text in sorted(sources.items()):
        stem = Path(name).stem
        doc = parse_doc(text, stem)
        if not doc["approved"]:
            skipped.append(stem)
            continue
        h = content_hash(text)
        for i, c in enumerate(chunk_document(doc["body"], title=doc["title"], max_tokens=max_tokens,
                                             overlap_tokens=overlap_tokens)):
            rows.append({
                "id": re.sub(r"[^A-Za-z0-9_\-=]", "_", f"{stem}--{i}"),
                "doc_id": stem,
                "title": doc["title"],
                "heading": c["heading"],
                "content": c["text"],
                "tokens": c["tokens"],
                "chunk": i,
                "approved": True,
                "doc_hash": h,
                **{k: doc[k] for k in ("language", "topic", "audience", "clinical_review_status", "reviewer",
                                        "version", "last_reviewed", "source")},
            })
    return rows, skipped


def plan_sync(rows: list[dict[str, Any]], existing: Iterable[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    """(rows to upload, ids to delete). Unchanged docs (same doc_id + hash) are left alone."""
    existing = list(existing)
    have = {(d["doc_id"], d["doc_hash"]) for d in existing}
    upload = [r for r in rows if (r["doc_id"], r["doc_hash"]) not in have]
    current = {(r["id"], r["doc_id"], r["doc_hash"]) for r in rows}
    upload_ids = {r["id"] for r in upload}
    delete = sorted(d["id"] for d in existing
                    if (d["id"], d["doc_id"], d["doc_hash"]) not in current and d["id"] not in upload_ids)
    return upload, delete


# --------------------------------------------------------------------------- embedders

class Embedder(Protocol):
    name: str

    def __call__(self, texts: list[str]) -> list[list[float]]: ...


class HashEmbedder:
    """Deterministic bag-of-words hashing vectors (offline only; no semantic quality claims)."""

    name = "offline-hash"

    def __init__(self, dims: int = DIMENSIONS) -> None:
        self.dims = dims

    def __call__(self, texts: list[str]) -> list[list[float]]:
        out = []
        for t in texts:
            v = [0.0] * self.dims
            for tok in re.findall(r"[\w\u0600-\u06FF]+", t.lower()):
                h = int.from_bytes(hashlib.blake2b(tok.encode(), digest_size=8).digest(), "big")
                v[h % self.dims] += 1.0 if (h >> 63) & 1 else -1.0
            n = math.sqrt(sum(x * x for x in v)) or 1.0
            out.append([round(x / n, 6) for x in v])
        return out


class GatewayEmbedder:
    """Embeddings through the APIM AI gateway (same URL shape and `api-key` header as the API)."""

    name = "apim"

    def __init__(self, base_url: str, deployment: str, api_key: str | None = None,
                 token: Callable[[], str] | None = None, api_version: str | None = None) -> None:
        self.base = base_url.rstrip("/")
        self.deployment = deployment
        self.api_key = api_key
        self.token = token
        self.version = api_version or os.environ.get("AZURE_OPENAI_API_VERSION", "2024-10-21")

    def url(self) -> str:
        base = self.base if self.base.endswith("/openai") else f"{self.base}/openai"
        return f"{base}/deployments/{self.deployment}/embeddings?api-version={self.version}"

    def headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json", "x-rabt-task": "kb-ingest"}
        if self.api_key:
            h["api-key"] = self.api_key
        elif self.token:
            h["Authorization"] = f"Bearer {self.token()}"
        return h

    def __call__(self, texts: list[str]) -> list[list[float]]:
        r = httpx.post(self.url(), headers=self.headers(), json={"input": texts}, timeout=60)
        r.raise_for_status()
        return [d["embedding"] for d in sorted(r.json()["data"], key=lambda x: x["index"])]


# --------------------------------------------------------------------------- stores

class Store(Protocol):
    def ensure_index(self, schema: dict[str, Any]) -> None: ...

    def existing(self) -> list[dict[str, Any]]: ...

    def apply(self, upload: list[dict[str, Any]], delete: list[str]) -> None: ...


class LocalIndexStore:
    """A JSON file standing in for an AI Search index (offline mode)."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def _load(self) -> dict[str, Any]:
        if self.path.exists():
            return json.loads(self.path.read_text(encoding="utf-8"))
        return {"schema": None, "docs": {}}

    def _save(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def ensure_index(self, schema: dict[str, Any]) -> None:
        data = self._load()
        if data["schema"] and data["schema"]["name"] != schema["name"]:
            raise ValueError(f"local index holds {data['schema']['name']}, not {schema['name']}")
        data["schema"] = schema
        self._save(data)

    def existing(self) -> list[dict[str, Any]]:
        return [{k: d[k] for k in ("id", "doc_id", "doc_hash")} for d in self._load()["docs"].values()]

    def apply(self, upload: list[dict[str, Any]], delete: list[str]) -> None:
        data = self._load()
        for i in delete:
            data["docs"].pop(i, None)
        for row in upload:
            data["docs"][row["id"]] = row
        self._save(data)

    def rows(self) -> list[dict[str, Any]]:
        return list(self._load()["docs"].values())


class AzureSearchStore:
    def __init__(self, endpoint: str, index: str, token: Callable[[], str]) -> None:
        self.base = endpoint.rstrip("/")
        self.index = index
        self.token = token

    def _h(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token()}", "Content-Type": "application/json"}

    def ensure_index(self, schema: dict[str, Any]) -> None:
        r = httpx.put(f"{self.base}/indexes/{self.index}?api-version={SEARCH_API}", headers=self._h(), json=schema,
                      timeout=60)
        r.raise_for_status()

    def existing(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        skip = 0
        while True:
            r = httpx.post(f"{self.base}/indexes/{self.index}/docs/search?api-version={SEARCH_API}", headers=self._h(),
                           json={"search": "*", "select": "id,doc_id,doc_hash", "top": 1000, "skip": skip,
                                 "orderby": "id"}, timeout=60)
            r.raise_for_status()
            page = r.json().get("value", [])
            out += page
            if len(page) < 1000:
                return out
            skip += len(page)

    def apply(self, upload: list[dict[str, Any]], delete: list[str]) -> None:
        actions = [{"@search.action": "delete", "id": i} for i in delete]
        actions += [{"@search.action": "upload", **row} for row in upload]
        for i in range(0, len(actions), 500):
            r = httpx.post(f"{self.base}/indexes/{self.index}/docs/index?api-version={SEARCH_API}", headers=self._h(),
                           json={"value": actions[i : i + 500]}, timeout=120)
            r.raise_for_status()


# --------------------------------------------------------------------------- sync

def sync(sources: dict[str, str], store: Store, embed: Embedder, *, index: str = DEFAULT_INDEX,
         batch: int = 16) -> dict[str, Any]:
    rows, skipped = build_rows(sources)
    store.ensure_index(index_schema(index))
    upload, delete = plan_sync(rows, store.existing())
    for i in range(0, len(upload), batch):
        part = upload[i : i + batch]
        for row, vec in zip(part, embed([r["content"] for r in part]), strict=True):
            row["content_vector"] = vec
    store.apply(upload, delete)
    langs: dict[str, int] = {}
    for r in {r["doc_id"]: r for r in rows}.values():
        langs[r["language"]] = langs.get(r["language"], 0) + 1
    return {
        "index": index,
        "schema_version": INDEX_SCHEMA_VERSION,
        "embedder": embed.name,
        "documents": len(sources),
        "approved_documents": len({r["doc_id"] for r in rows}),
        "skipped_not_approved": skipped,
        "documents_by_language": dict(sorted(langs.items())),
        "chunks": len(rows),
        "uploaded": len(upload),
        "deleted": len(delete),
        "unchanged": len(rows) - len(upload),
    }
