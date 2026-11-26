// Minimal Anthropic-Messages <-> OpenAI-Chat-Completions translator for
// EU-hosted Microsoft Foundry models (e.g. microsoft-foundry-eu/gpt-6-sol-2)
// routed through Bayer's AI Gateway (/chat/completions).
//
// Always calls Foundry EU with stream:false (fast 20-30s on 30+ page labels,
// zero chunk-reassembly drift, and returns exact usage.costInUSD). Callers in
// HTTP relays wrap this call in SSE keepalives so proxies never idle-timeout.
//
// Duplicated across worker/src/openai-chat.js, server/lib/openai-chat.mjs,
// and functions/api/_lib/openai-chat.js (no shared bundler). Keep in sync.

export const ALLOWED_MODELS = new Set([
  "anthropic/claude-sonnet-5",
  "anthropic/claude-opus-5",
  "microsoft-foundry-eu/gpt-6-sol-2"
]);

const OPENAI_PROVIDER_PREFIX = "microsoft-foundry-eu/";
const DEFAULT_MAX_COMPLETION_TOKENS = 12000;
const MAX_COMPLETION_TOKENS_CAP = 16384;

export function isAllowedModel(model) {
  return typeof model === "string" && ALLOWED_MODELS.has(model.trim());
}

export function isOpenAiModel(model) {
  return typeof model === "string" && model.trim().startsWith(OPENAI_PROVIDER_PREFIX);
}

/**
 * Resolves the QC model from env.QC_MODEL if present and allowlisted;
 * otherwise falls back to `fallback` (Sonnet).
 */
export function resolveQcModel(env, fallback = "anthropic/claude-sonnet-5") {
  const configured = String(env?.QC_MODEL || "").trim();
  if (configured && isAllowedModel(configured)) return configured;
  return fallback;
}

function flattenTextBlocks(content) {
  if (typeof content === "string") return content;
  if (!Array.isArray(content)) return content == null ? "" : String(content);
  const parts = [];
  for (const block of content) {
    if (typeof block === "string") {
      parts.push(block);
    } else if (block && block.type === "text" && typeof block.text === "string") {
      parts.push(block.text);
    } else if (block && block.type === "tool_result") {
      const inner = typeof block.content === "string"
        ? block.content
        : JSON.stringify(block.content ?? "");
      if (inner) parts.push(inner);
    }
  }
  return parts.join("\n\n");
}

/**
 * Converts an Anthropic /v1/messages request body into an OpenAI
 * /chat/completions request body (stream: false). Strips Anthropic-only fields
 * like cache_control.
 */
export function toOpenAiChatPayload(anthropicBody) {
  if (!anthropicBody || typeof anthropicBody !== "object") {
    throw new Error("Anthropic request body must be a JSON object");
  }
  const messages = [];
  const systemText = flattenTextBlocks(anthropicBody.system);
  if (systemText) {
    messages.push({ role: "system", content: systemText });
  }
  for (const msg of anthropicBody.messages || []) {
    if (!msg || !msg.role) continue;
    const role = msg.role === "assistant" ? "assistant" : "user";
    const text = flattenTextBlocks(msg.content);
    if (text) messages.push({ role, content: text });
  }

  const reqMax = Number(anthropicBody.max_tokens);
  const maxCompletionTokens = Number.isFinite(reqMax) && reqMax > 0
    ? Math.min(Math.max(Math.round(reqMax), 4096), MAX_COMPLETION_TOKENS_CAP)
    : DEFAULT_MAX_COMPLETION_TOKENS;

  const payload = {
    model: String(anthropicBody.model || "").trim(),
    messages,
    max_completion_tokens: maxCompletionTokens,
    stream: false
  };

  if (Array.isArray(anthropicBody.tools) && anthropicBody.tools.length) {
    payload.tools = anthropicBody.tools.map(t => ({
      type: "function",
      function: {
        name: t.name,
        description: t.description || "",
        parameters: t.input_schema || { type: "object", properties: {} }
      }
    }));
  }

  const tc = anthropicBody.tool_choice;
  if (tc && typeof tc === "object" && tc.type === "tool" && tc.name) {
    payload.tool_choice = { type: "function", function: { name: tc.name } };
  } else if (tc === "auto" || (tc && tc.type === "auto")) {
    payload.tool_choice = "auto";
  }

  return payload;
}

/**
 * Converts an OpenAI /chat/completions JSON response back into an Anthropic
 * message-shaped object ({ stop_reason, content, usage }). Validates JSON in
 * tool_call arguments so truncated/malformed replies trigger retry.
 */
export function fromOpenAiChatResponse(data) {
  const choice = data?.choices?.[0];
  if (!choice || !choice.message) {
    throw new Error("OpenAI Chat Completions response missing choices[0].message");
  }
  const msg = choice.message;
  const content = [];

  if (typeof msg.content === "string" && msg.content.trim()) {
    content.push({ type: "text", text: msg.content });
  }

  const toolCalls = Array.isArray(msg.tool_calls) ? msg.tool_calls : [];
  for (let i = 0; i < toolCalls.length; i++) {
    const tc = toolCalls[i];
    const fn = tc?.function || {};
    const name = fn.name;
    if (!name) continue;
    let input = {};
    if (typeof fn.arguments === "string" && fn.arguments.trim()) {
      try {
        input = JSON.parse(fn.arguments);
      } catch (err) {
        throw new Error(`OpenAI tool_call returned incomplete JSON (${name}): ${err.message}`);
      }
    } else if (fn.arguments && typeof fn.arguments === "object") {
      input = fn.arguments;
    }
    content.push({
      type: "tool_use",
      id: tc.id || `toolu_${i + 1}`,
      name,
      input
    });
  }

  const finish = choice.finish_reason;
  const stop_reason = finish === "length"
    ? "max_tokens"
    : (toolCalls.length ? "tool_use" : "end_turn");

  const rawUsage = data.usage || {};
  const inputTokens = Number(rawUsage.prompt_tokens) || 0;
  const outputTokens = Number(rawUsage.completion_tokens) || 0;
  const usage = {
    input_tokens: inputTokens,
    output_tokens: outputTokens,
    inputTokens,
    outputTokens
  };
  if (typeof rawUsage.costInUSD === "number" && Number.isFinite(rawUsage.costInUSD)) {
    usage.costInUSD = rawUsage.costInUSD;
  }

  return { stop_reason, content, usage };
}

/**
 * Sends a translated OpenAI Chat Completions request to Bayer AI Gateway and
 * returns an Anthropic-shaped message object.
 */
export async function callOpenAiChat({ chatUrl, accessToken, anthropicBody, signal }) {
  const payload = toOpenAiChatPayload(anthropicBody);
  const response = await fetch(chatUrl, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "authorization": `Bearer ${accessToken}`
    },
    body: JSON.stringify(payload),
    signal
  });

  if (!response.ok) {
    const errText = await response.text().catch(() => "");
    let detail = "";
    try { detail = JSON.parse(errText)?.error?.message || ""; } catch (_) { /* not JSON */ }
    const err = new Error(`AI Gateway request failed (${response.status})${detail ? `: ${detail}` : ""}`);
    err.status = response.status;
    err.bodyText = errText;
    throw err;
  }

  const data = await response.json();
  return fromOpenAiChatResponse(data);
}
