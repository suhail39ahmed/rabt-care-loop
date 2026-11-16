# AI evaluation & monitoring schema (#103)

Metrics (emit when `AI_ENABLED=true`):

- `rabt_ai_requests_total{task,model,provider,status}`
- `rabt_ai_latency_ms{task,model}`
- `rabt_ai_tokens{task,direction}`
- `rabt_ai_groundedness_score` (eval job)
- `rabt_ai_refusal_accuracy` (eval job)

Alerts (pilot): latency p95 > 5s; 5xx rate > 2%; Content Safety block spike.
Dashboard: Application Insights / Grafana using APIM + app logs. Demo does not host a live dashboard.
