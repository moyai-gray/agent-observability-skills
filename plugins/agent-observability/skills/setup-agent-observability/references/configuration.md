# Configuration

Last verified: 2026-11-09.

All destination settings are standard OpenTelemetry env vars, read by the bootstraps in this skill. Code stays destination-agnostic, so switching backends is an env change.

## Env vars to write

| Variable | Value |
| --- | --- |
| `OTEL_SERVICE_NAME` | the unit's name, e.g. `support-agent-api` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | the destination's **base** URL, without `/v1/traces` (the SDK appends `/v1/<signal>`) |
| `OTEL_EXPORTER_OTLP_PROTOCOL` | `http/protobuf` (default) or `grpc` |
| `OTEL_EXPORTER_OTLP_HEADERS` | auth headers as `key=value,key2=value2`. Values are URL-encoded, so a space is `%20`: `Authorization=Bearer%20sk-…` |
| `OTEL_TRACES_EXPORTER` / `OTEL_METRICS_EXPORTER` / `OTEL_LOGS_EXPORTER` | leave unset (means `otlp`). Set to `none` only for a signal the destination rejects (`references/verification.md`) |
| `OTEL_RESOURCE_ATTRIBUTES` | optional, e.g. `deployment.environment.name=production` |
| content-capture knobs | see below |

If the destination gives per-signal URLs that don't follow the `/v1/<signal>` pattern, use `OTEL_EXPORTER_OTLP_{TRACES,METRICS,LOGS}_ENDPOINT` instead. Those are used exactly as written.

## Where to write them

- **Secret values** (headers holding keys or tokens) go into the unit's existing gitignored env file: `.env.local` for Next.js, otherwise `.env` if `.gitignore` covers it. If no gitignored env file exists, create `.env` and add it to `.gitignore`. Check with `git check-ignore <file>` before writing a secret. Never commit one.
- **Every key** gets a placeholder in `.env.example` (create it if missing), with a one-line comment for non-obvious ones.
- **Make sure the env file is loaded before the bootstrap reads it.** Next.js, Vite and most frameworks load `.env*` before `instrumentation.ts` runs. Plain Node doesn't: use `node --env-file=.env` (Node 20.6+), or match how the project already loads env. A Python `telemetry.py` imported before the app's `load_dotenv()` call reads nothing: if the project uses `python-dotenv`, call `load_dotenv()` at the top of `telemetry.py`. Pydantic settings classes don't populate `os.environ`, so the same applies.
- **Deploy environments** (Vercel, Fly, Render, k8s Secrets, CI): don't edit these. List the exact variables the user must set there in the report.

## Content capture

Apply the user's one answer to every knob that applies to the unit's routes, so all routes behave the same. Unknown knobs mean an unlisted route: look for its documented flag before falling back to its default.

| Route | Knob | Capture on | Capture off | Default if unset |
| --- | --- | --- | --- | --- |
| Official Python `-genai-*` and `google-genai` | `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT` | `SPAN_ONLY` | `NO_CONTENT` | off. `true` is invalid here and means off |
| Official Python legacy (`-openai-v2`, `botocore` Bedrock) | same variable | `true` | `false` | off |
| Official JS (`instrumentation-openai`, `-openai-agents`), Java, .NET `Microsoft.Extensions.AI` | same variable | `true` | `false` | off |
| AI SDK (via the shared constant in `references/ai-sdk.md`) | same variable | the value for the unit's language above | `false` | off |
| Manual helper (`references/manual-spans.md`) | same variable | the value for the unit's language above | `false` | off |
| Anthropic SDK built-in tracing (Python and JS) | `ANTHROPIC_OPEN_TELEMETRY_TRACES_CONTENT_MODE` | `content` | `metadata_only` | off |
| OpenLLMetry Python packages | `TRACELOOP_TRACE_CONTENT` | `true` | `false` | **on** |
| OpenLLMetry JS packages | constructor option `traceContent` (the env var is ignored) | `true` | `false` | **on** |
| OpenInference | `OPENINFERENCE_HIDE_INPUTS` and `OPENINFERENCE_HIDE_OUTPUTS` | `false` | `true` | **on** |
| Pydantic AI | `InstrumentationSettings(include_content=…)` | `True` | `False` | on |
| Google ADK | `ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS` | `true` | `false` | on |
| Semantic Kernel | `SEMANTICKERNEL_EXPERIMENTAL_GENAI_ENABLE_OTEL_DIAGNOSTICS_SENSITIVE` | `true` | `false` | off |
| Haystack | `HAYSTACK_CONTENT_TRACING_ENABLED` | `true` | `false` | off |
| LiteLLM | `litellm.turn_off_message_logging` | `False` | `True` | on |
| Mastra | `tracingOptions: { hideInput, hideOutput }` | `false` | `true` | on |
| Claude Agent SDK (CLI) | `OTEL_LOG_USER_PROMPTS`, `OTEL_LOG_TOOL_DETAILS`, `OTEL_LOG_TOOL_CONTENT` | `1` | unset | off |

Where a knob is a code option (`traceContent`, `include_content`, …), derive it from `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT` in code, rather than hardcoding it, so the env stays the single switch:

```ts
const v = (process.env.OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT ?? "").toLowerCase();
const captureContent = v !== "" && v !== "false" && v !== "no_content";
```

```python
_v = os.environ.get("OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", "").lower()
capture_content = _v not in ("", "false", "no_content")
```

**Defaults that are on:** OpenLLMetry, OpenInference and several frameworks capture content unless told not to. When the user says "off", set those knobs explicitly.

## Local backends

When the user has no backend yet, or wants to look locally first, offer:

- **Jaeger** (traces only, lightest; the default offer):
  `docker run -d --name jaeger -p 16686:16686 -p 4317:4317 -p 4318:4318 jaegertracing/jaeger:latest`
  Set the endpoint to `http://localhost:4318` (http) or `http://localhost:4317` (grpc), and give the UI as http://localhost:16686. Verification will turn off metrics and logs, which Jaeger rejects.
- **Grafana `otel-lgtm`** (traces, metrics and logs in one container; heavier):
  `docker run -d --name lgtm -p 3000:3000 -p 4317:4317 -p 4318:4318 grafana/otel-lgtm:latest`
  Same endpoints. UI at http://localhost:3000.

Check `docker info` before offering to start either one. Without Docker, offer them as something the user runs, and verify with the console exporter in the meantime. Start the container yourself only if the user agrees. Either way the env points at `localhost`, so moving to a real backend later means changing only `OTEL_EXPORTER_OTLP_ENDPOINT` and `OTEL_EXPORTER_OTLP_HEADERS`.
