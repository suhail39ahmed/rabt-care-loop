# Grounded RAG, intent detection and the clinician-approved learning loop

Patients can ask questions on their case page (`POST /cases/{id}/reassure`). Answers only come from the **approved** knowledge base. Nothing in `_pending` is ever searched.

## Answer pipeline (`services/agents/rag/answer.py`)

1. **Crisis language** (deterministic lexicon): urgent-help text with 998 / 999, a human hand-off and a `HumanCallback` when the patient was notified. Personal diagnosis or medication questions get a clinician callback instead of a KB answer.
2. **Injection deny-list**: refuse and hand off. Prompt Shields also runs inside the LLM client.
3. **App cache** (`agents/common/semantic_cache.py`): scoped by language and KB index version. The question is PII-scrubbed before it is used as a key. Matching is cosine ≥ 0.92 on embeddings, or token overlap ≥ 0.85 without them.
4. **Retrieve** (`agents/rag/retrieve.py`):
   - **Azure:** AI Search through the APIM `/search` API (read-only, KB index only). Hybrid keyword + vector query (question embedded through the gateway), filtered by `approved eq true and language eq '<en|ar>'` (plus optional topic / audience), with the semantic ranker (`rabt-semantic`). Falls back to local search if the call fails.
   - **Local:** BM25 over chunks of approved `data/kb/*.md` docs in the patient's language (light Arabic normalisation).
5. **No hit**: "ask your care team", plus a `kb_gap` item in the coordinator queue (the question is PII-scrubbed).
6. **AI on**: the strong model answers from the numbered sources (prompt `rag_answer`), through the APIM semantic cache (scope = language + index version). The answer is kept only if:
   - it cites a source that exists;
   - it uses no number that is not in the sources;
   - it passes the no-diagnosis lexicon and Content Safety.

   Otherwise, or with AI off, the best approved paragraph is returned (`rag_extractive`).

## Intent / concern detection (`services/agents/intent/classify.py`)

- Rules first (cost, fear, time, transport, language, distrust).
- Crisis detection is always deterministic.
- With AI on, only messages the rules mark as `other` go to the small model (prompt `classify_concern`), and its reply must be one of the labels.
- The patient gets an approved snippet and the coordinator gets a queue item.

## Learning loop (clinician-approved)

```
patient question with no approved answer ─► kb_gap in the coordinator queue
coordinator writes a draft   POST /kb/suggestions          (PII-scrubbed, stored in data/kb/_pending)
physician/supervisor review  POST /kb/pending/{id}/approve  (or /reject with a reason)
                             └─► doc written with an approved_by stamp, index version bumped (cached answers invalidated)
                             └─► Azure: uploaded to the KB blob container (app identity, container-scoped role)
ingestion job (hourly / on deploy / on demand) ─► AI Search index
```

- `GET /kb` lists the approved docs and the current index version. `GET /kb/pending` lists drafts.
- Coordinators can draft but cannot approve; patients can do neither.
- CLI equivalent: `python scripts/kb_approve.py list|approve|reject`.
- Docs merged into `data/kb/` through a PR are approved by PR review and ship in the image.

## Ingestion (`scripts/rag_ingest.py`)

The full pipeline (front matter, chunking, idempotency, offline mode, evaluation) is described in [rag.md](rag.md). In short:

- Creates or updates the versioned index `rabt-kb-v2`:
  - keyword fields;
  - a `content_vector` field (1536 dimensions, HNSW);
  - the `rabt-semantic` configuration;
  - metadata filters (`language`, `topic`, `audience`, `clinical_review_status`, `approved`, `doc_hash`).
- Indexes approved docs only.
- Re-embeds only docs whose hash changed. Deletes the chunks of removed, changed or demoted docs.
- Embeddings go through the APIM gateway (`LLM_BASE_URL`, subscription key from the `llm-api-key` secret), with direct Azure OpenAI over Entra ID as the fallback. Search writes use Entra ID.

```bash
python scripts/rag_ingest.py                     # dry run: plan only, no Azure calls
python scripts/rag_ingest.py --offline           # local JSON index, no Azure
python scripts/rag_ingest.py --apply             # from your machine (az login; needs your IP in deployer_ip_allowlist when private)
az containerapp job start -n caj-rabt-ingest-pilot -g rg-rabt-pilot-sea   # in Azure (ingestion managed identity)
```

Terraform creates the job `caj-rabt-ingest-pilot` (hourly, `kb_ingest_cron`) with the ingestion identity:
- Blob read on the KB storage.
- Search Index Data Contributor.
- OpenAI User.
- AcrPull.

The deploy workflow updates its image and starts it after every deploy.
