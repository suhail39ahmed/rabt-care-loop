# Module 7 — What shipped in the latest stack

Study companion for stack work that closed the open issues. Defaults keep the **public demo template-safe**.

## Safety & honesty
| Change | Why it matters | Where |
|---|---|---|
| Timeline `kind=ai` only if LLM ran | Stops overclaiming “AI” on templates | `coordinator._apply`, reassurance `ai_generated: false` |
| `AI_ENABLED` kill switch | One flag turns off every AI network path | `settings.py`, `llm_client.py`, `/healthz` |
| Provider-agnostic LLM | Render can use API key + OpenAI-compatible URL | `LLM_PROVIDER`, `LLM_BASE_URL`, `LLM_API_KEY` |
| Injection deny-list | Blocks “ignore instructions…” on reassure | `agents/common/injection.py` |
| UAE PII scrub | Emirates ID + Arabic name placeholders | `agents/common/pii.py` |

## HITL completeness
| Change | Route / UI |
|---|---|
| Resolve queue | `POST /queue/{qid}/resolve` + board button |
| Resume consent | `POST /cases/{id}/consent/resume` |
| Callback done | `POST /cases/{id}/callback/done` |
| Mark unreachable / resolve data query | Board buttons |
| Patient persona | Patient page sets `patient:fatima` |
| Accept blocked on OnHoldConsent | HTTP 409 |

## Critical + concern
| Change | Detail |
|---|---|
| Expert call | Approved script in evidence; outcomes required before handle |
| Concern share | Crisis lexicon first; deterministic intent; approved snippet |
| Intent module | `services/agents/intent/classify.py` |

## Insurance Navigator
| Change | Detail |
|---|---|
| Demo Health Insurance | Agent card + eligibility/preauth/cost |
| Book guard | Blocks when `preauth_status=pending` or denied |
| Board Coverage card | Shows allowlisted structured fields only |

## Judge / admin surfaces
| Change | Detail |
|---|---|
| Judge mode tour | 6 steps on home `/` |
| KPIs | time-to-owner, verified closure, leak funnel |
| Equity | small-cell suppression N&lt;10 |
| Why? | provenance rule ids + navigator scores |
| Evidence pack | FHIR Bundle download |
| SMS preview | Simulated phone frame; no values |

## Multilingual / accessibility
| Change | Detail |
|---|---|
| i18n snippets | `data/templates/i18n/patient_snippets.yaml` (hi/ur/ml/fil/bn) |
| Listen | Browser `speechSynthesis` on patient message |
| Live translate stub | Board panel — labelled simulated |

## Docs & ops
| Doc | Topic |
|---|---|
| `docs/pilot-plan.md` | 12-week pilot + cost |
| `docs/threat-model.md` | STRIDE → code |
| `scripts/load_test.py` | Local ingest load (not live demo) |
| `docs/deck-outline.md` | Submission deck alignment |

## Try it
1. Home → Judge mode steps 1–6  
2. CRITICAL case → log call outcome → Handle escalation  
3. Fatima → Share concern  
4. `/admin` → funnel + equity  
5. `GET /healthz` → confirm `ai_enabled: false` on demo  
