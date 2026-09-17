#!/usr/bin/env bash
# Smoke-test Entra M2M → Bayer Production AI Gateway.
# Usage (from anywhere):
#   ./scripts/test-ai-gateway.sh
#
# Requires .dev.vars in the repo root with AZURE_CLIENT_SECRET=...
# Does not print the raw access token.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .dev.vars ]]; then
  echo "Missing .dev.vars — copy .dev.vars.example and set AZURE_CLIENT_SECRET"
  exit 1
fi

set -a
# shellcheck disable=SC1091
source .dev.vars
set +a

if [[ -z "${AZURE_CLIENT_SECRET:-}" ]]; then
  echo "AZURE_CLIENT_SECRET is empty in .dev.vars"
  exit 1
fi

TENANT_ID="${AZURE_TENANT_ID:-fcb2b37b-5da0-466b-9b83-0014b67a7c78}"
CLIENT_ID="${AZURE_CLIENT_ID:-5d0b410a-0b42-4427-8bd5-289c1ac0abce}"
SCOPE="${AZURE_SCOPE:-https://bayer.com/ai-gateway-prod-idp/.default}"
TFY_BASE_URL="${TFY_BASE_URL:-https://global.ai-gateway.int.bayer.ai/api/llm}"
TFY_BASE_URL="${TFY_BASE_URL%/}"

echo "=== 1) Entra client-credentials token ==="
TOKEN_JSON=$(curl -s -X POST \
  "https://login.microsoftonline.com/${TENANT_ID}/oauth2/v2.0/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials" \
  -d "client_id=${CLIENT_ID}" \
  -d "client_secret=${AZURE_CLIENT_SECRET}" \
  -d "scope=${SCOPE}")

TOKEN=$(python3 -c 'import json,sys; d=json.loads(sys.argv[1]);
t=d.get("access_token");
assert t, d;
print(t)' "$TOKEN_JSON")

python3 - <<PY
import json, base64
token = """$TOKEN"""
pad = "=" * (-len(token.split(".")[1]) % 4)
c = json.loads(base64.urlsafe_b64decode(token.split(".")[1] + pad))
print("Entra OK")
for k in ("ver", "azp", "aud", "roles", "iss"):
    print(f"  {k}: {c.get(k)}")
PY

echo
echo "=== 2) Gateway Anthropic POST ${TFY_BASE_URL}/v1/messages ==="
curl -s -w "\nHTTP %{http_code}\n" -X POST "${TFY_BASE_URL}/v1/messages" \
  -H "content-type: application/json" \
  -H "authorization: Bearer ${TOKEN}" \
  -H "anthropic-version: 2023-06-01" \
  -d '{"model":"claude-opus-5","max_tokens":16,"messages":[{"role":"user","content":"Reply with exactly: pong"}]}'

echo
echo "=== 3) Gateway OpenAI POST ${TFY_BASE_URL}/chat/completions ==="
curl -s -w "\nHTTP %{http_code}\n" -X POST "${TFY_BASE_URL}/chat/completions" \
  -H "content-type: application/json" \
  -H "authorization: Bearer ${TOKEN}" \
  -d '{"model":"azure-openai/gpt-5.4-nano","max_tokens":16,"messages":[{"role":"user","content":"Reply with exactly: pong"}]}'

echo
echo "Done. Success = HTTP 200 on step 2 or 3. Current auth failure = HTTP 401 Invalid token."
