# Guardrailed RAG on Azure (#92, #93, #94, #98)

Demo default: `RAG_PROVIDER=off` (keyword FAQ in `services/agents/reassurance`). Optional `mock` retrieves from `data/kb` with citations. Azure path is wired via Terraform.

## Infrastructure (shipped)

| Capability | Module |
|---|---|
| Azure OpenAI chat + embeddings | `infra/terraform/openai.tf` |
| AI Search | `infra/terraform/search.tf` |
| Content Safety | `infra/terraform/content_safety.tf` |
| APIM AI gateway (MI, token limits, metrics) | `infra/terraform/apim.tf` |
| Redis / semantic cache target | `infra/terraform/redis.tf` |
| Budget alert | `infra/terraform/monitoring.tf` |

See `infra/terraform/README.md` for apply steps. Public demo stays RAG-off until keys are set.
