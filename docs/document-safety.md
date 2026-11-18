# Document safety

Every file a patient uploads (reimbursement receipts, lab reports) and every file that lands in the knowledge-base container goes through one gate, `services/agents/docsafety/pipeline.py`, **before** any model, index, insurer or coordinator sees its content.

| # | Check | How | Failure |
|---|---|---|---|
| 1 | File type | Magic bytes (`%PDF-`, PNG, JPEG), never the extension. A mismatched extension is flagged | Unknown type → quarantine |
| 2 | Size and pages | `DOC_MAX_BYTES` (10 MB), `DOC_MAX_PAGES` (20) | Quarantine |
| 3 | PDF structure (pikepdf) | Encrypted / password PDFs rejected. JavaScript, launch actions, embedded files and auto-run actions quarantine the file. Forms and external links are **stripped** and flagged | Quarantine, or sanitized copy |
| 4 | Malware | EICAR signature always. ClamAV (`clamd` INSTREAM) when `CLAMAV_HOST` is set. In Azure, Defender for Storage malware scanning on upload can be switched on with Terraform `enable_storage_malware_scan` (off by default: billed per GB scanned) | Quarantine; scanner unavailable → quarantine (fail closed) |
| 5 | Text + hidden text | pypdf text plus metadata (Title, Subject, Keywords, Author). Heuristics for white text and near-zero font sizes | Flag `hidden_text` |
| 6 | PII + injection | Regex PII scrub (Azure AI Language when enabled) on the extracted text. Deny-list, then Prompt Shields `documents` when configured (fail closed) | Quarantine (`injection` / `hidden_text_injection`) |

**Which malware scanner?** The pilot runs the in-app gate (EICAR + optional ClamAV sidecar). Defender for Storage is wired in Terraform but disabled to keep the pilot at a fixed cost; turn it on for production.

**Quarantine.** A rejected upload is never stored as usable content: the case gets a `documents[]` record (name, sha256 prefix, flags; never the text), the ledger gets a "Document quarantined" audit event, and the coordinator board gets a `document_quarantine` queue item. Storage has `uploads` and `quarantine` containers for blob-based flows.

**Knowledge base.** KB markdown that contains planted instructions is quarantined instead of indexed (`build_rows`). A PDF dropped into the KB container passes the gate and becomes a **pending** document: it is never indexed until a clinician approves it (approved-only retrieval).

**Patient UI.** Each upload shows "Document checked" (with what was stripped) or "Held for review — a coordinator will contact you".

Tests: `services/orchestrator/tests/test_doc_safety.py` builds malicious PDFs in memory (JavaScript open action, launch action, embedded executable, password-protected, white-text and tiny-font injection, metadata injection, fake extension, oversized, too many pages, EICAR).
