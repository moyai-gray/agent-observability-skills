# Vercel AI SDK (`ai`)

Last verified: 2026-11-09 (`ai` 7.0.166, `@ai-sdk/otel` 1.0.166).

The AI SDK is a **native** route: it creates its own spans on the global OTel tracer provider, so it needs no monkey-patching and works in ESM, bundled and Edge code alike. What you configure depends on the installed major version. Read the resolved version (`npm ls ai`, `pnpm why ai`, or the lockfile), not the `package.json` range.

Stay on the installed major. If it is below 7, mention in the report that v7 emits GenAI-semconv spans (`gen_ai.*`), while older versions emit the AI SDK's own `ai.*` scheme.

## Shared telemetry settings (all versions)

Put the settings every call shares in one module that call sites import, so content capture is toggled in one place. Make it safe to import from any runtime (no Node-only imports), e.g. `lib/ai-telemetry.ts`:

```ts
// Content capture follows the same env var as the official OTel GenAI instrumentations.
const v = (process.env.OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT ?? "").toLowerCase();
const capture = v !== "" && v !== "false" && v !== "no_content";

export const aiTelemetry = {
  recordInputs: capture,
  recordOutputs: capture,
} as const;
```

`references/configuration.md` sets this variable from the user's content-capture answer.

At **every** call site (`generateText`, `streamText`, `generateObject`, `streamObject`, `embed`, `embedMany`, `rerank`, and agent constructors), spread the shared settings and add a **`functionId`**: a short kebab-case name for what the call does, taken from the enclosing function, route or agent (`chat-route`, `summarize-ticket`, `support-agent`). Done when a search for those function names finds no call without telemetry settings.

## v7 and later

Telemetry is global and opt-out. Once an integration is registered, every call emits spans.

1. Install `@ai-sdk/otel`.
2. In the bootstrap, right after the OTel SDK starts, register it once:

   ```ts
   import { registerTelemetry } from "ai";
   import { OpenTelemetry } from "@ai-sdk/otel";

   registerTelemetry(new OpenTelemetry());
   ```

   In Next.js, call this inside `register()` in `instrumentation.ts` for **both** runtimes, since it has no Node-only dependencies. Only the OTel SDK start goes behind the `NEXT_RUNTIME === "nodejs"` guard (see `references/bootstrap-typescript.md`).
3. Per call, the option is `telemetry`:

   ```ts
   const result = streamText({
     model,
     messages,
     telemetry: { ...aiTelemetry, functionId: "chat-route" },
   });
   ```

   For `ToolLoopAgent` (and `WorkflowAgent`), `telemetry` goes on the **constructor**: `generate()` and `stream()` don't accept it.

   Rename any existing `experimental_telemetry` you touch to `telemetry` (the old name is a deprecated alias in v7). Drop `isEnabled: true` (it's the default) and `metadata` (removed in v7). If the project used `metadata`, map it to `runtimeContext` on the call plus `telemetry.includeRuntimeContext: { <key>: true }` (an allowlist), and mention this in the report.
4. Use `OpenTelemetry`, the GenAI-semconv integration. `LegacyOpenTelemetry` exists only to reproduce the old `ai.*` spans.

What v7 emits (instrumentation scope `gen_ai`):

| Span | Kind | Notes |
| --- | --- | --- |
| `invoke_agent {model}` | INTERNAL | Root of each call. `gen_ai.agent.name` = `functionId` |
| `step {n}` | INTERNAL | One per agent step |
| `chat {model}` | CLIENT | One per provider request, with `gen_ai.input.messages` / `gen_ai.output.messages`, usage, finish reasons |
| `execute_tool {tool}` | INTERNAL | `gen_ai.tool.call.arguments` / `.result` |
| `embeddings {model}`, `rerank {model}` | CLIENT | |

It also records the `gen_ai.client.inference.duration` histogram when a global MeterProvider exists, which the bootstrap provides. Optional extras, all off by default, are constructor flags on `new OpenTelemetry({...})`: `usage`, `providerMetadata`, `headers`, `toolChoice`, `schema`. Leave them off unless the user asks.

Requirements: v7 is ESM-only and needs Node 22 or later.

## v5 and v6

Telemetry is opt-in **per call** through `experimental_telemetry`, and it uses the global tracer provider (`trace.getTracer("ai")`). No extra package is needed beyond the OTel SDK.

```ts
const { text } = await generateText({
  model,
  prompt,
  experimental_telemetry: { isEnabled: true, ...aiTelemetry, functionId: "summarize-ticket" },
});
```

Put `isEnabled: true` in the shared constant for these versions. Spans are `ai.generateText`, `ai.generateText.doGenerate`, `ai.streamText.doStream`, `ai.toolCall`, `ai.embed`, and so on, with `ai.*` attributes plus a few `gen_ai.*` ones (`gen_ai.system`, `gen_ai.request.model`, `gen_ai.usage.*`). `experimental_telemetry.metadata` is still valid here.

For `Agent` / `ToolLoopAgent` in v6, pass `experimental_telemetry` to the constructor.

## Underlying provider SDKs

AI SDK providers (`@ai-sdk/openai`, `@ai-sdk/anthropic`, …) make their own HTTP calls and don't use the `openai` or `@anthropic-ai/sdk` packages. Don't add provider-SDK instrumentation for AI SDK call paths: it would capture nothing. If the same unit also imports `openai` directly, that is a separate call path with its own route.
