#!/usr/bin/env bash
# Smoke-test Bayer Production AI Gateway via Entra M2M (default).
# Usage:
#   ./scripts/test-ai-gateway.sh
#   USE_VAT=1 ./scripts/test-ai-gateway.sh   # force Virtual Account token
#
# Does not print raw secrets.

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

TFY_BASE_URL="${TFY_BASE_URL:-https://global.ai-gateway.int.bayer.ai/api/llm}"
TFY_BASE_URL="${TFY_BASE_URL%/}"
MODEL="${TFY_MODEL:-anthropic/claude-opus-5}"

if [[ "${USE_VAT:-}" == "1" && -n "${TFY_API_TOKEN:-}" ]]; then
  echo "=== 1) Auth: Virtual Account token (USE_VAT=1) ==="
  TOKEN="$TFY_API_TOKEN"
  echo "Using VAT (length ${#TOKEN})"
elif [[ -n "${AZURE_CLIENT_SECRET:-}" ]]; then
  TENANT_ID="${AZURE_TENANT_ID:-fcb2b37b-5da0-466b-9b83-0014b67a7c78}"
  CLIENT_ID="${AZURE_CLIENT_ID:-5d0b410a-0b42-4427-8bd5-289c1ac0abce}"
  SCOPE="${AZURE_SCOPE:-https://bayer.com/ai-gateway-prod-idp/.default}"

  echo "=== 1) Auth: Entra client-credentials (production path) ==="
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
elif [[ -n "${TFY_API_TOKEN:-}" ]]; then
  echo "=== 1) Auth: Virtual Account token (fallback) ==="
  TOKEN="$TFY_API_TOKEN"
  echo "Using VAT (length ${#TOKEN})"
else
  echo "Set AZURE_CLIENT_SECRET in .dev.vars"
  exit 1
fi

echo
echo "=== 2) Gateway Anthropic POST ${TFY_BASE_URL}/v1/messages (model=${MODEL}) ==="
curl -s -w "\nHTTP %{http_code}\n" -X POST "${TFY_BASE_URL}/v1/messages" \
  -H "content-type: application/json" \
  -H "authorization: Bearer ${TOKEN}" \
  -H "anthropic-version: 2023-06-01" \
  -d "{\"model\":\"${MODEL}\",\"max_tokens\":16,\"messages\":[{\"role\":\"user\",\"content\":\"Reply with exactly: pong\"}]}"

echo
echo "=== 3) Gateway OpenAI POST ${TFY_BASE_URL}/chat/completions ==="
curl -s -w "\nHTTP %{http_code}\n" -X POST "${TFY_BASE_URL}/chat/completions" \
  -H "content-type: application/json" \
  -H "authorization: Bearer ${TOKEN}" \
  -d '{"model":"azure-openai/gpt-5.4-nano","max_tokens":16,"messages":[{"role":"user","content":"Reply with exactly: pong"}]}'

echo
echo "Done. Success = HTTP 200 on step 2 (Anthropic path used by the app)."
