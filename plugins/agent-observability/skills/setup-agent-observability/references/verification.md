# Verification

Prove that each instrumented unit exports telemetry, and that the destination accepts every signal it is sent. Run these checks per unit, in order.

## 1. Build

Install dependencies and run the unit's typecheck or build (`tsc --noEmit`, `next build`, `python -c "import <entry module>"`, …). Fix failures before going on.

## 2. Probe the destination

For `http/protobuf` or `http/json` destinations, send each signal path an empty export request with the configured headers. An empty request is valid OTLP, so a healthy endpoint answers 2xx:

```sh
for s in traces metrics logs; do
  printf '%s ' "$s"
  curl -s -o /dev/null -w '%{http_code}\n' -X POST "$OTEL_EXPORTER_OTLP_ENDPOINT/v1/$s" \
    -H 'Content-Type: application/x-protobuf' -H "<each header from OTEL_EXPORTER_OTLP_HEADERS>" \
    --data-binary ''
done
```

Use a signal-specific endpoint as-is if one was set (`OTEL_EXPORTER_OTLP_TRACES_ENDPOINT`, …). Read the codes:

- **2xx**: the signal is accepted.
- **401 / 403**: the headers are wrong. Fix them with the user before going on.
- **404 / 405 / 415 / 501** on metrics or logs: the backend doesn't take that signal. Set `OTEL_METRICS_EXPORTER=none` or `OTEL_LOGS_EXPORTER=none` in the unit's env, and record it for the report.
- **404 on traces**: the endpoint is wrong, e.g. it already ends in `/v1/traces`. `OTEL_EXPORTER_OTLP_ENDPOINT` is the base URL, and the SDK appends `/v1/<signal>`.
- **Connection refused** on a local viewer: it isn't running. Start it (`references/configuration.md`).

For gRPC destinations, skip the probe and rely on step 4's export errors.

## 3. Trigger a real LLM call per route

Find the cheapest existing way to exercise each instrumented call path: a test that hits the real model, a script or CLI entrypoint, or the dev server plus one `curl` to the route. Run it with the unit's real env, so the API keys and `OTEL_*` values are loaded. Add `OTEL_LOG_LEVEL=debug` (Node) to surface exporter errors. Prefer a call that uses a tool, if the agent has tools, so tool spans get checked too.

If you can't make the call (missing API keys, the app needs infrastructure you can't start, no reachable entrypoint), don't fake it. Go to step 5's fallback.

## 4. Confirm export

Pick the strongest observation available:

1. **Local viewer**: query it. For Jaeger: `curl -s "http://localhost:16686/api/traces?service=$OTEL_SERVICE_NAME&limit=5"`, then check for spans whose names start with the GenAI operation (`chat`, `invoke_agent`, `execute_tool`, `embeddings`, or `ai.*` for AI SDK v5/v6).
2. **Console exporter**: rerun with `OTEL_TRACES_EXPORTER=console` (the bootstraps in this skill honour it) and inspect the printed spans directly.
3. **Remote backend**: the run shows no export errors in its output, and the user (or the backend's API, if one is documented and you have credentials) confirms the trace arrived.

For each route, check that the spans exist, sit under the right parent (LLM spans nested inside the request or agent span, not floating as separate traces), and carry `gen_ai.request.model` and token usage. Check that message content is present or absent according to the user's content-capture choice.

Watch the run's output for export errors. A 404 or `UNIMPLEMENTED` on metrics or logs means: disable that signal as in step 2.

## 5. If it can't be run

Tell the user plainly that runtime verification didn't happen, and why. Give them the exact command to run and what to look for (the step-4 check against their backend or a local viewer).
