# Manual GenAI spans

Last verified: 2026-11-09 against `open-telemetry/semantic-conventions-genai` (unreleased, `gen-ai-dev/1.42.0-dev`).

For call paths with no instrumentation (raw HTTP to an inference API, or an uncovered library), and only after the user said yes in Step 3. Add **one shared helper** per unit and wrap every approved call site with it, so attributes stay consistent and the diff stays small.

## The span contract (OTel GenAI semantic conventions)

- **Name:** `{gen_ai.operation.name} {gen_ai.request.model}`, e.g. `chat gpt-4.1-mini`.
- **Kind:** `CLIENT`.
- **Required:** `gen_ai.operation.name` (`chat`, `text_completion`, `generate_content`, `embeddings`, …) and `gen_ai.provider.name` (`openai`, `anthropic`, `aws.bedrock`, `azure.ai.openai`, `gcp.gemini`, `gcp.vertex_ai`, `cohere`, `mistral`, `groq`, `deepseek`, `x_ai`, `perplexity`, `ollama`, …).
- **When known:** `gen_ai.request.model`, `server.address`, `server.port`, `gen_ai.request.temperature` / `max_tokens` / `top_p`, `gen_ai.response.model`, `gen_ai.response.id`, `gen_ai.response.finish_reasons` (string array), `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, `gen_ai.usage.cache_read.input_tokens`, `gen_ai.usage.reasoning.output_tokens`.
- **On error:** `error.type` (exception class name or HTTP status code), span status `ERROR`, and the exception recorded.
- **Content, only when capture is on:** `gen_ai.input.messages`, `gen_ai.output.messages`, `gen_ai.system_instructions`, as JSON strings, since span attributes can't hold nested structures. Message shape: `[{"role": "user", "parts": [{"type": "text", "content": "…"}]}]`. Output messages also carry `"finish_reason"`.

**Provider for OpenAI-compatible endpoints:** use the vendor actually serving the model when it's known (`ollama`, `groq`, `deepseek`, …). Otherwise use the API family (`openai`), and rely on `server.address` to identify the host (a LiteLLM proxy, vLLM).

**Mapping common response shapes to usage:**

| API | input tokens | output tokens | finish reason |
| --- | --- | --- | --- |
| OpenAI-compatible chat | `usage.prompt_tokens` | `usage.completion_tokens` | `choices[i].finish_reason` |
| OpenAI Responses | `usage.input_tokens` | `usage.output_tokens` | `status` |
| Anthropic Messages | `usage.input_tokens` | `usage.output_tokens` | `stop_reason` |
| Gemini `generateContent` | `usageMetadata.promptTokenCount` | `usageMetadata.candidatesTokenCount` | `candidates[i].finishReason` |
| embeddings (OpenAI-compatible) | `usage.prompt_tokens` | (none) | (none) |

**Streaming:** the span must cover the whole stream. Start it before the request, accumulate usage and finish reasons from the chunks (request `stream_options: {"include_usage": true}` from OpenAI-compatible APIs, if the call site already sets stream options), and end it after the last chunk or on error. Wrap the stream consumer, not just the initial request.

## TypeScript helper

`genai-span.ts`, next to the code that makes the calls:

```ts
import { SpanKind, SpanStatusCode, trace, type Attributes } from "@opentelemetry/api";

const tracer = trace.getTracer("genai-manual");
const v = (process.env.OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT ?? "").toLowerCase();
const captureContent = v !== "" && v !== "false" && v !== "no_content";

export interface GenAIRequest {
  operation: "chat" | "text_completion" | "generate_content" | "embeddings";
  provider: string;
  model: string;
  serverAddress?: string;
  serverPort?: number;
  attributes?: Attributes; // gen_ai.request.temperature, gen_ai.request.max_tokens, …
  inputMessages?: unknown; // recorded only when content capture is on
  systemInstructions?: unknown;
}

export interface GenAIResult {
  responseModel?: string;
  responseId?: string;
  finishReasons?: string[];
  inputTokens?: number;
  outputTokens?: number;
  outputMessages?: unknown; // recorded only when content capture is on
}

/** Run `call` inside a GenAI client span. `describe` maps its result to response attributes. */
export function withGenAISpan<T>(req: GenAIRequest, call: () => Promise<T>, describe: (result: T) => GenAIResult): Promise<T> {
  const attributes: Attributes = {
    "gen_ai.operation.name": req.operation,
    "gen_ai.provider.name": req.provider,
    "gen_ai.request.model": req.model,
    ...(req.serverAddress && { "server.address": req.serverAddress }),
    ...(req.serverPort && { "server.port": req.serverPort }),
    ...req.attributes,
  };
  if (captureContent && req.inputMessages !== undefined) attributes["gen_ai.input.messages"] = JSON.stringify(req.inputMessages);
  if (captureContent && req.systemInstructions !== undefined) attributes["gen_ai.system_instructions"] = JSON.stringify(req.systemInstructions);

  return tracer.startActiveSpan(`${req.operation} ${req.model}`, { kind: SpanKind.CLIENT, attributes }, async (span) => {
    try {
      const result = await call();
      const r = describe(result);
      span.setAttributes({
        ...(r.responseModel && { "gen_ai.response.model": r.responseModel }),
        ...(r.responseId && { "gen_ai.response.id": r.responseId }),
        ...(r.finishReasons && { "gen_ai.response.finish_reasons": r.finishReasons }),
        ...(r.inputTokens !== undefined && { "gen_ai.usage.input_tokens": r.inputTokens }),
        ...(r.outputTokens !== undefined && { "gen_ai.usage.output_tokens": r.outputTokens }),
      });
      if (captureContent && r.outputMessages !== undefined) span.setAttribute("gen_ai.output.messages", JSON.stringify(r.outputMessages));
      return result;
    } catch (err) {
      const e = err instanceof Error ? err : new Error(String(err));
      span.recordException(e);
      span.setAttribute("error.type", e.name);
      span.setStatus({ code: SpanStatusCode.ERROR, message: e.message });
      throw err;
    } finally {
      span.end();
    }
  });
}
```

Call site, wrapping the existing request and parse without changing their logic:

```ts
const data = await withGenAISpan(
  { operation: "chat", provider: "openai", model, serverAddress: new URL(BASE_URL).hostname, inputMessages: messages },
  async () => {
    const res = await fetch(`${BASE_URL}/chat/completions`, { /* unchanged */ });
    if (!res.ok) throw new Error(`HTTP ${res.status}`); // keep the call site's existing error handling
    return res.json();
  },
  (d) => ({
    responseModel: d.model,
    responseId: d.id,
    finishReasons: d.choices?.map((c: { finish_reason: string }) => c.finish_reason),
    inputTokens: d.usage?.prompt_tokens,
    outputTokens: d.usage?.completion_tokens,
    outputMessages: d.choices?.map((c: { message: { role: string; content: string }; finish_reason: string }) => ({
      role: c.message.role, parts: [{ type: "text", content: c.message.content }], finish_reason: c.finish_reason,
    })),
  }),
);
```

`inputMessages` should be in the semconv shape. When the call site has OpenAI-style `{role, content}` messages, map them: `messages.map((m) => ({ role: m.role, parts: [{ type: "text", content: m.content }] }))`.

## Python helper

`genai_span.py`, next to the code that makes the calls:

```python
"""Manual OpenTelemetry GenAI client spans (OTel GenAI semantic conventions)."""
import json
import os
from contextlib import contextmanager
from typing import Any, Iterator, Optional

from opentelemetry import trace
from opentelemetry.trace import SpanKind, Status, StatusCode

_tracer = trace.get_tracer("genai-manual")
_v = os.environ.get("OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", "").lower()
CAPTURE_CONTENT = _v not in ("", "false", "no_content")


class GenAISpan:
    def __init__(self, span: trace.Span) -> None:
        self.span = span

    def record_response(
        self,
        *,
        response_model: Optional[str] = None,
        response_id: Optional[str] = None,
        finish_reasons: Optional[list[str]] = None,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
        output_messages: Any = None,
    ) -> None:
        attrs = {
            "gen_ai.response.model": response_model,
            "gen_ai.response.id": response_id,
            "gen_ai.response.finish_reasons": finish_reasons,
            "gen_ai.usage.input_tokens": input_tokens,
            "gen_ai.usage.output_tokens": output_tokens,
        }
        self.span.set_attributes({k: v for k, v in attrs.items() if v is not None})
        if CAPTURE_CONTENT and output_messages is not None:
            self.span.set_attribute("gen_ai.output.messages", json.dumps(output_messages))


@contextmanager
def genai_span(
    operation: str,
    provider: str,
    model: str,
    *,
    server_address: Optional[str] = None,
    server_port: Optional[int] = None,
    input_messages: Any = None,
    system_instructions: Any = None,
    **request_attributes: Any,  # e.g. **{"gen_ai.request.temperature": 0.2}
) -> Iterator[GenAISpan]:
    attrs = {
        "gen_ai.operation.name": operation,
        "gen_ai.provider.name": provider,
        "gen_ai.request.model": model,
        **request_attributes,
    }
    if server_address:
        attrs["server.address"] = server_address
    if server_port:
        attrs["server.port"] = server_port
    if CAPTURE_CONTENT and input_messages is not None:
        attrs["gen_ai.input.messages"] = json.dumps(input_messages)
    if CAPTURE_CONTENT and system_instructions is not None:
        attrs["gen_ai.system_instructions"] = json.dumps(system_instructions)

    with _tracer.start_as_current_span(
        f"{operation} {model}", kind=SpanKind.CLIENT, attributes=attrs,
        record_exception=False, set_status_on_exception=False,
    ) as span:
        try:
            yield GenAISpan(span)
        except BaseException as exc:
            span.record_exception(exc)
            span.set_attribute("error.type", type(exc).__qualname__)
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            raise
```

Call site:

```python
with genai_span("chat", "openai", model, server_address=urlparse(BASE_URL).hostname,
                input_messages=[{"role": m["role"], "parts": [{"type": "text", "content": m["content"]}]} for m in messages]) as s:
    r = httpx.post(...)  # unchanged
    r.raise_for_status()
    data = r.json()
    s.record_response(
        response_model=data.get("model"), response_id=data.get("id"),
        finish_reasons=[c["finish_reason"] for c in data["choices"]],
        input_tokens=data.get("usage", {}).get("prompt_tokens"),
        output_tokens=data.get("usage", {}).get("completion_tokens"),
        output_messages=[{"role": "assistant", "parts": [{"type": "text", "content": c["message"]["content"]}],
                          "finish_reason": c["finish_reason"]} for c in data["choices"]],
    )
```

## Other languages

Use the same span contract with that language's OTel API: a `CLIENT` span named `{operation} {model}`, the attributes above, and errors recorded the same way. Keep it to one helper per unit.
