# Deployment Guide

This app has two deploy targets:

1. **Cloudflare Pages** (current pilot) — static `app/` + Pages Functions under `functions/api/`
2. **Agentrix / container** — single Docker image: nginx (UI) + Node relay (`server/`) for LLM extraction

---

## Agentrix (container)

### What the image runs

- **One Node process** on **`$PORT` (default 8080)** — required by Knative/Agentrix
  - Static UI from `/app/public` (`app/` in the repo)
  - `/api/extract` and `/api/qc-summary` (Entra → Bayer AI Gateway)
  - `/health`, `/api/features`, and a stub `/mcp` that points browsers to `/`
- **Not in Phase 1:** background jobs (`/api/jobs*`, queue worker). The UI hides those controls when `GET /api/features` reports `backgroundJobs: false`.

> Do not run a separate nginx on 8080: Knative injects `PORT=8080`, and two listeners
> collide so `GET /` returns the API 404 JSON instead of the UI.

### Required secrets / env vars

Set these in Agentrix (or your orchestrator) before deploy:

| Variable | Required | Notes |
|----------|----------|-------|
| `AZURE_CLIENT_SECRET` | Yes* | Entra client secret for "Use Summary Table Extractor" |
| `TFY_API_TOKEN` | *or this* | VA fallback if Entra secret is unset |
| `PILOT_GATE_SECRET` | Yes | Must match `PILOT_GATE_HEADER_VALUE` in `app/index.html` (`ust-pilot-2026`) |

Optional (defaults match `wrangler.toml`):

| Variable | Default |
|----------|---------|
| `AZURE_TENANT_ID` | `fcb2b37b-5da0-466b-9b83-0014b67a7c78` |
| `AZURE_CLIENT_ID` | `5d0b410a-0b42-4427-8bd5-289c1ac0abce` |
| `AZURE_SCOPE` | `https://bayer.com/ai-gateway-prod-idp/.default` |
| `TFY_BASE_URL` | `https://global.ai-gateway.int.bayer.ai/api/llm` |
| `RATE_LIMIT_PER_MINUTE` | `20` |
| `DAILY_BUDGET_USD` | `100` |
| `KILL_SWITCH_ENABLED` | unset / `false` |
| `KILL_SWITCH_REASON` | shown when kill switch is on |

The container must reach `login.microsoftonline.com` and the AI Gateway host from the cluster network (VPN/egress as required by Bayer).

### Deploy

1. Ensure `Dockerfile`, `server/`, `docker/`, and `app/` are on the branch Agentrix clones.
2. Configure the secrets above in Agentrix.
3. Redeploy. Health check: `GET /health` → `{"ok":true,"runtime":"agentrix"}`.
4. Open the app URL → check **Extract with AI** → **Run Extraction**.

### Local smoke test (optional)

```bash
export AZURE_CLIENT_SECRET="..."
export PILOT_GATE_SECRET="ust-pilot-2026"
docker build -t use-summary-table:local .
docker run --rm -p 8080:8080 \
  -e AZURE_CLIENT_SECRET \
  -e PILOT_GATE_SECRET \
  use-summary-table:local
# open http://localhost:8080
```

Or run the API alone against a static file server:

```bash
export AZURE_CLIENT_SECRET="..."
export PILOT_GATE_SECRET="ust-pilot-2026"
node server/index.mjs
```

---

## Cloudflare Pages

This app is deployed on **Cloudflare Pages** with a serverless function for LLM extraction.

## Setup Steps

### 1. Connect Repository to Cloudflare Pages

1. Go to [Cloudflare Dashboard](https://dash.cloudflare.com) → Pages
2. Click **Create a project** → **Connect to Git**
3. Select this repository
4. Configure build settings:
   - **Build command:** (leave empty)
   - **Build output directory:** `app`
   - **Root directory:** (leave empty)

### 2. Configure Environment Variables

Go to **Settings** → **Environment variables** and add:

| Variable | Value | Notes |
|----------|-------|-------|
| `AZURE_CLIENT_SECRET` | `[your-entra-secret]` | Client secret for Entra app "Use Summary Table Extractor" (encrypted secret) |
| `PILOT_GATE_SECRET` | `ust-pilot-2026` | Must match `PILOT_GATE_HEADER_VALUE` in app/index.html |

**Important:** Set these in the **Production** environment (Cloudflare applies env vars only to deployments built after they're saved).

`AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_SCOPE`, `TFY_BASE_URL`,
`RATE_LIMIT_PER_MINUTE`, `DAILY_BUDGET_USD`, and `AUDIT_TTL_SECONDS` are also configurable
— as plain (non-secret) `[vars]` in `wrangler.toml`, not dashboard environment variables —
but have safe defaults baked into the code, so you don't need to set them to get started.

### 3. Create the AUDIT_LOG KV namespace (monitoring, audit trail, cost controls)

The governance layer (`functions/api/_lib/governance.js`) needs a second KV namespace,
separate from `JOBS`, for rate-limit counters, the daily cost-budget counter, and
metadata-only audit records:

1. **Workers & Pages** → **KV** → **Create namespace** → name it something like
   `use-summary-audit-log`.
2. Copy its id into `[[kv_namespaces]] binding = "AUDIT_LOG"` in `wrangler.toml` (root)
   **and** `worker/wrangler.toml` — both must point at the same namespace so the
   interactive and background-job paths share one cumulative daily budget.
3. This only takes effect once the Pages project's "v2 build system" is on (see the
   comment at the top of `wrangler.toml`) — same requirement as the existing `JOBS`
   namespace.

Nothing breaks if this step is skipped — the governance checks fail open (they log the
error and let the request through) rather than blocking extraction on a missing binding.
But skipping it means the rate limit, budget cap, and audit trail are effectively inert.

### 4. Deploy

Push a commit or click **Retry deployment** in the Cloudflare dashboard. The function will be automatically available at:

```
https://your-site.pages.dev/api/extract
```

## How It Works

1. **App** (`app/index.html`): Static HTML/CSS/JS served directly
2. **Function** (`functions/api/extract.js`): Cloudflare Pages Function that:
   - Accepts POST requests to `/api/extract`
   - Validates the `x-ust-pilot: ust-pilot-2026` header
   - Obtains an Entra M2M access token (client credentials)
   - Forwards Anthropic Messages requests to Bayer AI Gateway
     (`TFY_BASE_URL` + `/v1/messages`, default `https://global.ai-gateway.int.bayer.ai/api/llm`)
   - Keeps `AZURE_CLIENT_SECRET` server-side (never exposed to browser)
   - Returns the model's structured response

## Function Endpoint Mapping

Cloudflare Pages automatically maps:
- `/api/extract` → `functions/api/extract.js` → `onRequestPost()` export

No special configuration file needed (unlike Netlify).

## Testing Locally

Install Wrangler (Cloudflare CLI):

```bash
npm install -g wrangler
```

Run local dev server:

```bash
wrangler pages dev app
```

Then open `http://localhost:8788` and test extraction.

**Note:** Local testing requires setting environment variables:

```bash
export AZURE_CLIENT_SECRET="your-entra-secret-here"
export PILOT_GATE_SECRET="ust-pilot-2026"
wrangler pages dev app
```

Or create a `.dev.vars` file (never commit this):

```
AZURE_CLIENT_SECRET=your-entra-secret-here
PILOT_GATE_SECRET=ust-pilot-2026
```

## Troubleshooting

### "Unauthorized" Error
- Check that `PILOT_GATE_SECRET` in Cloudflare matches `PILOT_GATE_HEADER_VALUE` in app/index.html

### "Entra token request failed" Error
- Verify `AZURE_CLIENT_SECRET` is set and not expired
- Confirm `llm.read` (Application) is granted on **AI-Gateway-PROD-IDP**
- Scope must be `https://bayer.com/ai-gateway-prod-idp/.default`

### "Could not reach AI Gateway" / Gateway 401/403
- Verify you're on Bayer's network or VPN
- Check that `https://global.ai-gateway.int.bayer.ai` is reachable
- Confirm TrueFoundry Virtual Account maps your client ID (`azp`) under `bayer-entraid`
- Model IDs: `anthropic/claude-sonnet-5` (extraction/QC), `anthropic/claude-opus-5` (remediation)

### "Rate limit exceeded" / "Daily AI budget exceeded" Error
- Expected behavior from the governance layer (see README.md's "Monitoring, audit trail &
  cost controls" section), not a bug. Wait a minute for the rate limit, or a day for the
  budget — or raise `RATE_LIMIT_PER_MINUTE` / `DAILY_BUDGET_USD` in `wrangler.toml` (and
  `worker/wrangler.toml`) if the defaults are genuinely too low for the pilot's usage.
- Check `wrangler kv key list --binding=AUDIT_LOG` if you need to see today's actual spend.

### Emergency: disabling AI extraction immediately (kill switch)
If something goes wrong with the shared mGA token or an extraction is misbehaving, disable
both AI paths without a deploy:
```bash
wrangler kv key put --namespace-id=<AUDIT_LOG_ID> "killswitch:enabled" "true"
wrangler kv key put --namespace-id=<AUDIT_LOG_ID> "killswitch:reason" "short reason shown to users"
```
`<AUDIT_LOG_ID>` is the same namespace id you pasted into both `wrangler.toml` files in
step 3 above (either file's copy works — it's one namespace). Both `/api/extract` and
`/api/jobs` start returning 503 immediately; no redeploy needed, no need to be in either
project's directory. Re-enable with:
```bash
wrangler kv key delete --namespace-id=<AUDIT_LOG_ID> "killswitch:enabled"
```
This only stops *new* work — a job already queued or a Worker mid-file is checked again
before that file starts, but a call already in flight to mGA still completes.

### Function Not Found (404)
- Verify `functions/api/extract.js` exists
- Check that it exports `onRequestPost` (not `handler` or other names)
- Trigger a fresh deployment after adding the file

## Keeping Knowledge Files in Sync

The app embeds knowledge files as constants. After editing any file in `knowledge/`, run:

```bash
python3 scripts/sync-knowledge.py
```

Then commit `app/index.html` and push to deploy the updated rules to production.
