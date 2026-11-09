# Instrumentation matrix

Last verified: 2026-11-09 against PyPI, npm and the projects' repos.

Each row maps a library to its **route** and package. Version ranges matter: compare the project's **resolved** library version (lockfile, `npm ls`, `uv pip show`, `pip show`) against the row, and when it falls outside, take the next row for that library. Re-check every package with the registry before installing (SKILL.md, Step 2).

Content-capture knobs per route are in `references/configuration.md`.

## Rules that apply to every row

- **One instrumentation per library.** Two packages instrumenting the same library produce duplicate spans. Before adding one, check what is already active: an existing `getNodeAutoInstrumentations()` (it bundles `@opentelemetry/instrumentation-openai`), `opentelemetry-instrument` with installed instrumentations, or an SDK's built-in tracing.
- **Framework over SDK.** When a call path goes through a framework, instrument the framework's row and not the underlying provider SDK. The exception is provider SDKs with **built-in** tracing (Anthropic, below): they emit spans by themselves under any framework. Turn their spans off with `ANTHROPIC_OPEN_TELEMETRY=false` when the framework's spans already carry the model and token usage.
- **Registering.** Python instrumentors are `XInstrumentor().instrument()` calls placed after the providers in `telemetry.py`. JS instrumentations go in the `instrumentations: [...]` array of the `NodeSDK` (see `references/bootstrap-typescript.md`, which also covers ESM and bundlers).
- **Never the vendor bootstraps.** Use OpenLLMetry and OpenInference only as individual instrumentation packages. Never `traceloop-sdk` / `Traceloop.init`, `@traceloop/node-server-sdk`, `phoenix.otel.register`, or `arize-otel`.

## Python: provider SDKs

| Library | Route | Package | Register |
| --- | --- | --- | --- |
| `anthropic` ≥ 2.0 | native | none (built in, on once a tracer provider is set) | nothing. Spans only, no metrics |
| `anthropic` 0.51 – < 2.0 | official | `opentelemetry-instrumentation-genai-anthropic` | `from opentelemetry.instrumentation.genai.anthropic import AnthropicInstrumentor` |
| `openai` 1.26 – < 4 | official | `opentelemetry-instrumentation-genai-openai` | `from opentelemetry.instrumentation.genai.openai import OpenAIInstrumentor` |
| `google-genai` | official | `opentelemetry-instrumentation-google-genai` | `from opentelemetry.instrumentation.google_genai import GoogleGenAiSdkInstrumentor` |
| `boto3` / `aioboto3` Bedrock Runtime and Agent Runtime | official | `opentelemetry-instrumentation-genai-bedrock` | `from opentelemetry.instrumentation.genai.bedrock import BedrockInstrumentor` |
| `google-cloud-aiplatform` (`vertexai`) | official | `opentelemetry-instrumentation-vertexai>=2.0b0` | `from opentelemetry.instrumentation.vertexai import VertexAIInstrumentor` |
| `mistralai` ≥ 3.0 | native | none (built in, off by default) | set `MISTRAL_SDK_TELEMETRY=global` so it uses the app's provider. Never `dedicated` or `true`: both send traces to `api.mistral.ai`. Spans include content, with no off switch. The client import moved to `from mistralai.client import Mistral` in 3.x |
| `mistralai` < 2.0 | community | `opentelemetry-instrumentation-mistralai` (OpenLLMetry) | `from opentelemetry.instrumentation.mistralai import MistralAiInstrumentor`. The SDK also emits its own sparse spans, so expect two spans per call; say so in the report |
| `mistralai` 2.x | manual | (OpenLLMetry's package fails to import on ≥ 2.0) | `references/manual-spans.md`, or suggest upgrading to 3.x |
| `cohere` | community | `opentelemetry-instrumentation-cohere` | `…cohere import CohereInstrumentor` |
| `groq` | community | `opentelemetry-instrumentation-groq` | `…groq import GroqInstrumentor` |
| `ollama` | community | `opentelemetry-instrumentation-ollama` | `…ollama import OllamaInstrumentor` |
| `together` | community | `opentelemetry-instrumentation-together` | `…together import TogetherAiInstrumentor` |
| `replicate` | community | `opentelemetry-instrumentation-replicate` | `…replicate import ReplicateInstrumentor` |
| `ibm-watson-machine-learning` | community | `opentelemetry-instrumentation-watsonx` | `…watsonx import WatsonxInstrumentor` |
| `voyageai` | community | `opentelemetry-instrumentation-voyageai` | `…voyageai import VoyageAIInstrumentor` |
| `transformers` (local pipelines) | community | `opentelemetry-instrumentation-transformers` | `…transformers import TransformersInstrumentor` |
| boto3 SageMaker endpoints | community | `opentelemetry-instrumentation-sagemaker` | `…sagemaker import SageMakerInstrumentor` |

**PyPI name traps:**

- `opentelemetry-instrumentation-openai`, `-anthropic` and `-langchain` (no `genai-`) are **OpenLLMetry** packages, not the official ones. Always use the `-genai-` names in the official rows.
- `opentelemetry-instrumentation-vertexai` is one PyPI project with two publishers. Plain installs resolve to OpenLLMetry's 0.x. The official build is a pre-release, so the `>=2.0b0` specifier is required.
- Legacy `opentelemetry-instrumentation-openai-v2` is the frozen predecessor of `-genai-openai`. If a project already has it, replace it with `-genai-openai` rather than adding the new one beside it.
- OpenLLMetry and official packages register the same auto-instrumentation entry-point names (`openai`, `anthropic`, `langchain`, `openai_agents`). Never install both for one library.

**Bedrock:** `opentelemetry-instrumentation-botocore` also emits GenAI spans for Bedrock. If the project already uses botocore instrumentation, don't add `-genai-bedrock` as well. Note in the report that the two may overlap.

## Python: frameworks and gateways

| Framework | Route | How |
| --- | --- | --- |
| Pydantic AI | native | `from pydantic_ai import Agent, InstrumentationSettings`, then `Agent.instrument_all(InstrumentationSettings(include_content=<capture>))` in `telemetry.py`. Uses the global providers; no Logfire needed. The `Agent(instrument=True)` argument no longer exists (2.x) |
| Google ADK | native | Uses the global provider automatically once `telemetry.py` has run. Content: `ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS` (default on). Don't call `maybe_set_otel_providers()`: `telemetry.py` owns the providers |
| Strands Agents | native | Install `strands-agents[otel]`. It uses the global provider; don't call `StrandsTelemetry().setup_otlp_exporter()`. Set `OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental` |
| Semantic Kernel | native | `SEMANTICKERNEL_EXPERIMENTAL_GENAI_ENABLE_OTEL_DIAGNOSTICS=true`; content: `SEMANTICKERNEL_EXPERIMENTAL_GENAI_ENABLE_OTEL_DIAGNOSTICS_SENSITIVE=true` |
| LiteLLM (library) | native | `litellm.callbacks = ["otel"]` after `import telemetry`. In verification, confirm its spans carry this unit's `service.name`. If they don't (it built its own provider), switch to OpenLLMetry `opentelemetry-instrumentation-litellm` / `LiteLLMInstrumentor` |
| Haystack | native | `pip install opentelemetry-haystack`; `from haystack import tracing`; `from haystack_integrations.tracing.opentelemetry import OpenTelemetryTracer`; `tracing.enable_tracing(OpenTelemetryTracer(trace.get_tracer("haystack")))`. Content: `HAYSTACK_CONTENT_TRACING_ENABLED=true` |
| Claude Agent SDK | native (via its CLI) | Env for the spawned CLI: `CLAUDE_CODE_ENABLE_TELEMETRY=1`, `OTEL_METRICS_EXPORTER=otlp`, `OTEL_LOGS_EXPORTER=otlp`. Traces are beta: add `CLAUDE_CODE_ENHANCED_TELEMETRY_BETA=1` and `OTEL_TRACES_EXPORTER=otlp`. Install `claude-agent-sdk[otel]` so the active span propagates to the CLI via `TRACEPARENT`. Content: `OTEL_LOG_USER_PROMPTS=1`, `OTEL_LOG_TOOL_DETAILS=1`, `OTEL_LOG_TOOL_CONTENT=1` |
| LangChain / LangGraph | official | `opentelemetry-instrumentation-genai-langchain`, `from opentelemetry.instrumentation.genai.langchain import LangChainInstrumentor` (covers LangGraph). It declares a dependency on the `langchain` package. Projects with only `langchain-core` / `langgraph` installed need `LangChainInstrumentor().instrument(skip_dep_check=True)`, otherwise it logs an error and instruments nothing. LangSmith's OTel mode is a vendor path; leave it alone |
| LlamaIndex | official | `opentelemetry-instrumentation-genai-llama-index`, `…genai.llama_index import LlamaIndexInstrumentor`. Skip `llama-index-observability-otel`: it builds its own provider |
| OpenAI Agents SDK | official | `opentelemetry-instrumentation-genai-openai-agents`, `…genai.openai_agents import OpenAIAgentsInstrumentor`, then `.instrument(disable_openai_trace_export=True)` so traces stop going to OpenAI |
| DSPy | official | `opentelemetry-instrumentation-genai-dspy`, `…genai.dspy import DSPyInstrumentor` |
| Agno | official | `opentelemetry-instrumentation-genai-agno`, `…genai.agno import AgnoInstrumentor` |
| smolagents | official | `opentelemetry-instrumentation-genai-smolagents`, `…genai.smolagents import SmolagentsInstrumentor` |
| Portkey | official | `opentelemetry-instrumentation-genai-portkey`, `…genai.portkey import PortkeyInstrumentor` |
| Qwen-Agent | official | `opentelemetry-instrumentation-genai-qwen-agent`, `…genai.qwen_agent import QwenAgentInstrumentor` |
| CrewAI | community | `opentelemetry-instrumentation-crewai`, `from opentelemetry.instrumentation.crewai import CrewAIInstrumentor`. Also set `CREWAI_DISABLE_TELEMETRY=true` (CrewAI's own analytics run on a private provider) |
| MCP client sessions | community | `opentelemetry-instrumentation-mcp`, `…mcp import McpInstrumentor`. Only as a supplement: MCP calls aren't inference |

The official `-genai-crewai`, `-genai-ollama` and `-genai-claude-agent-sdk` packages exist in the repo but weren't on PyPI at last check. Prefer them over the rows above once the registry has them.

## JavaScript / TypeScript: provider SDKs

| Library | Route | Package | Register |
| --- | --- | --- | --- |
| `ai` (Vercel AI SDK) | native | `@ai-sdk/otel` for v7+, none for v5/v6 | see `references/ai-sdk.md` |
| `@anthropic-ai/sdk` ≥ 0.134 (incl. 1.x) | native | none (built in, on once a tracer provider is registered) | nothing. Spans only |
| `@anthropic-ai/sdk` < 0.134 | community | `@traceloop/instrumentation-anthropic` | `new AnthropicInstrumentation({ traceContent: <capture> })` |
| `openai` 4.19 – < 7 | official | `@opentelemetry/instrumentation-openai` | `new OpenAIInstrumentation()` |
| `openai` ≥ 7 | community | `@arizeai/openinference-instrumentation-openai` (OpenInference: neither the official nor the OpenLLMetry package supports v7 yet) | `new OpenAIInstrumentation()` from that package. Spans use OpenInference attributes, not `gen_ai.*`: say so in the report |
| `@aws-sdk/client-bedrock-runtime` | official | `@opentelemetry/instrumentation-aws-sdk` | `new AwsInstrumentation()` |
| `@google/genai` | community | `@traceloop/instrumentation-google-generativeai` | `new GenAIInstrumentation({ traceContent: <capture> })` |
| `@google-cloud/vertexai` | community | `@traceloop/instrumentation-vertexai` | `new VertexAIInstrumentation({ traceContent: <capture> })` |
| `cohere-ai` | community | `@traceloop/instrumentation-cohere` | `new CohereInstrumentation({ traceContent: <capture> })` |
| `together-ai` | community | `@traceloop/instrumentation-together` | `new TogetherInstrumentation({ traceContent: <capture> })` |

The official `@opentelemetry/instrumentation-anthropic` (0.2.0) records no response, usage or content data yet. That is why the old-Anthropic row uses OpenLLMetry.

The official openai instrumentation follows semconv 1.36 for Chat Completions (`gen_ai.system`, per-message log events) and 1.38 for the Responses API. Mention this in the report when the project uses Chat Completions.

## JavaScript / TypeScript: frameworks

| Framework | Route | How |
| --- | --- | --- |
| Mastra | native | `@mastra/observability` with `bridge: new OtelBridge()` from `@mastra/otel-bridge`, so Mastra's spans go through the global provider from the bootstrap. The bridge is experimental. If it fails in verification, use `new OtelExporter({ provider: { custom: { endpoint, protocol: "http/protobuf", headers } } })` from `@mastra/otel-exporter`, filled from the `OTEL_EXPORTER_OTLP_*` env values. Content: `tracingOptions: { hideInput, hideOutput }` |
| Claude Agent SDK (TS) | native (via its CLI) | Same env vars as the Python row |
| Strands Agents (TS) | native | uses the global provider once the bootstrap runs; don't call `setupTracer()` |
| OpenAI Agents SDK (`@openai/agents`) | official | `@opentelemetry/instrumentation-openai-agents`, `new OpenAIAgentsInstrumentation({ captureMessageContent: <capture> })`. Check its README for how to stop the SDK's own export to OpenAI, and apply it |
| LangChain.js / LangGraph.js | community | `@traceloop/instrumentation-langchain`: `new LangChainInstrumentation({ traceContent: <capture> })`. It hooks the callback manager; in ESM, call `.manuallyInstrument({ callbackManagerModule })` with `import * as callbackManagerModule from "@langchain/core/callbacks/manager"` |
| LlamaIndex.TS | community | `@traceloop/instrumentation-llamaindex`: `new LlamaIndexInstrumentation({ traceContent: <capture> })` |

## Not inference

These are borderline for the Step 1 gate, not call paths: MCP servers (`@modelcontextprotocol/sdk`, `mcp`/FastMCP server code), vector databases, and HTTP calls to a hosted agent platform. OpenLLMetry has vector-DB and MCP packages that can supplement a real call path when the user asks.
