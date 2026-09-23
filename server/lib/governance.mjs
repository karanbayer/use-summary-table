// Governance helpers — rate limiting, daily cost budget, audit logging, and
// a content-safety tripwire. Port of functions/api/_lib/governance.js for
// Agentrix; uses env.AUDIT_LOG (memory store) instead of Cloudflare KV.
// Also honors KILL_SWITCH_ENABLED / KILL_SWITCH_REASON env vars so ops can
// disable AI without a shared KV CLI.

const DEFAULT_RATE_LIMIT_PER_MINUTE = 20;
const DEFAULT_DAILY_BUDGET_USD = 100;
const DEFAULT_AUDIT_TTL_SECONDS = 180 * 24 * 60 * 60;

const MODEL_PRICING = {
  "anthropic/claude-sonnet-5": { inputPerMtok: 3, outputPerMtok: 15 },
  "anthropic/claude-opus-5": { inputPerMtok: 15, outputPerMtok: 75 }
};
const DEFAULT_MODEL = "anthropic/claude-sonnet-5";

const INJECTION_PATTERNS = [
  { name: "ignore-instructions", re: /ignore (all |any )?(previous|prior) instructions/i },
  { name: "disregard-system-prompt", re: /disregard (the |any )?(system prompt|previous instructions)/i },
  { name: "role-override", re: /you are now (a|an)\b/i },
  { name: "new-instructions-override", re: /new instructions?:/i }
];

function todayKey() {
  return new Date().toISOString().slice(0, 10);
}

export function scanForInjectionPhrases(text) {
  if (!text) return [];
  return INJECTION_PATTERNS.filter(p => p.re.test(text)).map(p => p.name);
}

export async function checkKillSwitch(env) {
  if (String(env.KILL_SWITCH_ENABLED || "").toLowerCase() === "true") {
    return {
      enabled: true,
      reason: env.KILL_SWITCH_REASON || "AI extraction is temporarily disabled."
    };
  }
  try {
    const value = await env.AUDIT_LOG.get("killswitch:enabled");
    if (value !== "true") return { enabled: false };
    const reason = await env.AUDIT_LOG.get("killswitch:reason");
    return { enabled: true, reason: reason || "AI extraction is temporarily disabled." };
  } catch (err) {
    console.error(`kill-switch check failed, allowing request through: ${err.message}`);
    return { enabled: false };
  }
}

export async function checkRateLimit(env, bucketPrefix) {
  const limit = Number(env.RATE_LIMIT_PER_MINUTE) || DEFAULT_RATE_LIMIT_PER_MINUTE;
  const bucket = Math.floor(Date.now() / 60000);
  const key = `ratelimit:${bucketPrefix}:${bucket}`;
  try {
    const existing = await env.AUDIT_LOG.get(key);
    const count = existing ? Number(existing) : 0;
    await env.AUDIT_LOG.put(key, String(count + 1), { expirationTtl: 120 });
    return { allowed: count < limit, count: count + 1, limit };
  } catch (err) {
    console.error(`rate-limit check failed, allowing request through: ${err.message}`);
    return { allowed: true, count: 0, limit };
  }
}

export function estimateCostUsd(usage, model) {
  if (!usage) return 0;
  if (model && !MODEL_PRICING[model]) {
    console.warn(`estimateCostUsd: unrecognized model "${model}", using ${DEFAULT_MODEL} pricing as an approximation`);
  }
  const pricing = MODEL_PRICING[model] || MODEL_PRICING[DEFAULT_MODEL];
  const inputCost = ((usage.inputTokens || 0) / 1e6) * pricing.inputPerMtok;
  const outputCost = ((usage.outputTokens || 0) / 1e6) * pricing.outputPerMtok;
  return inputCost + outputCost;
}

export async function checkBudget(env) {
  const limit = Number(env.DAILY_BUDGET_USD) || DEFAULT_DAILY_BUDGET_USD;
  const key = `budget:${todayKey()}`;
  try {
    const existing = await env.AUDIT_LOG.get(key);
    const spent = existing ? (JSON.parse(existing).estCostUsd || 0) : 0;
    return { allowed: spent < limit, spentUsd: spent, limitUsd: limit };
  } catch (err) {
    console.error(`budget check failed, allowing request through: ${err.message}`);
    return { allowed: true, spentUsd: 0, limitUsd: limit };
  }
}

export async function recordUsage(env, usage) {
  const key = `budget:${todayKey()}`;
  try {
    const existingText = await env.AUDIT_LOG.get(key);
    const existing = existingText ? JSON.parse(existingText) : { inputTokens: 0, outputTokens: 0, estCostUsd: 0 };
    const updated = {
      inputTokens: existing.inputTokens + (usage?.inputTokens || 0),
      outputTokens: existing.outputTokens + (usage?.outputTokens || 0),
      estCostUsd: existing.estCostUsd + (usage?.estCostUsd || 0)
    };
    await env.AUDIT_LOG.put(key, JSON.stringify(updated), { expirationTtl: 2 * 24 * 60 * 60 });
  } catch (err) {
    console.error(`could not record usage against the daily budget: ${err.message}`);
  }
}

export async function recordAudit(env, record) {
  try {
    const ttl = Number(env.AUDIT_TTL_SECONDS) || DEFAULT_AUDIT_TTL_SECONDS;
    const key = `audit:${todayKey()}:${crypto.randomUUID()}`;
    await env.AUDIT_LOG.put(
      key,
      JSON.stringify({ ts: new Date().toISOString(), ...record }),
      { expirationTtl: ttl }
    );
  } catch (err) {
    console.error(`could not write audit record (the call itself is unaffected): ${err.message}`);
  }
}
