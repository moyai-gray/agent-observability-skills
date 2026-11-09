# Bootstrap: other languages (best effort)

Last verified: 2026-11-09.

TypeScript and Python have tested recipes in this skill. For anything else, follow the language's current OTel getting-started page (`https://opentelemetry.io/docs/languages/<lang>/`) for the SDK and OTLP exporter setup, keeping this skill's rules:

- One SDK setup per process; extend an existing one.
- Env-driven configuration: standard `OTEL_*` vars, never a hardcoded endpoint.
- All three signals where the language's SDK supports them (logs are still missing or experimental in some).
- Route order from SKILL.md Step 2; the manual span contract in `references/manual-spans.md` when nothing covers the library.

Tell the user up front that this language is best-effort.

## Java

- **Bootstrap:** the OTel Java agent (`-javaagent:opentelemetry-javaagent.jar`, added to the start command or `JAVA_TOOL_OPTIONS`) is the env-driven default and exports all three signals over OTLP. With an existing Spring Boot Micrometer/OTel setup, extend that instead.
- **official:** the agent instruments the `openai-java` SDK (1.1+) and Bedrock through AWS SDK v2. For library-only setups use `io.opentelemetry.instrumentation:opentelemetry-openai-java-1.1` (`OpenAITelemetry.builder(openTelemetry).build().instrument(client)`).
- **native:** Spring AI emits Micrometer observations with `gen_ai.*` keys. Its content flags (`spring.ai.chat.observations.log-prompt`, `…log-completion`, `spring.ai.tools.observations.include-content`) are off by default. Export them through the Micrometer OTel bridge and OTLP exporter in the existing Spring Boot setup.
- **Content:** `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true` (system property `otel.instrumentation.genai.capture-message-content`).

## .NET

- **Bootstrap:** `OpenTelemetry.Extensions.Hosting` plus `OpenTelemetry.Exporter.OpenTelemetryProtocol`, with `.WithTracing(...)`, `.WithMetrics(...)` and `.WithLogging(...)` and `.UseOtlpExporter()`, which reads `OTEL_EXPORTER_OTLP_*`.
- **native, OpenAI .NET (`OpenAI` package):** experimental. Enable it with `OPENAI_EXPERIMENTAL_ENABLE_OPEN_TELEMETRY=true` (or `AppContext.SetSwitch("OpenAI.Experimental.EnableOpenTelemetry", true)`), then `.AddSource("OpenAI.*")` and `.AddMeter("OpenAI.*")`.
- **native, Microsoft.Extensions.AI:** `chatClientBuilder.UseOpenTelemetry()`, then `.AddSource("Experimental.Microsoft.Extensions.AI")` and `.AddMeter("Experimental.Microsoft.Extensions.AI")`. Content follows `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true`.
- **native, Azure.AI.Inference:** `AZURE_EXPERIMENTAL_ENABLE_ACTIVITY_SOURCE=true`, then `.AddSource("Azure.AI.Inference.*")`.
- **native, Semantic Kernel:** AppContext switches `Microsoft.SemanticKernel.Experimental.GenAI.EnableOTelDiagnostics` (and `…Sensitive` for content), then `.AddSource("Microsoft.SemanticKernel*")`.

## Go

- **Bootstrap:** `go.opentelemetry.io/otel/sdk` with `go.opentelemetry.io/contrib/exporters/autoexport`, which picks exporters from `OTEL_{TRACES,METRICS,LOGS}_EXPORTER`. Set the tracer, meter and logger providers globally in `main` and shut them down on exit.
- **No official GenAI instrumentation** exists in `opentelemetry-go-contrib`. Provider SDK calls (`openai-go`, `anthropic-sdk-go`, …) go to the **manual** route: a small helper following `references/manual-spans.md`. First check whether the SDK in use has grown built-in tracing (search its docs for "OpenTelemetry"), and prefer that if so.

## Others (Ruby, PHP, Rust, Elixir, …)

Use the language's OTel SDK with OTLP, then check the SDK in use for built-in tracing, then the OTel registry (`https://opentelemetry.io/ecosystem/registry/?s=<library>`) for an instrumentation, and fall back to the manual route.
