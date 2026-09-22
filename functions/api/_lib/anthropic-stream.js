// Reassemble an Anthropic Messages SSE stream into the non-streaming
// { stop_reason, content, usage } JSON shape the browser expects.
// Same approach as worker/src/pipeline.js — streaming avoids AI Gateway /
// proxy idle timeouts (504/524) on long Opus generations for large labels.

export async function readMessagesStream(response) {
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  const blocksByIndex = new Map();
  let stopReason = null;
  let buffer = "";
  const usage = { input_tokens: 0, output_tokens: 0 };

  const handleEvent = (dataLine) => {
    if (!dataLine) return;
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
      if (evt.delta.type === "input_json_delta") block._json += evt.delta.partial_json;
      else if (evt.delta.type === "text_delta") block.text = (block.text || "") + evt.delta.text;
      else if (evt.delta.type === "thinking_delta" && evt.delta.thinking != null) {
        block.thinking = (block.thinking || "") + evt.delta.thinking;
      }
    } else if (evt.type === "content_block_stop") {
      const block = blocksByIndex.get(evt.index);
      if (block && block.type === "tool_use") {
        block.input = block._json ? JSON.parse(block._json) : {};
      }
    } else if (evt.type === "message_delta") {
      if (evt.delta?.stop_reason) stopReason = evt.delta.stop_reason;
      if (evt.usage?.output_tokens != null) usage.output_tokens = evt.usage.output_tokens;
    }
  };

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += value;
      let sepIndex;
      while ((sepIndex = buffer.indexOf("\n\n")) !== -1) {
        const rawEvent = buffer.slice(0, sepIndex);
        buffer = buffer.slice(sepIndex + 2);
        const dataLine = rawEvent
          .split("\n")
          .find(line => line.startsWith("data:"));
        if (dataLine) handleEvent(dataLine.slice(5).trim());
      }
    }
  } finally {
    reader.releaseLock();
  }

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
