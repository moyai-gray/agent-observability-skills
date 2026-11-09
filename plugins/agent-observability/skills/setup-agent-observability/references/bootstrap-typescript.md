# Bootstrap: TypeScript / JavaScript (Node)

Last verified: 2026-11-09 (`@opentelemetry/sdk-node` 0.301.0, SDK 3.1, `@opentelemetry/api` 1.10).

One `NodeSDK` per process, constructed **without exporters**. NodeSDK then reads `OTEL_{TRACES,METRICS,LOGS}_EXPORTER` (`otlp` by default, `console`, `none`) and `OTEL_EXPORTER_OTLP_*` itself, so the destination and per-signal switches live entirely in env. Passing `traceExporter`, `spanProcessors`, `metricReaders` or `logRecordProcessors` turns off the env lookup for that signal, so don't pass them in new setups.

## Packages

- `@opentelemetry/sdk-node` (includes the OTLP http/proto/grpc exporters for all three signals)
- `@opentelemetry/api` (`trace`, `metrics` and `logs` all live here in 1.10)
- the instrumentation packages from the plan

`@opentelemetry/instrumentation` 0.301 requires Node ≥ 22.15. On older Node, find the newest compatible versions with `npm view @opentelemetry/sdk-node@<version> engines` and pin all `@opentelemetry/*` packages to one release line. The AI SDK v7 needs Node 22 anyway.

## Existing setup

If the unit already starts OTel, extend it rather than adding a second SDK. Keep its existing exporters, service name and instrumentations as they are. Replacing or removing one changes where the team's existing telemetry goes, so propose it and wait for a yes. Also say what you'd gain, e.g. "the hard-coded exporter ignores `OTEL_EXPORTER_OTLP_PROTOCOL` and the `OTEL_*_EXPORTER` switches".

- **Existing `NodeSDK`**: add the new instrumentations to its `instrumentations` array. `getNodeAutoInstrumentations()` already includes `@opentelemetry/instrumentation-openai` (supports `openai` < 7). Don't add it twice: set its content knob and you're done. If the existing setup passes exporters in code and the destination is new, add a span processor for the new destination next to the existing one, built from env (`new BatchSpanProcessor(new OTLPTraceExporter())` reads `OTEL_EXPORTER_OTLP_*`).
- **`@vercel/otel`**: add instrumentations through `registerOTel({ instrumentations: [...] })`. It reads only the trace-related OTLP env vars: metrics and logs need `metricReaders` / `logRecordProcessors` passed explicitly. It also pins its `@opentelemetry/*` peers to the pre-3.0 line (`<0.300`, `<3.0.0`), so match new OTel packages to those ranges.
- **Sentry, Datadog `dd-trace`, New Relic, other vendor agents**: these own the tracer provider. Show the user what you found and ask whether to register the instrumentations through the vendor's hook (e.g. Sentry's `openTelemetryInstrumentations` / `openTelemetrySpanProcessors` options) or stop. Never start a second SDK beside them.

## `instrumentation.ts`

Match the project's module system and language: `.ts` for TypeScript, `.mjs` for ESM JavaScript, `.cjs` for CommonJS. Put it next to the entrypoint.

```ts
// OpenTelemetry bootstrap. Loaded before the app (see "Loading it first").
// Configured entirely by OTEL_* env vars: OTEL_SERVICE_NAME, OTEL_EXPORTER_OTLP_ENDPOINT,
// OTEL_EXPORTER_OTLP_HEADERS, OTEL_EXPORTER_OTLP_PROTOCOL, OTEL_{TRACES,METRICS,LOGS}_EXPORTER.
import { logs, metrics, trace } from "@opentelemetry/api";
import { NodeSDK } from "@opentelemetry/sdk-node";

const sdk = new NodeSDK({
  instrumentations: [
    // from the plan, e.g. new OpenAIInstrumentation()
  ],
});
sdk.start();

/** Export everything buffered so far. Call at the end of serverless invocations and scripts. */
export async function flushTelemetry(): Promise<void> {
  const tracerProvider = trace.getTracerProvider() as unknown as { getDelegate?: () => unknown };
  const providers = [tracerProvider.getDelegate?.() ?? tracerProvider, metrics.getMeterProvider(), logs.getLoggerProvider()];
  await Promise.all(providers.map((p) => (p as { forceFlush?: () => Promise<void> }).forceFlush?.()));
}

/** Flush and stop telemetry. Call once on process shutdown. */
export const shutdownTelemetry = (): Promise<void> => sdk.shutdown();
```

For the AI SDK v7, add `registerTelemetry(new OpenTelemetry())` right after `sdk.start()` (`references/ai-sdk.md`).

### Shutdown

Batched telemetry is lost if the process exits without flushing.

- **Long-running servers**: if the app already handles `SIGTERM`/`SIGINT`, add `await shutdownTelemetry()` inside its handler. If it doesn't, add one to the bootstrap: `process.once("SIGTERM", () => shutdownTelemetry().finally(() => process.exit(0)))`. Adding a SIGTERM listener disables Node's default exit, which is why it calls `process.exit`.
- **Scripts and CLIs**: `await shutdownTelemetry()` before the script ends.
- **Serverless** (Lambda, Vercel functions, Cloud Functions): `await flushTelemetry()` before the handler returns. In Next.js route handlers on Vercel, use `after(flushTelemetry)` from `next/server` so the flush doesn't delay the response. For streamed responses, `after` runs once the stream has finished.

## Loading it first

The bootstrap must run before any module that imports an instrumented library. How depends on how the unit starts. Update **every** start path you found in the inventory (package.json scripts, Dockerfile `CMD`, Procfile, PM2 config, serverless handler config).

| Start command | Change to |
| --- | --- |
| `node dist/index.js` | `node --import ./dist/instrumentation.js dist/index.js` |
| `tsx src/index.ts` | `tsx --import ./src/instrumentation.ts src/index.ts` |
| `ts-node src/index.ts` | add `--require ./src/instrumentation.ts` (CJS) |
| a framework CLI (`nest start`, `remix-serve`, …) | `NODE_OPTIONS="--import ./dist/instrumentation.js"` in the script |
| AWS Lambda | `NODE_OPTIONS=--import ./instrumentation.mjs` in the function env, plus `flushTelemetry` in the handler |
| Next.js | see the Next.js section |

`--import` works for both CJS and ESM apps. Prefer it over "import the bootstrap at the top of the entrypoint", which only works in CJS (ESM evaluates every import before the module body runs).

### ESM and monkey-patching instrumentations

Native routes (AI SDK, Anthropic built-in tracing) need no patching. Patching instrumentations (official `instrumentation-openai`, OpenLLMetry, OpenInference) can only patch ESM imports through the loader hook, so add it before `--import` when the unit is ESM (`"type": "module"`, `.mjs`, or TS compiled to ESM):

```sh
node --experimental-loader=@opentelemetry/instrumentation/hook.mjs --import ./instrumentation.mjs app.mjs
```

A CJS app whose ESM dependencies import the patched library needs the hook too. If the hook can't be used (exotic runners, bundlers), call the instrumentation's `manuallyInstrument(module)` instead, passing the imported library module. OpenLLMetry and OpenInference instrumentations support this:

```ts
import * as anthropicModule from "@anthropic-ai/sdk";
const anthropicInstrumentation = new AnthropicInstrumentation({ traceContent: captureContent });
anthropicInstrumentation.manuallyInstrument(anthropicModule);
```

### Bundled code

Monkey-patching can't see a library that the bundler inlined (Next.js server bundles, esbuild/webpack/ncc Lambda bundles). Mark the instrumented library as external (Next.js `serverExternalPackages`, esbuild `--external:openai`, webpack `externals`) or use `manuallyInstrument`. Verification will show whether spans appear.

## Next.js

`instrumentation.ts` in the project root (or `src/`) exports `register()`. It is stable in Next 15+, so no `experimental.instrumentationHook` flag is needed; remove it if present. Next also emits its own request spans, which become the parents of the LLM spans.

**Default: `@opentelemetry/sdk-node` in the Node.js runtime.**

```ts
// instrumentation.ts
export async function register() {
  if (process.env.NEXT_RUNTIME === "nodejs") {
    await import("./instrumentation.node");
  }
  // AI SDK v7 only, for both runtimes:
  // const { registerTelemetry } = await import("ai");
  // const { OpenTelemetry } = await import("@ai-sdk/otel");
  // registerTelemetry(new OpenTelemetry());
}
```

`instrumentation.node.ts` holds the `instrumentation.ts` body from above (NodeSDK, `flushTelemetry`, `shutdownTelemetry`). Import `flushTelemetry` from it only in Node-runtime route handlers.

Packages patched by an instrumentation must be in `serverExternalPackages` in `next.config.*`, or Next bundles them and the patch misses. The AI SDK and Anthropic built-in tracing don't need this.

**Edge runtime.** If LLM calls run in Edge routes (`export const runtime = "edge"`, or middleware), NodeSDK can't run there. Use `@vercel/otel` instead, for **both** runtimes, so there's one setup:

```ts
// instrumentation.ts
import { registerOTel } from "@vercel/otel";

export function register() {
  registerOTel({ serviceName: process.env.OTEL_SERVICE_NAME });
}
```

It reads `OTEL_EXPORTER_OTLP_*` for traces and flushes via `waitUntil` on Vercel by itself. It doesn't export metrics or logs from env. Say in the report that only traces are exported. Also use `@vercel/otel` when the project already has it installed.

## Short-lived processes

For a CLI or script entrypoint, `await shutdownTelemetry()` at the end (or in a `finally`) is required. Otherwise the batch processors drop the spans when the process exits.
