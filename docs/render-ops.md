# Render ops checklist (#35)

Services were created manually; align with `render.yaml`:

1. **rabt-api** health check path: `/healthz`
2. **rabt-web** health check path: `/`
3. Confirm `RABT_INGEST_SECRET` is set on rabt-api (Environment). Without it, ingest is open.
4. Verify: `curl -X POST https://rabt-api-9oig.onrender.com/cases/ingest` without secret → **401**
5. Verify: `curl https://rabt-api-9oig.onrender.com/` → **200** JSON with docs/healthz links
6. Region note: Oregon today; Frankfurt is closer to Abu Dhabi if recreating.
7. Keep-warm: `.github/workflows/keep-warm.yml` pings both URLs every 10 minutes.
