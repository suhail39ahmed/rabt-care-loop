# Learn Rabt (in depth)

Curriculum markdown for the care-loop demo. **In-app `/learn` routes were removed from the public web app** (judges use the live board / patient / admin / Judge mode tour). This folder stays the study pack.

## Path

1. **Modules 01–07** → `learn/modules/*.md`
2. **Abbreviations A–Z** → `learn/glossary.md`
3. **What Rabt adds (F1–F12)** → `learn/modules/06-features-deep-dive.md` + `learn/modules/07-shipped-since.md`
4. **Practice game** → `learn/game-data.json` (data for a future UI or offline quiz)
5. **Assessment** (pass ≥ 80%) → `learn/assessment.json`

Also see: [docs/learn-agents.md](../docs/learn-agents.md), [docs/hitl-playbook.md](../docs/hitl-playbook.md), home **Judge mode** tour on the live site.

## Repo layout

| Path | What |
|---|---|
| `learn/modules/*.md` | Concept lessons |
| `learn/modules/features/` | Feature deep-dive index |
| `learn/game-data.json` | Practice questions |
| `learn/assessment.json` | Formal assessment bank |
| `learn/diagrams/*.png` | Workflow · Delegation · HITL |

## Rule

> Deterministic code decides. The LLM explains (only when `AI_ENABLED`). Humans gate the unsafe paths.  
> Timeline **violet / AI** only when an LLM actually ran (`ai_generated`). Templates stay **calculated**.

## Live demo (after stack)

| Surface | URL path |
|---|---|
| Judge tour | `/` → Judge mode |
| HITL board | `/board` |
| Patient | `/patient/{caseId}` |
| KPIs + equity | `/admin` |
| Health / AI flags | `GET /healthz` → `ai_enabled`, `llm`, `llm_provider` |
