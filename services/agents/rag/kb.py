"""Approved knowledge base + the clinician-approved learning loop (#96).

KB docs live in KB_DIR (default data/kb/*.md) with a YAML front matter (see agents.rag.chunking); only
`clinical_review_status: approved` docs are retrievable. Suggestions (written by coordinators, or opened
automatically when a patient question finds no approved answer) wait in KB_DIR/_pending as markdown
with a small YAML header. Only a physician or supervisor can approve; approval writes the doc with
front matter (`clinical_review_status: approved`, `reviewer`, `last_reviewed`), bumps the index version (which invalidates cached answers) and, in Azure, uploads
it to the KB blob container where the ingestion job indexes it into AI Search.
"""

from __future__ import annotations

import logging
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import yaml

from agents.rag.chunking import DEMO_SOURCE, content_hash, detect_language, parse_doc, split_front_matter

log = logging.getLogger("rabt.kb")


def kb_dir() -> Path:
    return Path(os.environ.get("KB_DIR") or Path(__file__).resolve().parents[3] / "data" / "kb")


def pending_dir() -> Path:
    d = kb_dir() / "_pending"
    d.mkdir(parents=True, exist_ok=True)
    return d


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s[:60] or f"doc-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"


def list_docs(*, include_drafts: bool = True) -> list[dict[str, Any]]:
    out = []
    for path in sorted(kb_dir().glob("*.md")):
        text = path.read_text(encoding="utf-8")
        doc = parse_doc(text, path.stem)
        if not include_drafts and not doc["approved"]:
            continue
        out.append(
            {k: v for k, v in doc.items() if k != "body"}
            | {"id": path.stem, "approved_by": doc["reviewer"] if doc["approved"] else None,
               "hash": content_hash(text), "text": text}
        )
    return out


def index_version() -> str:
    return content_hash("|".join(f"{d['id']}:{d['hash']}" for d in list_docs()))


def _split_front(text: str) -> tuple[dict[str, Any], str]:
    return split_front_matter(text)


def suggest(*, title: str, content: str, language: str | None, suggested_by: str, reason: str = "",
            source_case: str | None = None) -> dict[str, Any]:
    sid = slugify(title)
    meta = {
        "id": sid,
        "title": title.strip()[:120],
        "language": language or detect_language(content),
        "suggested_by": suggested_by,
        "reason": reason[:300],
        "source_case": source_case,
        "created": datetime.now(UTC).isoformat(timespec="seconds"),
        "status": "pending",
    }
    body = content.strip()
    if not body.startswith("#"):
        body = f"# {meta['title']}\n\n{body}"
    (pending_dir() / f"{sid}.md").write_text(
        "---\n" + yaml.safe_dump(meta, allow_unicode=True, sort_keys=False) + "---\n" + body + "\n", encoding="utf-8"
    )
    return meta | {"content": body}


def list_pending() -> list[dict[str, Any]]:
    rows = []
    for path in sorted(pending_dir().glob("*.md")):
        meta, body = _split_front(path.read_text(encoding="utf-8"))
        rows.append(meta | {"id": meta.get("id") or path.stem, "content": body.strip()})
    return rows


def approve(sid: str, reviewer: str) -> dict[str, Any]:
    src = pending_dir() / f"{slugify(sid)}.md"
    if not src.exists():
        raise FileNotFoundError(sid)
    meta, body = _split_front(src.read_text(encoding="utf-8"))
    now = datetime.now(UTC)
    stamp = now.strftime("%Y-%m-%dT%H:%MZ")
    front = {
        "id": src.stem,
        "title": meta.get("title") or src.stem,
        "language": meta.get("language") or detect_language(body),
        "topic": meta.get("topic") or "general",
        "audience": "patient",
        "clinical_review_status": "approved",
        "reviewer": reviewer,
        "version": 1,
        "last_reviewed": now.date().isoformat(),
        "source": DEMO_SOURCE,
        "suggested_by": meta.get("suggested_by", "n/a"),
        "approved_at": stamp,
    }
    text = "---\n" + yaml.safe_dump(front, allow_unicode=True, sort_keys=False) + "---\n" + body.strip() + "\n"
    dst = kb_dir() / f"{src.stem}.md"
    dst.write_text(text, encoding="utf-8")
    src.unlink()
    published = publish_blob(dst.name, text)
    from agents.common import semantic_cache

    semantic_cache.clear()
    return {"id": dst.stem, "approved_by": reviewer, "at": stamp, "published_to_blob": published,
            "index_version": index_version()}


def reject(sid: str, reviewer: str, reason: str) -> dict[str, Any]:
    src = pending_dir() / f"{slugify(sid)}.md"
    if not src.exists():
        raise FileNotFoundError(sid)
    src.unlink()
    return {"id": sid, "rejected_by": reviewer, "reason": reason[:300]}


def publish_blob(name: str, text: str) -> bool:
    """Upload an approved doc to KB_BLOB_CONTAINER_URL with the app's managed identity (Azure only)."""
    container = os.environ.get("KB_BLOB_CONTAINER_URL", "").rstrip("/")
    if not container:
        return False
    try:
        from azure.identity import DefaultAzureCredential

        token = DefaultAzureCredential().get_token("https://storage.azure.com/.default").token
        r = httpx.put(
            f"{container}/{name}",
            content=text.encode("utf-8"),
            headers={
                "Authorization": f"Bearer {token}",
                "x-ms-version": "2023-11-03",
                "x-ms-blob-type": "BlockBlob",
                "Content-Type": "text/markdown; charset=utf-8",
                "x-ms-meta-approved": "true",
            },
            timeout=15,
        )
        r.raise_for_status()
        return True
    except Exception as e:
        log.warning("kb_publish_failed err=%s", type(e).__name__)
        return False
