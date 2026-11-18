"""Document safety gate for uploads (reimbursement documents, lab reports) and KB ingestion.

Nothing from a file reaches a model, the search index or a coordinator until it passes, in order:
  1. Type by magic bytes (PDF, PNG, JPEG), never by extension; a mismatched extension is flagged.
  2. Size (MAX_BYTES) and page (MAX_PAGES) limits.
  3. PDF structure (pikepdf): encrypted / password PDFs are rejected; JavaScript, launch actions, embedded
     files and auto-run actions quarantine the file; forms and external links are stripped and flagged.
  4. Malware scan hook: EICAR test signature always; ClamAV (clamd over TCP) when CLAMAV_HOST is set. In Azure
     the upload container can also use Defender for Storage malware scanning (Terraform
     `enable_storage_malware_scan`, off by default because it is billed per GB scanned).
  5. Text extraction (pypdf) including document metadata, plus hidden-text heuristics: white text, near-zero
     font sizes, text in metadata.
  6. PII scrub (regex; Azure AI Language when enabled) and prompt-injection checks on the text and metadata:
     deny-list always, Prompt Shields `documents` when configured (fail closed).
Failures go to quarantine (never indexed, never sent to a model) with an audit event and a board flag.
KB files additionally need clinician approval before indexing; that stays in the KB pipeline.
"""

from __future__ import annotations

import hashlib
import io
import os
import re
import socket
from dataclasses import dataclass, field
from typing import Any

MAX_BYTES = int(os.environ.get("DOC_MAX_BYTES", str(10 * 1024 * 1024)))
MAX_PAGES = int(os.environ.get("DOC_MAX_PAGES", "20"))
EICAR = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"

MAGIC = {b"%PDF-": "application/pdf", b"\x89PNG\r\n\x1a\n": "image/png", b"\xff\xd8\xff": "image/jpeg"}
EXT = {"application/pdf": (".pdf",), "image/png": (".png",), "image/jpeg": (".jpg", ".jpeg")}
QUARANTINE_FLAGS = {"javascript", "launch_action", "embedded_files", "auto_action", "encrypted", "malware",
                    "injection", "hidden_text_injection", "unsupported_type", "too_large", "too_many_pages",
                    "unreadable"}


@dataclass
class Verdict:
    status: str = "accepted"  # accepted | quarantined
    mime: str | None = None
    sha256: str = ""
    pages: int = 0
    flags: list[str] = field(default_factory=list)
    stripped: list[str] = field(default_factory=list)
    text: str = ""
    pii_redactions: int = 0
    scanner: str = "eicar-signature"

    def flag(self, name: str) -> None:
        if name not in self.flags:
            self.flags.append(name)
        if name in QUARANTINE_FLAGS:
            self.status = "quarantined"

    def public(self) -> dict[str, Any]:
        """What the ledger, board and patient see: no document text."""
        return {"status": self.status, "mime": self.mime, "sha256": self.sha256[:16], "pages": self.pages,
                "flags": self.flags, "stripped": self.stripped, "pii_redactions": self.pii_redactions,
                "scanner": self.scanner}


def sniff(data: bytes) -> str | None:
    for magic, mime in MAGIC.items():
        if data.startswith(magic):
            return mime
    # PDFs may have up to 1 KB of junk before the header; treat that as suspicious but still a PDF.
    return "application/pdf" if b"%PDF-" in data[:1024] else None


def malware_scan(data: bytes, v: Verdict) -> None:
    if EICAR in data:
        v.flag("malware")
        return
    host = os.environ.get("CLAMAV_HOST")
    if not host:
        return
    v.scanner = "clamav"
    try:
        with socket.create_connection((host, int(os.environ.get("CLAMAV_PORT", "3310"))), timeout=10) as s:
            s.sendall(b"zINSTREAM\0")
            for i in range(0, len(data), 8192):
                chunk = data[i:i + 8192]
                s.sendall(len(chunk).to_bytes(4, "big") + chunk)
            s.sendall(b"\0\0\0\0")
            reply = s.recv(4096)
        if b"FOUND" in reply:
            v.flag("malware")
    except OSError:
        v.flag("malware_scan_unavailable")
        v.status = "quarantined"  # fail closed


_WHITE = re.compile(rb"(?:^|\s)(?:1(?:\.0+)?\s+1(?:\.0+)?\s+1(?:\.0+)?\s+rg|1(?:\.0+)?\s+g)\b")
_TINY = re.compile(rb"/\w+\s+(0?\.\d+|[01](?:\.\d+)?)\s+Tf\b")
_TEXT_OP = re.compile(rb"\((?:[^()\\]|\\.)*\)\s*Tj|\[[^\]]*\]\s*TJ")


def _inspect_pdf(data: bytes, v: Verdict) -> bytes:
    import pikepdf

    try:
        pdf = pikepdf.open(io.BytesIO(data))
    except pikepdf.PasswordError:
        v.flag("encrypted")
        return data
    except Exception:
        v.flag("unreadable")
        return data
    with pdf:
        if pdf.is_encrypted:
            v.flag("encrypted")
        v.pages = len(pdf.pages)
        if v.pages > MAX_PAGES:
            v.flag("too_many_pages")
        root = pdf.Root
        names = root.get("/Names")
        if root.get("/OpenAction") is not None:
            action = root.get("/OpenAction")
            kind = str(action.get("/S")) if isinstance(action, pikepdf.Dictionary) else ""
            v.flag("javascript" if kind == "/JavaScript" else "launch_action" if kind == "/Launch" else "auto_action")
            del root["/OpenAction"]
        if root.get("/AA") is not None:
            v.flag("auto_action")
            del root["/AA"]
        if isinstance(names, pikepdf.Dictionary):
            if names.get("/JavaScript") is not None:
                v.flag("javascript")
                del names["/JavaScript"]
            if names.get("/EmbeddedFiles") is not None:
                v.flag("embedded_files")
                del names["/EmbeddedFiles"]
        if root.get("/AcroForm") is not None:
            v.flag("form")
            v.stripped.append("form")
            del root["/AcroForm"]
        hidden = False
        for page in pdf.pages:
            for annot in list(page.get("/Annots") or []):
                a = annot.get("/A")
                if isinstance(a, pikepdf.Dictionary):
                    s = str(a.get("/S"))
                    if s == "/JavaScript":
                        v.flag("javascript")
                    elif s == "/Launch":
                        v.flag("launch_action")
                    elif s == "/URI":
                        v.flag("external_link")
                        if "external_link" not in v.stripped:
                            v.stripped.append("external_link")
            if page.get("/Annots") is not None:
                del page["/Annots"]
            if page.get("/AA") is not None:
                v.flag("auto_action")
                del page["/AA"]
            contents = page.get("/Contents")
            if isinstance(contents, pikepdf.Array):
                raw = b" ".join(c.read_bytes() for c in contents)
            elif contents is not None:
                raw = contents.read_bytes()
            else:
                raw = b""
            if _TEXT_OP.search(raw) and (_WHITE.search(raw) or _TINY.search(raw)):
                hidden = True
        if hidden:
            v.flag("hidden_text")
        out = io.BytesIO()
        pdf.save(out)
        return out.getvalue()


def _extract_text(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    parts = [(p.extract_text() or "") for p in reader.pages[:MAX_PAGES]]
    meta = reader.metadata or {}
    parts += [str(meta.get(k) or "") for k in ("/Title", "/Subject", "/Keywords", "/Author")]
    return "\n".join(x for x in parts if x).strip()


def check(data: bytes, filename: str = "", *, purpose: str = "claim") -> tuple[Verdict, bytes]:
    """Run the gate. Returns the verdict and the sanitized bytes (active content stripped)."""
    v = Verdict(sha256=hashlib.sha256(data).hexdigest())
    if len(data) > MAX_BYTES:
        v.flag("too_large")
        return v, b""
    v.mime = sniff(data)
    if v.mime is None:
        v.flag("unsupported_type")
        return v, b""
    ext = os.path.splitext(filename.lower())[1]
    if ext and ext not in EXT[v.mime]:
        v.flag("extension_mismatch")
    malware_scan(data, v)
    clean = data
    if v.mime == "application/pdf" and v.status != "quarantined":
        clean = _inspect_pdf(data, v)
        if v.status != "quarantined":
            try:
                text = _extract_text(clean)
            except Exception:
                v.flag("unreadable")
                text = ""
            _text_checks(text, v)
    return v, clean if v.status == "accepted" else b""


def _text_checks(text: str, v: Verdict) -> None:
    from agents.common.injection import deny_listed
    from agents.common.pii import scrub

    scrubbed = scrub(text)
    v.pii_redactions = sum(scrubbed.counts.values()) if scrubbed.counts else 0
    v.text = scrubbed.text[:20000]
    if deny_listed(text):
        v.flag("hidden_text_injection" if "hidden_text" in v.flags else "injection")
        return
    from agents.common import content_safety
    from agents.common.llm_client import ai_enabled

    if text and ai_enabled() and content_safety.configured():
        verdict = content_safety.shield_prompt("Summarise the attached document.", [v.text[:9000]])
        if verdict is None or verdict:
            v.flag("injection")
