# Handover: Bayer AI apps on Agentrix (Use Summary Table Extractor, AgriGuide QC Assistant)

For whoever takes over these apps. It explains what exists, how the pieces connect, how to run and fix them,
and how to set up a new app the same way. **No secret values are in this file** — only names and IDs that are
safe to share inside Bayer. Secrets live in Agentrix (and in the owner's local `.dev.vars`, never in git or chat).

Owner until handover: Karandeep Singh (karandeep.singh@bayer.com), Life Sciences Regulatory.
Last updated: 23 Nov 2026 (Agentrix stages: section 6).

---

## 1. The two apps at a glance

| | Use Summary Table Extractor (UST) | AgriGuide QC Assistant |
|---|---|---|
| What it does | Extracts EPA label PDFs into the 28-column Use Summary Table; human review | Advisory QC of Quill → AgriGuide digital labels against the golden Word/PDF; never publishes |
| Live URL (Bayer network/VPN) | https://use-summary-table-extractor.agent.agentrix.int.bayer.ai/ | https://agriguide-qc.agent.agentrix.int.bayer.ai/ |
| Stages (since Nov 2026) | Development `https://use-summary-table-extractor-dev.agent.agentrix.int.bayer.ai/`, QA `…-qa…`, Production = Live URL. Check the agent page shows the stages before the next release | Development https://agriguide-qc-dev.agent.agentrix.int.bayer.ai/, QA https://agriguide-qc-qa.agent.agentrix.int.bayer.ai/, Production = Live URL |
| Agentrix project | https://agentrix.int.bayer.ai/projects/prj-ff9f7094 | "Agriguide QC Assistant" — https://agentrix.int.bayer.ai/projects/prj-11265a61 |
| Agentrix agent | `use-summary-table-extractor` (id `agent-27163dcf`) | `agriguide-qc` (id shown in Agentrix → agent → Security) |
| GitHub (code that is deployed) | https://github.com/bayer-int/use-summary-table (Internal) | https://github.com/bayer-int/agriguide-qc-assistant (Internal) |
| Older / personal copies | Cloudflare Pages `use-summary-table.pages.dev` | Cloudflare Pages `agriguide-qc-assistant.pages.dev` (to retire) |
| BEAT ID | `BEAT04090032` | `BEAT04090032` (shared — see section 3) |
| Entra app registration | "Use Summary Table Extractor", client id `5d0b410a-0b42-4427-8bd5-289c1ac0abce` | same (shared) |
| AI Gateway virtual account | `use-summary-table-extractor-prod` | same (shared) |
| Owning team (group) | `Use-Summary-Table-Extractor-Users` | same (shared) |
| Health check | `/health` | `/health` |
| Repo docs | `DEPLOYMENT.md`, `README.md`, `TRAINING.md` | `DEPLOYMENT.md`, `docs/colleague-workflow.md`, `TRAINING.md` |

Both apps are one Docker container each: a single Node process on port 8080 that serves the web page and a
small `/api/*` relay. The relay is the only part that talks to the AI model.

---

### BEAT record (governance)

| Field | Value |
|---|---|
| Record | `BEAT04090032` (link in section 4) |
| IT Product name | Use Summary Table Extractor |
| Category | Business Application |
| Business criticality | **Important** (after SME review) — no extra Special Roles needed for Quality and Security reviews |
| BEAT owner | Diana Stoyanova, NA KIM (BAY-CS-RD-RS-REEX) — diana.stoyanova@bayer.com |
| IT Product Manager / System Owner | Karandeep Singh |
| Lead business portfolio | CS-RD-REG-NAANZ, nonIT |
| Obligations | "Minimum Mandatory Requirements" (MMRs) tab on the record — keep them up to date |

The record names only UST. AgriGuide QC Assistant runs under it today (section 3).

---

## 2. How an AI call gets from the app to Claude

```
Browser page ──► app's /api/* relay (Agentrix container)
                    │ 1. asks Microsoft Entra ID for a token
                    │    (client credentials: client id + client secret, scope below)
                    ▼
                 Entra ID returns a v2.0 token: azp = our client id, roles = [llm.read]
                    │ 2. calls the Bayer AI Gateway (TrueFoundry) with that token
                    ▼
                 AI Gateway checks the token (IDP "bayer-entraid"), maps azp → our virtual account,
                 applies the virtual account's budget/rate limits, forwards to the model (AWS Bedrock / Azure)
```

Values used by both apps (none of these are secret):

| Setting | Value |
|---|---|
| Tenant id (`AZURE_TENANT_ID`) | `fcb2b37b-5da0-466b-9b83-0014b67a7c78` |
| Client id (`AZURE_CLIENT_ID`) | `5d0b410a-0b42-4427-8bd5-289c1ac0abce` ("Use Summary Table Extractor") |
| Scope (`AZURE_SCOPE`) | `https://bayer.com/ai-gateway-prod-idp/.default` |
| Resource app (the Gateway in Entra) | "AI-Gateway-PROD-IDP", app id `cd0c8712-6bcf-4da5-9033-9f0d002cac16` (token `aud`) |
| Permission on our app | Application permission `llm.read` on AI-Gateway-PROD-IDP, admin consent granted |
| Gateway endpoint (`TFY_BASE_URL`) | `https://eu.ai-gateway.int.bayer.ai/api/llm` (calls `/v1/messages`) |
| Model | `anthropic/claude-opus-5` (AgriGuide default; UST uses Opus and Sonnet) |

AI Gateway hosts (production): `cp.ai-gateway.int.bayer.ai` = portal/admin (log in here to see the virtual
account); `global.` / `eu.` / `us.ai-gateway.int.bayer.ai` = model calls. Never point an app at `cp`.
Non-production uses the same names on `…int.bayer.com`.

The only secret either app needs is **`AZURE_CLIENT_SECRET`** (the Entra client secret). A virtual-account API
token (`TFY_API_TOKEN`) also works as a fallback, but it auto-rotates every 90 days, so Entra is preferred.

---

## 3. Shared credentials — read this before changing anything

To avoid weeks of waiting, **AgriGuide QC Assistant reuses everything UST already had**: the BEAT ID, the Entra
app registration and its client secret, the AI Gateway virtual account and its owning team. Only the Agentrix
project/agent and the GitHub repo are separate.

What that means:

- **Cost and quota are pooled.** The virtual account budget (USD 200 at creation; check the portal for the current
  value) is spent by both apps together. The AI Gateway cannot tell them apart. Each app still has its own
  daily cap inside the app (`DAILY_BUDGET_USD`, 100 USD/day) and rate limit (`RATE_LIMIT_PER_MINUTE`, 20).
- **One secret, two apps.** If the Entra client secret expires or is rotated, **both apps stop** until the new value
  is pasted into **both** Agentrix agents and both are redeployed.
- **Revoking access hits both.** Removing `llm.read`, deleting the virtual account or the app registration breaks both.
- **Governance.** The BEAT entry describes UST. The BEAT owner (Diana Stoyanova) should be told that it also covers AgriGuide QC
  Assistant, or AgriGuide QC should get its own BEAT entry (below).

### How to separate them later (give AgriGuide QC its own identity)

Do these in order; each step is the same as for a brand-new app (section 5):

1. Own **BEAT entry** for AgriGuide QC Assistant (go/beat) — then update the Agentrix project's BEAT ID.
2. Own **owning-team group** (IdentityNow entitlement, e.g. `AgriGuide-QC-Assistant-Users`).
3. Own **Entra app registration** + client secret + `llm.read` on AI-Gateway-PROD-IDP (admin consent).
4. Own **AI Gateway virtual account** mapped to the new client id (ask AI Gateway IT support: Ashish Niranjan or Shiva Shiva).
5. In Agentrix (agent `agriguide-qc`): set `AZURE_CLIENT_ID` = new client id and `AZURE_CLIENT_SECRET` = new
   secret, redeploy, run one QC to confirm. No code change is needed — the client id is an environment variable
   (the code only defaults to UST's id).
6. Tell the UST owner that the shared secret is no longer used by AgriGuide QC.

---

## 4. Where everything lives (links)

| What | Link |
|---|---|
| Agentrix (projects, agents, deploys, secrets, access tokens) | https://agentrix.int.bayer.ai/ |
| Agentrix docs | https://docs.int.bayer.com/agentrix/ |
| Agentrix support | Platform: Luis Angelico; IT/infrastructure: Eswar CL — see section 9 |
| AI Gateway portal (virtual accounts, budgets, tokens) | https://cp.ai-gateway.int.bayer.ai/ |
| AI Gateway M2M (Entra) guide | https://docs.int.bayer.com/-/agentic-ai-docs/ecosystem/ai-gateway/m2m_flow/ |
| AI Gateway FAQ / user guide (hosts, endpoints) | https://docs.int.bayer.com/-/agentic-ai-docs/ecosystem/ai-gateway/ai-gateway-faq-and-user-guide/ |
| AI Gateway support (virtual accounts, 401/403 from Gateway) | No form — message Ashish Niranjan or Shiva Shiva (IT support); platform questions: Ilya Beketov, Tatsiana Rudnitskaya — see section 9 |
| Register an Entra app (ServiceNow request) | https://bayersi.service-now.com/efservices?id=sc_cat_item&sys_id=6f5e8a241bba8550d0c3b912dd4bcb16&sysparm_category=1ea23aa383c10a1020a940747daad390 |
| Entra app registration "Use Summary Table Extractor" (Azure portal) | https://portal.azure.com/#view/Microsoft_AAD_RegisteredApps/ApplicationMenuBlade/~/Overview/appId/5d0b410a-0b42-4427-8bd5-289c1ac0abce/isMSAApp~/false |
| Groups / entitlements (create or change the owning-team group) | https://bayer.identitynow.com/ui/d/launchpad/interactive-processes/01M4GFKVFPX7RDJRBD6CVHSZRW |
| BEAT record `BEAT04090032` (IT product "Use Summary Table Extractor", in ServiceNow) | https://bayersi.service-now.com/x_inpgh_upmx_business_application.do?sys_id=ea04afc02b978b502e6bf624f291bfac |
| BEAT (create a new IT product record) | go/beat |
| GitHub org | https://github.com/bayer-int |
### AI Gateway and machine-to-machine (Entra) reference

| What | Link / value |
|---|---|
| M2M guide: Entra client credentials → AI Gateway (start here for a new app) | https://docs.int.bayer.com/-/agentic-ai-docs/ecosystem/ai-gateway/m2m_flow/ |
| AI Gateway FAQ and user guide (hosts, endpoints, which region to use) | https://docs.int.bayer.com/-/agentic-ai-docs/ecosystem/ai-gateway/ai-gateway-faq-and-user-guide/ |
| Production portal / control plane (log in, virtual accounts, budgets, tokens — not for model calls) | https://cp.ai-gateway.int.bayer.ai/ |
| Production model endpoint, EU (what both apps use) | `https://eu.ai-gateway.int.bayer.ai/api/llm` → Anthropic format `…/v1/messages` |
| Production model endpoint, global (cheaper global routing, no region pinning) | `https://global.ai-gateway.int.bayer.ai/api/llm` → `…/v1/messages` or OpenAI format `…/chat/completions` |
| Production model endpoint, US | `https://us.ai-gateway.int.bayer.ai/api/llm` |
| Production token scope (Entra resource "AI-Gateway-PROD-IDP") | `https://bayer.com/ai-gateway-prod-idp/.default` |
| Non-production (testing only): portal / endpoints | `https://cp.ai-gateway.int.bayer.com`, `global.` / `eu.` / `us.ai-gateway.int.bayer.com` |
| Non-production token scope (Entra resource "TF-AI-Gateway-NP-EU") | `https://bayer.com/tf-ai-gateway-np-eu/.default` — do not mix with production endpoints (401) |
| TrueFoundry docs: gateway authentication | https://www.truefoundry.com/docs/gateway/authentication |
| TrueFoundry docs: native SDK support (Anthropic / OpenAI clients) | https://www.truefoundry.com/docs/ai-gateway/native-sdk-support |
| UST agent card on Agentrix (example of the agent registry entry) | https://api.agentrix.int.bayer.ai/api/agents/agent-27163dcf/.well-known/agent-card.json |

---

## 5. Setting up a new app from scratch (the order that works)

Expect the identity steps (1–4) to take days to weeks because of approvals; start them first.

1. **BEAT entry** — register the application in BEAT (go/beat). You get an ID like `BEAT0409xxxx`. Agentrix asks
   for it when you create a project ("required for tracing agents in Bayer observability").
2. **Owning-team group** — create an entitlement group in IdentityNow ("Create an entitlement (group)"), e.g.
   `<App-Name>-Users`, with you and a deputy as owners/members. The AI Gateway virtual account is owned by this
   group, and token-expiry emails go to its mailbox. Add the future owner here at handover.
3. **Entra app registration** — request it with the ServiceNow "register Entra app" form (section 4), then manage
   it in the Azure portal → App registrations:
   - Note the **Application (client) id** and **Directory (tenant) id**.
   - Certificates & secrets → **New client secret** → copy the **Value** immediately (shown once; the "Secret ID"
     is not the secret). Write down the **expiry date** and set a reminder.
   - API permissions → add **Application** permission **`llm.read`** on **AI-Gateway-PROD-IDP** → admin consent.
4. **AI Gateway virtual account** — ask AI Gateway IT support (Ashish Niranjan or Shiva Shiva) for a production virtual account,
   owned by the group from step 2, with identity-provider mapping **`bayer-entraid` → `azp` = your client id**.
   They create it via a pull request on their side; it works only after that PR is merged (they email you).
5. **Smoke test** from a laptop on VPN: request a token (client credentials, scope
   `https://bayer.com/ai-gateway-prod-idp/.default`), decode it and check `ver: 2.0`, `azp` = your client id,
   `roles: ["llm.read"]`; then `POST https://eu.ai-gateway.int.bayer.ai/api/llm/v1/messages` → HTTP 200.
   UST has a script for this: `scripts/test-ai-gateway.sh`.
6. **GitHub** — create an **Internal** repo in `bayer-int` (same as the others), empty (no README). Push with an SSH
   key for your Bayer GitHub account. Keep confidential data (golden labels, drafts, reports) out of git.
7. **Container** — repo root needs a `Dockerfile`. Rules learned the hard way:
   - One process listens on **`$PORT` (8080)** and serves both the page and `/api/*` (no separate nginx on 8080).
   - Answer **`GET /health`** with 200, and also **`GET /mcp`** (Agentrix probes it; a 200 JSON note is fine).
   - Read secrets from environment variables only.
   - Long model calls: stream or send keep-alive bytes so proxies don't cut idle requests.
8. **Agentrix project** — My Projects → Create project: name, description, **BEAT ID**, category (Regulatory).
   Leave **Memory Management off** unless the app is a chat agent that needs it.
9. **Agentrix agent** — inside the project choose **Deploy an agent** (builds your repo). **Not "Register an
   agent"** — that only adds a catalogue entry for an app hosted elsewhere and gives you no secrets screen.
   - Repo `https://github.com/bayer-int/<repo>`, branch `main`, lowercase hyphenated name (it becomes the URL:
     `https://<name>.agent.agentrix.int.bayer.ai/`). Visibility **Private**, lifecycle Development.
   - Secrets & Environment: `AGENTRIX_PAT` (Create Access Token → only scopes `write:traces` + `read:agent`;
     note the expiry), leave `AGENT_ID` and `OTEL_EXPORTER_OTLP_ENDPOINT` as filled in, then add
     `AZURE_CLIENT_SECRET` and the app's other variables.
   - Deploy (≈3 min): Queued → Clone → Code Scan → Build Image → Push to Registry → Deploy to Cluster.
     The first deploy goes to Development (`https://<name>-dev.agent.agentrix.int.bayer.ai/`); promote it to QA and
     Production for users (section 6, "Stages").
10. **Verify** on VPN: `/health` → `{"ok":true,...}`, open `/`, run one real case end to end.
---

## 6. Running the apps day to day

| Task | How |
|---|---|
| Deploy a code change | Push to `main` in the bayer-int repo. The GitHub workflow (Auto-Deploy) deploys it to the **Development** stage only (≈5 min); the **Deploy** button in Agentrix also deploys to Development but does not raise the version (see "Versions"). Check it on the `-dev` address, then Agentrix → agent → **Promote to QA** → **Promote to Prod**. Users see it only after the promotion to Production (see "Stages" below). |
| Change a secret / variable | Agentrix → agent → secrets editor (blank value = keep current) → save → **redeploy** so the pod picks it up. Secrets are per stage (Development, QA, Production). |
| Check it's alive | `https://<agent>.agent.agentrix.int.bayer.ai/health` on VPN. First hit after idle can take 30–60 s (scale to zero). |
| Logs | Agentrix → agent → deployment / pipeline runs → View logs; app audit lines are JSON (metadata only, no label text). |
| Pause AI use (kill switch) | Set `KILL_SWITCH_ENABLED=true` and `KILL_SWITCH_REASON=...` on the agent, redeploy. Remove to re-enable. |
| Spending | App caps: `DAILY_BUDGET_USD` (100) and `RATE_LIMIT_PER_MINUTE` (20) per app. Overall: virtual account budget in the AI Gateway portal (shared by both apps). |

### Stages: Development → QA → Production

Since 20 Nov 2026 Agentrix runs every agent in three stages, each with its own address, namespace and secrets:
`https://<agent>-dev.agent.agentrix.int.bayer.ai/` (Development), `https://<agent>-qa.agent.agentrix.int.bayer.ai/` (QA)
and `https://<agent>.agent.agentrix.int.bayer.ai/` (Production, the address users open). A deploy, from the GitHub
workflow or the **Deploy** button, updates Development only. The agent page may then show the new version as
"Deployed / Active" while Production still runs the old one, so check the Production address, not the badge.

To release:
1. Check the change on the `-dev` address.
2. Agentrix → agent → **Promote to QA**, then **Promote to Prod**. Both use the same image and take about 20 s each.
3. Each dialog checks that the target stage has all secrets; the first time, use **Copy from Development**. Keep
   Visibility **Private** unless the app should be listed on AgentHub, and tick "Unite cybersecurity review confirmed"
   only if a review was really done.
4. Open the Production address and hard-refresh (Cmd+Shift+R).

A secret or variable changed in one stage is not changed in the others; scale settings ("Keep always ready", Max Replicas) do carry over to every stage (Eswar CL, 24 Nov 2026). All three agents should run with Max Replicas 1 (state lives in the pod: budget and rate counters, UST's jobs, APRS's store), UST also with "Keep always ready". Send platform requests to **agentrix_support@bayer.com** so they are on record for the Agentrix backlog. Agentrix (Eswar CL, 23 Nov 2026): the stages
are intended, so every deploy can be checked before Production; automatic promotion is on the Agentrix backlog (Eswar, 24 Nov 2026): a
version that deploys successfully and passes the promotion checks moves to the next stage by itself. Until then the
owner clicks. The app owner can promote without Agentrix help (first done for AgriGuide QC 1.2.79,
23 Nov 2026).

### Who can open the apps

- Every `*.agent.agentrix.int.bayer.ai` address is behind the Agentrix **Bayer sign-in** (Entra). Anyone with a Bayer
  account, including external contractors with a `.ext@bayer.com` account, can open it, on or off VPN. Visibility
  "Private" only keeps an agent off AgentHub; it does not limit who can open it. People without a Bayer account cannot.
- Managing an agent (deploy, promote, secrets, logs) needs Agentrix project membership (`ef.a.ph-dai-agentrix-contributor`
  plus being added to the project, section 7).
- **Open request (Nov 2026): third-party label providers should be able to use AgriGuide QC.** Plan: invite each provider
  employee as an Entra **guest** (Bayer sponsor, end date), put the guests in a group such as "AgriGuide QC users", and
  have Agentrix allow only that group for `agriguide-qc` ("assignment required", like other Bayer apps). Not yet asked:
  Luis Angelico — does the Agentrix sign-in accept guests, can one agent be limited to a group, and which request
  invites a guest. Before anyone external gets access: update the BEAT record (or give AgriGuide QC its own, section 3),
  check the provider's contract/NDA covers confidential labels, ask whether the cybersecurity review becomes required,
  and check the daily budget (pooled with UST).
- **Persistent storage** will be a generic Agentrix feature (Eswar, 24 Nov 2026, on the backlog). Nice to have for
  AgriGuide QC (feedback and audit survive restarts); needed for APRS before its users start (January 2027).

### Versions

Each app has one version, kept in its Dockerfile (`LABEL version`, `ENV AGENT_VERSION`), `agent-card.json` and
`agenthub-agent.yaml` (Eswar CL, 24 Nov 2026: keep Agentrix and the repo in sync). The GitHub workflow raises it by one
on every deploy (`scripts/bump_version.py`), commits "Release x.y.z [skip ci]" to `main` and deploys with exactly that
version; nobody edits it by hand. So:
- `git pull` before your next push after a deploy (otherwise the push is rejected with "fetch first").
- Deploy without a code change via GitHub → Actions → **Deploy to Agentrix** → **Run workflow**, not the Agentrix
  **Deploy** button (the button does not raise the version, and a version Agentrix has seen makes it reuse its cache).
- `/health` on each stage's address shows the version it runs.

### Things that expire — put them in a calendar

| Item | Where | Expiry | Effect when it expires |
|---|---|---|---|
| Entra client secret | Azure portal → app → Certificates & secrets | **16 Sep 2027** — create the new secret by end of Aug 2027 | **Both apps** lose AI access → new secret into both agents, redeploy |
| Agentrix PATs (UST: `use-summary-table-deploy` ×2, `use-summary-table-extractor-deploy` ×2, created 23 Sep 2026; AgriGuide: `agriguide-qc`, created 18 Oct 2026) | Agentrix → Access Tokens | **Never** (as shown in Agentrix, Oct 2026) | — |

UST has four active tokens from its first deploy attempts; only one is in use and Agentrix does not show which.
To tidy up: create one new token, set it as `AGENTRIX_PAT` on the UST agent, redeploy, check `/health` and one
extraction, then delete the four old tokens. Deleting a token blindly can break the UST agent.
| Virtual-account API token (only if `TFY_API_TOKEN` is used) | AI Gateway portal | auto-rotates every 90 days (10-day grace) | fallback path only |

**Renewing the Entra client secret without downtime** (old and new secrets work side by side until the old expires):
1. Azure portal → "Use Summary Table Extractor" → Certificates & secrets → **New client secret** (24 months) →
   copy the **Value** once.
2. Paste it as `AZURE_CLIENT_SECRET` in **both** Agentrix agents (`use-summary-table-extractor`, `agriguide-qc`)
   and in your local `.dev.vars`; redeploy both.
3. Run one AI job in each app on VPN.
4. Delete the old secret in the Azure portal. Update the date in this table.

---

## 7. Handover checklist (new owner)

- [ ] Added as **owner** of the Entra app registration "Use Summary Table Extractor" (Azure portal → Owners).
- [ ] Added as owner/member of group **`Use-Summary-Table-Extractor-Users`** (IdentityNow) → gives virtual-account access and expiry emails.
- [ ] Can open virtual account `use-summary-table-extractor-prod` in the AI Gateway portal with **Manage** permission.
- [ ] Added to both **Agentrix projects** as owner (UST project, "Agriguide QC Assistant").
- [ ] **Admin** on `bayer-int/use-summary-table` and `bayer-int/agriguide-qc-assistant`.
- [ ] BEAT record `BEAT04090032`: **IT Product Manager / System Owner** changed to the new owner, MMRs tab reviewed.
- [ ] Received the current client secret through a secure channel (not email/chat), or created a new one and updated both agents.
- [ ] Knows the expiry dates in section 6 (most important: Entra client secret, 16 Sep 2027).
- [ ] Read each repo's `DEPLOYMENT.md` and `AGENTS.md`.

---

## 8. Problems we hit and what fixed them

| Symptom | Cause | Fix |
|---|---|---|
| Gateway `401 Invalid token` although Entra gives a token | Virtual account not mapped to our client id yet (AI Gateway PR not merged), or a v1.0 token without `azp` | AI Gateway support ticket (UST: INC27690735). Check token has `ver 2.0` + `azp`. |
| `403 … Unable to retrieve AWS credentials` from Agentrix only | `AZURE_CLIENT_SECRET` missing/stale on the agent, or not on VPN when testing | Paste the secret again in the agent's secrets, redeploy, test on VPN. |
| Can see the virtual account but "no Manage Virtual Account permission" | Virtual account is owned by the group, and your user isn't in it with Manage | Get added to the owning group (IdentityNow) / ask AI Gateway support. |
| Agentrix: "Cannot detect project type … add a Dockerfile" | No Dockerfile at repo root | Add a `Dockerfile` at the root. |
| Agentrix: "Knative service not ready after 325s", or `/` returns `{"error":"Not found"}` | nginx and Node both on 8080 / wrong port / nothing answering the probe | One Node process on `$PORT` serving page + API; answer `/health` and `/mcp`. |
| Browser: Skyhigh "SSL handshake failed" on the new URL | Service/cert not ready yet, or not on VPN | Wait a few minutes after first deploy, use VPN. |
| Agent shows "Runtime: Registered", no secrets editor | Created with **Register an agent** | Delete it; create with **Deploy an agent**. |
| "An agent named … already exists" after deleting it | Name stays reserved for a while | Pick another name (AgriGuide: `agriguide-qc`). |
| GitHub Action "Deploy to Agentrix" fails in 0 s: `bayer-int/PH-agentops-build-deploy-pipeline/…agent-build-push.yml@main … workflow was not found` | Our repos had no access to the shared pipeline repo | **Resolved — Auto-Deploy works.** If it fails again, deploy from the Agentrix UI and ask the Agentrix team (Luis Angelico) to check the repos' access to the pipeline. |
| A deploy succeeded (new version "Deployed / Active") but users still see the old app | Since 20 Nov 2026 deploys land in the Development stage (`<agent>-dev.agent…`); Production changes only through promotion | **Promote to QA** → **Promote to Prod** (section 6, "Stages"). Not a pipeline fault; nothing to change in `deploy.yml`. |
| Empty 404 after sign-in; Runtime logs say "No resources found in agents namespace" | That stage has nothing deployed yet (for example QA or Production before the first promotion) | Use the `-dev` address, or promote first. |
| `git push` rejected: OAuth app lacks `workflow` scope | HTTPS token can't change `.github/workflows` | Push over SSH, or `gh auth refresh -s workflow`. |
| App says "Daily AI budget exceeded" | App's own `DAILY_BUDGET_USD` reached | Wait until tomorrow (UTC) or raise the variable and redeploy. |
| Long batches drop ("stream dropped", 429/502) on UST | Long streaming calls through proxies; Gateway rate limits | UST retries with backoff and splits big labels; run one label at a time on Agentrix. |

---

## 9. Who to contact

| For | Who / how |
|---|---|
| Agentrix platform (how Agentrix works, projects, agents, who can open the URL, Auto-Deploy pipeline access) | Luis Angelico, Lead AI Engineer (BAY-FI-IT-DTPH-PDAI-DAII) — luis.angelico@bayer.com |
| Agentrix IT / infrastructure (minScale / keep a pod warm, volumes, request timeouts, pods not ready, deploy failures) | Eswar CL, Software Engineer (BAY-FI-IT-DTPH-PDAI-DAII) — eswar.cl@bayer.com; India time, works roughly 04:30–13:30 German time |
| AI Gateway platform (questions about the platform, virtual accounts, budgets, how to set up a new app) | Ilya Beketov (ilya.beketov@bayer.com) and Tatsiana Rudnitskaya (tatsiana.rudnitskaya@bayer.com) |
| AI Gateway IT support (access problems, 401/403 from the Gateway, tickets) | Ashish Niranjan, Software Engineering (BAY-FI-IT-TE-AIPA-AIE) — ashish.niranjan@bayer.com; India time, works roughly 06:30–15:30 German time |
| AI Gateway IT support (same topics, alternative contact) | Shiva Shiva, external (TCS, BAY-FI-IT-ITF) — shiva.shiva.ext@bayer.com; India time, works roughly 04:30–13:30 German time |
| Entra app registration, secrets, permissions/consent | New app: ServiceNow "register Entra app" form (section 4). Existing app: its owners in the Azure portal (Owners tab) |
| Groups / entitlements | IdentityNow (link in section 4) |
| BEAT record | BEAT owner: Diana Stoyanova — diana.stoyanova@bayer.com; US time, works roughly 15:00–00:00 German time. Detail questions: the record's Domain SMEs |
| Business owners / users | UST: Nancy Delaney, F&V SGR BLX & Consumer Prod (BAY-CS-RD-RS-RAC-BNAC) — nancy.delaney@bayer.com; US time, works roughly 14:00–00:00 German time; AgriGuide QC: Gaelle Der Hagopian, EMEA Scientific Affairs Manager (BAY-CS-RD-RS-REEX) — gaelle.derhagopian@bayer.com; German time, 09:00–17:00 |

---

## 10. App-specific notes

**Use Summary Table Extractor** — see that repo's `DEPLOYMENT.md`. Agentrix secrets: `AZURE_CLIENT_SECRET`,
`PILOT_GATE_SECRET` (must match `PILOT_GATE_HEADER_VALUE` in `app/index.html`), plus the Agentrix-provided ones.
Background jobs run inside the pod, so keep one replica warm (minScale 1) or jobs are lost on restart.

**AgriGuide QC Assistant** — see this repo's `DEPLOYMENT.md`. Agentrix secrets: `AZURE_CLIENT_SECRET`,
`RATE_LIMIT_PER_MINUTE=20`, `DAILY_BUDGET_USD=100`, `AUDIT_TTL_SECONDS=15552000`, plus the Agentrix-provided ones.
No pilot-gate secret. The QC engine runs in the colleague's browser (Pyodide from `cdn.jsdelivr.net`); label files
never leave the browser — only the model prompts go through the relay. It never publishes to Quill or AgriGuide.
Without a persistent volume, colleague feedback and the audit trail reset on restart (copies are in the logs).
