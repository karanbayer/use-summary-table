// Reassemble an Anthropic Messages SSE stream into the non-streaming
// { stop_reason, content, usage } JSON shape the browser expects.
// Same approach as worker/src/pipeline.js — streaming avoids AI Gateway /
// proxy idle timeouts (504/524) on long Opus generations for large labels.

function finalizeToolUseBlocks(blocksByIndex) {
  for (const block of blocksByIndex.values()) {
    if (block.type !== "tool_use") continue;
    // Prefer accumulated partial_json (even if content_block_stop never
    // arrived — truncated streams used to leave input as {}).
    if (block._json) {
      try {
        block.input = JSON.parse(block._json);
      } catch (err) {
        throw new Error(
          `AI Gateway stream returned incomplete tool JSON (${block.name || "tool_use"}): ${err.message}`
        );
      }
    } else if (!block.input || typeof block.input !== "object") {
      block.input = {};
    }
  }
}

export async function readMessagesStream(response) {
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  const blocksByIndex = new Map();
  let stopReason = null;
  let buffer = "";
  const usage = { input_tokens: 0, output_tokens: 0 };

  const handleEvent = (dataLine) => {
    if (!dataLine || dataLine === "[DONE]") return;
    const evt = JSON.parse(dataLine);
    if (evt.type === "error") {
      throw new Error(evt.error?.message || "AI Gateway stream reported an error event");
    } else if (evt.type === "message_start") {
      if (evt.message?.usage?.input_tokens != null) usage.input_tokens = evt.message.usage.input_tokens;
    } else if (evt.type === "content_block_start") {
      blocksByIndex.set(evt.index, { ...evt.content_block, _json: "" });
    } else if (evt.type === "content_block_delta") {
      const block = blocksByIndex.get(evt.index);
      if (!block) return;
      if (evt.delta.type === "input_json_delta") block._json += evt.delta.partial_json || "";
      else if (evt.delta.type === "text_delta") block.text = (block.text || "") + evt.delta.text;
      else if (evt.delta.type === "thinking_delta" && evt.delta.thinking != null) {
        block.thinking = (block.thinking || "") + evt.delta.thinking;
      }
    } else if (evt.type === "content_block_stop") {
      const block = blocksByIndex.get(evt.index);
      if (block && block.type === "tool_use" && block._json) {
        block.input = JSON.parse(block._json);
      }
    } else if (evt.type === "message_delta") {
      if (evt.delta?.stop_reason) stopReason = evt.delta.stop_reason;
      if (evt.usage?.output_tokens != null) usage.output_tokens = evt.usage.output_tokens;
    }
  };

  const flushBuffer = (flushTail) => {
    // Accept CRLF or LF event separators.
    buffer = buffer.replace(/\r\n/g, "\n");
    let sepIndex;
    while ((sepIndex = buffer.indexOf("\n\n")) !== -1) {
      const rawEvent = buffer.slice(0, sepIndex);
      buffer = buffer.slice(sepIndex + 2);
      const dataLines = rawEvent.split("\n").filter(line => line.startsWith("data:"));
      // Anthropic sends one data: line per event; join if a proxy splits JSON.
      if (dataLines.length) {
        handleEvent(dataLines.map(line => line.slice(5).trim()).join(""));
      }
    }
    if (flushTail && buffer.trim()) {
      const dataLines = buffer.split("\n").filter(line => line.startsWith("data:"));
      if (dataLines.length) {
        handleEvent(dataLines.map(line => line.slice(5).trim()).join(""));
      }
      buffer = "";
    }
  };

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += value;
      flushBuffer(false);
    }
    flushBuffer(true);
  } finally {
    reader.releaseLock();
  }

  finalizeToolUseBlocks(blocksByIndex);

  const content = [...blocksByIndex.values()].map(({ _json, ...block }) => block);
  return {
    stop_reason: stopReason,
    content,
    usage,
    type: "message",
    role: "assistant"
  };
}

/** Parse client JSON body and force Anthropic streaming upstream. */
export function withStreamEnabled(bodyText) {
  const parsed = JSON.parse(bodyText);
  parsed.stream = true;
  return { parsed, upstreamBody: JSON.stringify(parsed) };
}
