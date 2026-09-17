// Entra ID client-credentials token for Bayer AI Gateway (TrueFoundry) M2M.
// Secrets stay server-side — never expose AZURE_CLIENT_SECRET to the browser.
//
// Required env (Cloudflare encrypted secrets / .dev.vars):
//   AZURE_CLIENT_SECRET
// Optional env (defaults match prod Entra resource + documented Gateway host):
//   AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_SCOPE, TFY_BASE_URL

const DEFAULT_TENANT_ID = "fcb2b37b-5da0-466b-9b83-0014b67a7c78";
const DEFAULT_CLIENT_ID = "5d0b410a-0b42-4427-8bd5-289c1ac0abce";
const DEFAULT_SCOPE = "https://bayer.com/ai-gateway-prod-idp/.default";
const DEFAULT_TFY_BASE_URL = "https://global.ai-gateway.int.bayer.ai/api/llm";

// Per-isolate cache — Workers/Pages may recycle; refresh before expiry.
let cachedToken = null;
let cachedExpiresAtMs = 0;

export function gatewayConfig(env) {
  const base = (env.TFY_BASE_URL || DEFAULT_TFY_BASE_URL).replace(/\/$/, "");
  return {
    tenantId: env.AZURE_TENANT_ID || DEFAULT_TENANT_ID,
    clientId: env.AZURE_CLIENT_ID || DEFAULT_CLIENT_ID,
    scope: env.AZURE_SCOPE || DEFAULT_SCOPE,
    // Anthropic Messages API via TrueFoundry (same shape as former mGA relay).
    messagesUrl: `${base}/v1/messages`,
    baseUrl: base
  };
}

/**
 * Returns a Bearer access token for the AI Gateway.
 * @param {object} env Cloudflare env bindings
 * @returns {Promise<string>}
 */
export async function getGatewayAccessToken(env) {
  const now = Date.now();
  if (cachedToken && now < cachedExpiresAtMs - 60_000) {
    return cachedToken;
  }

  const { tenantId, clientId, scope } = gatewayConfig(env);
  const secret = env.AZURE_CLIENT_SECRET;
  if (!secret) {
    throw new Error("AZURE_CLIENT_SECRET is not configured");
  }

  const tokenUrl = `https://login.microsoftonline.com/${tenantId}/oauth2/v2.0/token`;
  const body = new URLSearchParams({
    grant_type: "client_credentials",
    client_id: clientId,
    client_secret: secret,
    scope
  });

  const res = await fetch(tokenUrl, {
    method: "POST",
    headers: { "content-type": "application/x-www-form-urlencoded" },
    body
  });

  const data = await res.json().catch(() => ({}));
  if (!res.ok || !data.access_token) {
    const detail = data.error_description || data.error || `HTTP ${res.status}`;
    throw new Error(`Entra token request failed: ${detail}`);
  }

  cachedToken = data.access_token;
  const expiresInSec = Number(data.expires_in) || 3600;
  cachedExpiresAtMs = now + expiresInSec * 1000;
  return cachedToken;
}
