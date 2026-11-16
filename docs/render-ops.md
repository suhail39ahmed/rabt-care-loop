# Render ops checklist (#35, #49)

Services were created manually; align with `render.yaml`:

| Service | Dashboard | Health check path |
|---|---|---|
| **rabt-api** | https://dashboard.render.com/web/srv-dbt6derbc2fs73d8c3ng | `/healthz` |
| **rabt-web** | https://dashboard.render.com/web/srv-dbt6fcui0phs73er05o0 | `/` |

## One-time Dashboard settings

1. On each service → **Settings → Health Check Path** — set the paths above (Blueprint already declares them; manual services need the field filled).
2. Confirm `RABT_INGEST_SECRET` is set on rabt-api (Environment). Without it, ingest is open.
3. Region note: Oregon today; Frankfurt is closer to Abu Dhabi if recreating.
4. Keep-warm: `.github/workflows/keep-warm.yml` pings both URLs every 10 minutes.

## Auto-deploy (commit trigger)

Both services show `autoDeploy: yes` / trigger `commit`, but GitHub → Render app access must include **rabt-care-loop** or pushes never start a deploy.

1. GitHub → **Settings → Applications → Render** → Repository access → include `suhail39ahmed/rabt-care-loop`.
2. Or on each Render service → **Settings → Build & Deploy** → reconnect the GitHub repo.
3. Verify: merge a trivial docs PR to `main` → Render deploy appears with **trigger = commit** (not `api` / manual).

## Manual deploy (when auto-deploy is stuck)

Dashboard → each service → **Manual Deploy → Deploy latest commit**, or API/MCP `trigger_deploy` for:

- `srv-dbt6derbc2fs73d8c3ng` (rabt-api)
- `srv-dbt6fcui0phs73er05o0` (rabt-web)

Prefer clearing the build cache if the live site still serves old routes.

## Post-deploy smoke (`main` expected)

Run after cold-start (~30–60 s on free tier). Replace nothing — URLs are live.

```bash
# API root (not 404)
curl -sS -o /tmp/rabt-root.json -w "%{http_code}\n" https://rabt-api-9oig.onrender.com/
# expect 200 + JSON with docs/healthz

curl -sS https://rabt-api-9oig.onrender.com/healthz
# expect ok, content_safety, llm / mcp_in_demo_path flags

curl -sS -o /dev/null -w "%{http_code}\n" -X POST \
  -H "X-Rabt-Persona: anyone" \
  "https://rabt-api-9oig.onrender.com/demo/advance?minutes=1"
# expect 403 (unknown persona)

curl -sS -o /dev/null -w "%{http_code}\n" -X POST \
  -H "X-Rabt-Persona: human:gp-aisha" \
  https://rabt-api-9oig.onrender.com/cases/case-nope/attend
# expect 404 (not 500)

curl -sS -o /dev/null -w "%{http_code}\n" \
  https://rabt-api-9oig.onrender.com/cases/case-gc01-fatima
# expect 200

curl -sS -o /dev/null -w "%{http_code}\n" -X POST \
  -H "X-Rabt-Persona: human:coordinator-sara" \
  https://rabt-api-9oig.onrender.com/demo/reset
# expect 200

curl -sS -o /dev/null -w "%{http_code}\n" -X POST \
  https://rabt-api-9oig.onrender.com/cases/ingest
# expect 401 when RABT_INGEST_SECRET is set

# Web
curl -sS -o /dev/null -w "%{http_code}\n" https://rabt-web.onrender.com/
# expect 200

curl -sS -o /dev/null -w "%{http_code}\n" https://rabt-web.onrender.com/learn
# expect 404 on current main (study /learn removed)

curl -sS -o /dev/null -w "%{http_code}\n" https://rabt-web.onrender.com/icon.png
curl -sS -o /dev/null -w "%{http_code}\n" https://rabt-web.onrender.com/og.png
# expect 200
```

Do **not** treat a green smoke on old commit SHAs as success — check the deploy commit matches `origin/main`.
