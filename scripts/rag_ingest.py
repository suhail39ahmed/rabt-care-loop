#!/usr/bin/env python3
"""Index the approved KB into Azure AI Search (#94).

Sources: `data/kb/*.md` (approved through PR review and shipped in the image), plus, with
`--from-blob`, docs approved in the app and uploaded to the KB blob container (the Container Apps
ingestion job uses this). Never reads `_pending`.

Steps: create/update the index (keyword + vector + semantic config), chunk each doc, skip docs whose
content hash is already indexed, embed new chunks with Azure OpenAI, upload, delete chunks of docs that
no longer exist. Auth: Microsoft Entra ID (DefaultAzureCredential: az login locally, the ingestion
managed identity in Azure). No keys.

  python scripts/rag_ingest.py                    # dry run: print the plan, no Azure calls
  python scripts/rag_ingest.py --apply            # index local data/kb
  python scripts/rag_ingest.py --from-blob --apply

Settings (env or flags): AZURE_SEARCH_SERVICE_ENDPOINT, AZURE_SEARCH_INDEX, AZURE_OPENAI_ENDPOINT,
AZURE_OPENAI_EMBEDDING_DEPLOYMENT, KB_BLOB_CONTAINER_URL.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services"))

from agents.rag.chunking import chunk_markdown, content_hash, detect_language, title_of

SEARCH_API = "2024-07-01"
OPENAI_API = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-10-21")
DIMENSIONS = 1536  # text-embedding-3-small


def index_schema(name: str) -> dict[str, Any]:
    return {
        "name": name,
        "fields": [
            {"name": "id", "type": "Edm.String", "key": True, "filterable": True},
            {"name": "doc_id", "type": "Edm.String", "filterable": True, "facetable": True},
            {"name": "title", "type": "Edm.String", "searchable": True},
            {"name": "content", "type": "Edm.String", "searchable": True},
            {"name": "language", "type": "Edm.String", "filterable": True},
            {"name": "approved", "type": "Edm.Boolean", "filterable": True},
            {"name": "approved_by", "type": "Edm.String", "filterable": True},
            {"name": "doc_hash", "type": "Edm.String", "filterable": True},
            {"name": "chunk", "type": "Edm.Int32", "sortable": True},
            {
                "name": "content_vector",
                "type": "Collection(Edm.Single)",
                "searchable": True,
                "retrievable": False,
                "dimensions": DIMENSIONS,
                "vectorSearchProfile": "rabt-hnsw",
            },
        ],
        "vectorSearch": {
            "algorithms": [{"name": "hnsw", "kind": "hnsw"}],
            "profiles": [{"name": "rabt-hnsw", "algorithm": "hnsw"}],
        },
        "semantic": {
            "configurations": [
                {
                    "name": "rabt-semantic",
                    "prioritizedFields": {
                        "titleField": {"fieldName": "title"},
                        "prioritizedContentFields": [{"fieldName": "content"}],
                    },
                }
            ]
        },
    }


def build_docs(sources: dict[str, str]) -> list[dict[str, Any]]:
    """Chunk documents into index rows (without vectors)."""
    rows = []
    for name, text in sorted(sources.items()):
        doc_id = Path(name).stem
        h = content_hash(text)
        approved_by = "seed"
        if "approved_by:" in text:
            approved_by = text.split("approved_by:", 1)[1].split()[0]
        for i, chunk in enumerate(chunk_markdown(text)):
            rows.append(
                {
                    "id": f"{doc_id}--{i}".replace(".", "_"),
                    "doc_id": doc_id,
                    "title": title_of(text, doc_id),
                    "content": chunk,
                    "language": detect_language(text),
                    "approved": True,
                    "approved_by": approved_by,
                    "doc_hash": h,
                    "chunk": i,
                }
            )
    return rows


def local_sources() -> dict[str, str]:
    kb = ROOT / "data" / "kb"
    return {p.name: p.read_text(encoding="utf-8") for p in sorted(kb.glob("*.md"))}


def _token(scope: str) -> str:
    from azure.identity import DefaultAzureCredential

    return DefaultAzureCredential().get_token(scope).token


def blob_sources(container_url: str) -> dict[str, str]:
    import xml.etree.ElementTree as ET

    h = {"Authorization": f"Bearer {_token('https://storage.azure.com/.default')}", "x-ms-version": "2023-11-03"}
    r = httpx.get(f"{container_url}?restype=container&comp=list", headers=h, timeout=30)
    r.raise_for_status()
    names = [b.findtext("Name") for b in ET.fromstring(r.content).iter("Blob")]
    out = {}
    for n in names:
        if n and n.endswith(".md") and not n.startswith("_"):
            out[n] = httpx.get(f"{container_url}/{n}", headers=h, timeout=30).text
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="call Azure (default is a dry run)")
    ap.add_argument("--dry-run", action="store_true", help="kept for compatibility; dry run is the default")
    ap.add_argument("--from-blob", action="store_true")
    ap.add_argument("--search-endpoint", default=os.environ.get("AZURE_SEARCH_SERVICE_ENDPOINT"))
    ap.add_argument("--index", default=os.environ.get("AZURE_SEARCH_INDEX", "rabt-kb"))
    ap.add_argument("--openai-endpoint", default=os.environ.get("AZURE_OPENAI_ENDPOINT"))
    ap.add_argument("--embedding-deployment", default=os.environ.get("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "embed"))
    ap.add_argument("--blob-container-url", default=os.environ.get("KB_BLOB_CONTAINER_URL"))
    args = ap.parse_args()

    # Docs shipped in the image (approved through PR review) + docs approved in the app (blob); blob wins.
    sources = local_sources()
    if args.from_blob and args.apply:
        sources |= blob_sources(args.blob_container_url.rstrip("/"))
    rows = build_docs(sources)
    plan = {
        "index": args.index,
        "documents": len(sources),
        "chunks": len(rows),
        "languages": sorted({r["language"] for r in rows}),
        "apply": args.apply,
    }
    if not args.apply:
        print(json.dumps(plan | {"sample": rows[:1]}, ensure_ascii=False, indent=2))
        return 0

    search = args.search_endpoint.rstrip("/")
    sh = {"Authorization": f"Bearer {_token('https://search.azure.com/.default')}", "Content-Type": "application/json"}
    r = httpx.put(f"{search}/indexes/{args.index}?api-version={SEARCH_API}", headers=sh,
                  json=index_schema(args.index), timeout=60)
    r.raise_for_status()

    # Which doc versions are already indexed?
    r = httpx.post(f"{search}/indexes/{args.index}/docs/search?api-version={SEARCH_API}", headers=sh,
                   json={"search": "*", "select": "id,doc_id,doc_hash", "top": 1000}, timeout=60)
    r.raise_for_status()
    existing = r.json().get("value", [])
    have = {(d["doc_id"], d["doc_hash"]) for d in existing}
    new_rows = [row for row in rows if (row["doc_id"], row["doc_hash"]) not in have]
    current_ids = {row["id"] for row in rows}
    stale = [d["id"] for d in existing if d["id"] not in current_ids or (d["doc_id"], d["doc_hash"]) not in
             {(row["doc_id"], row["doc_hash"]) for row in rows}]

    if new_rows:
        oh = {"Authorization": f"Bearer {_token('https://cognitiveservices.azure.com/.default')}"}
        url = (f"{args.openai_endpoint.rstrip('/')}/openai/deployments/{args.embedding_deployment}"
               f"/embeddings?api-version={OPENAI_API}")
        for i in range(0, len(new_rows), 16):
            batch = new_rows[i : i + 16]
            e = httpx.post(url, headers=oh, json={"input": [b["content"] for b in batch]}, timeout=60)
            e.raise_for_status()
            for b, d in zip(batch, sorted(e.json()["data"], key=lambda x: x["index"]), strict=True):
                b["content_vector"] = d["embedding"]

    actions = [{"@search.action": "delete", "id": i} for i in stale if i not in {r["id"] for r in new_rows}]
    actions += [{"@search.action": "mergeOrUpload", **row} for row in new_rows]
    if actions:
        r = httpx.post(f"{search}/indexes/{args.index}/docs/index?api-version={SEARCH_API}", headers=sh,
                       json={"value": actions}, timeout=120)
        r.raise_for_status()
    print(json.dumps(plan | {"uploaded": len(new_rows), "deleted": len(actions) - len(new_rows),
                             "unchanged": len(rows) - len(new_rows)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
