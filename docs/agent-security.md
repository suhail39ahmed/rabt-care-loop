# Agent security hardening (#106)

Mapped to OWASP LLM / Agentic risks (demo controls):

| Risk | Control in repo |
|---|---|
| Prompt injection | `agents/common/injection.py` deny-list + optional Prompt Shields hook |
| Excessive agency | `TOOL_SCOPES` / `MAX_STEPS` in coordinator |
| Insecure plugin | MCP tools not on demo path (`mcp_in_demo_path: false`) |
| Untrusted agent data | Insurer allowlist in `app/insurer.py` |
| Identity | `X-Rabt-Persona` + A2A agent card identity |
| Budget | `llm_client` max_tokens + kill switch `AI_ENABLED` |
| Audit | Ledger timeline + provenance |

Red-team stubs: `tests/rag/test_injection.py`.
