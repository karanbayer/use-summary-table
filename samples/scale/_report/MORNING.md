# Morning — Cloudflare scale (EU Gateway)

Queued **2026-10-14T18:20:34Z**. Worker `TFY_BASE_URL` pinned to `https://eu.ai-gateway.int.bayer.ai/api/llm` (US plane Bedrock broken).

Relay workaround removed. **Agentrix:** set the same `TFY_BASE_URL` env and redeploy.

**Pages dashboard:** if `TFY_BASE_URL` is still `global…`, change it to `eu…` too.

## Job links

- **Wave A**: https://use-summary-table.pages.dev/?job=ac3e4632-3789-449d-9688-a585a0e57e66
- **Wave B**: https://use-summary-table.pages.dev/?job=fdf7bc76-71cf-48a2-82c2-c355ba74a08b
- **Wave C**: https://use-summary-table.pages.dev/?job=d95c1b1b-eb9f-4433-bf05-a8b57b056528

```bash
python3 scripts/scale_run_live.py --mode poll
```
