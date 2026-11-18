#!/usr/bin/env python3
"""Index the approved KB into a versioned Azure AI Search index, or into a local offline index.

Pipeline (services/agents/rag/pipeline.py): parse front matter -> keep `clinical_review_status: approved`
-> heading-aware token chunks with overlap -> embeddings -> idempotent upsert -> delete rows of removed,
changed or demoted docs. Never reads `_pending`.

  python scripts/rag_ingest.py                         # dry run: plan only, no network
  python scripts/rag_ingest.py --offline               # local JSON index + hashing embedder, no Azure
  python scripts/rag_ingest.py --apply                 # Azure (az login or managed identity)
  python scripts/rag_ingest.py --from-blob --apply     # plus docs approved in the app (ingestion job)

Embeddings go through the APIM AI gateway when LLM_BASE_URL is set (subscription key LLM_API_KEY, or an
Entra token for APIM_TOKEN_SCOPE), otherwise straight to AZURE_OPENAI_ENDPOINT with Entra ID.
Settings: AZURE_SEARCH_SERVICE_ENDPOINT, AZURE_SEARCH_INDEX (default rabt-kb-v2), LLM_BASE_URL,
AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_EMBEDDING_DEPLOYMENT, KB_BLOB_CONTAINER_URL.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services"))

from agents.rag import pipeline
from agents.rag.pipeline import build_rows, index_schema  # noqa: F401  (re-exported for tests)

OFFLINE_INDEX = ROOT / ".kb-index"


def local_sources(kb: Path | None = None) -> dict[str, str]:
    kb = kb or Path(os.environ.get("KB_DIR") or ROOT / "data" / "kb")
    out = {p.name: p.read_text(encoding="utf-8") for p in sorted(kb.glob("*.md"))}
    for p in sorted(kb.glob("*.pdf")):  # PDFs pass the document safety gate and land as pending
        md = pipeline.pdf_source(p.name, p.read_bytes())
        if md:
            out[p.stem + ".md"] = md
    return out


def build_docs(sources: dict[str, str]) -> list[dict]:
    """Approved index rows without vectors (kept for older callers)."""
    return build_rows(sources)[0]


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
        elif n and n.lower().endswith(".pdf") and not n.startswith("_"):
            md = pipeline.pdf_source(n, httpx.get(f"{container_url}/{n}", headers=h, timeout=60).content)
            if md:
                out[n.rsplit(".", 1)[0] + ".md"] = md
    return out


def azure_embedder(args: argparse.Namespace) -> pipeline.Embedder:
    if args.embed_via == "apim":
        key = os.environ.get("LLM_API_KEY")
        scope = os.environ.get("APIM_TOKEN_SCOPE")
        return pipeline.GatewayEmbedder(args.gateway, args.embedding_deployment, api_key=key,
                                        token=(lambda: _token(scope)) if scope and not key else None)
    emb = pipeline.GatewayEmbedder(args.openai_endpoint, args.embedding_deployment,
                                   token=lambda: _token("https://cognitiveservices.azure.com/.default"))
    emb.name = "azure-openai"
    return emb


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="index into Azure AI Search")
    mode.add_argument("--offline", action="store_true", help="index into a local JSON file (no Azure)")
    ap.add_argument("--dry-run", action="store_true", help="kept for compatibility; dry run is the default")
    ap.add_argument("--from-blob", action="store_true")
    ap.add_argument("--kb-dir", type=Path, default=None)
    ap.add_argument("--offline-index", type=Path, default=None)
    ap.add_argument("--search-endpoint", default=os.environ.get("AZURE_SEARCH_SERVICE_ENDPOINT"))
    ap.add_argument("--index", default=os.environ.get("AZURE_SEARCH_INDEX") or pipeline.DEFAULT_INDEX)
    ap.add_argument("--gateway", default=os.environ.get("LLM_BASE_URL"))
    ap.add_argument("--openai-endpoint", default=os.environ.get("AZURE_OPENAI_ENDPOINT"))
    ap.add_argument("--embedding-deployment", default=os.environ.get("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "embed"))
    ap.add_argument("--embed-via", choices=["apim", "direct"], default=None,
                    help="default: apim when LLM_BASE_URL is set, else direct")
    ap.add_argument("--blob-container-url", default=os.environ.get("KB_BLOB_CONTAINER_URL"))
    args = ap.parse_args(argv)
    args.embed_via = args.embed_via or ("apim" if args.gateway else "direct")

    sources = local_sources(args.kb_dir)
    if args.from_blob and args.apply:
        sources |= blob_sources(args.blob_container_url.rstrip("/"))  # docs approved in the app win

    if args.offline:
        path = args.offline_index or OFFLINE_INDEX / f"{args.index}.json"
        report = pipeline.sync(sources, pipeline.LocalIndexStore(path), pipeline.HashEmbedder(), index=args.index)
        print(json.dumps(report | {"offline_index": str(path)}, ensure_ascii=False, indent=2))
        return 0

    if not args.apply:
        rows, skipped = build_rows(sources)
        print(json.dumps({"index": args.index, "documents": len(sources), "approved_documents":
                          len({r["doc_id"] for r in rows}), "skipped_not_approved": skipped, "chunks": len(rows),
                          "embed_via": args.embed_via, "apply": False, "sample": rows[:1]}, ensure_ascii=False,
                         indent=2))
        return 0

    store = pipeline.AzureSearchStore(args.search_endpoint, args.index,
                                      lambda: _token("https://search.azure.com/.default"))
    report = pipeline.sync(sources, store, azure_embedder(args), index=args.index)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
