---
name: setup-agent-observability
description: Wire vendor-neutral OpenTelemetry (traces, metrics, logs over OTLP) into an LLM app or agent. Detects how inference is called (Vercel AI SDK, provider SDKs like openai or anthropic, agent frameworks, raw HTTP) and installs the matching GenAI instrumentation. Use when the user wants observability, tracing, telemetry or OTel for their agent or LLM calls.
license: MIT
---

# Setup agent observability

Instrument the project's LLM calls with OpenTelemetry and export traces, metrics and logs over OTLP to whatever backend the user picks. **Vendor-neutral** is the rule at every choice: OpenTelemetry-maintained components and standard `OTEL_*` configuration first, whatever vendor SDKs the project already depends on.

Skill version: `0.1.0`

## Loading references

Detail lives in `references/`, loaded only when a step points at it. To load `references/<file>`:

1. If `${CLAUDE_SKILL_DIR}/references/<file>` exists (the `references/` folder beside this SKILL.md), read it.
2. Otherwise fetch `https://raw.githubusercontent.com/moyai-ai/agent-observability-skills/v0.1.0/plugins/agent-observability/skills/setup-agent-observability/references/<file>` (`curl -fsSL`, or your web-fetch tool).
3. If that fails, fetch the same path from `main` instead of `v0.1.0`, and tell the user the pinned version was unavailable.

If a reference can't be loaded at all, stop and tell the user. Package names and APIs in this space change monthly, so the references, not memory, are the source of truth.

## Asking the user

Ask with AskUserQuestion when available (batch one step's questions into one call, recommended option first), otherwise as a short numbered list in chat. Wait for the answers before acting on them.

## Step 1: Inventory

Survey the project and build an **inventory**, one entry per **unit** (a separately launched program: app, service, worker, CLI, notebook). For each unit record:

- language, runtime and framework (Next.js, FastAPI, Express, Lambda, …), package manager, entrypoint(s), and how it is started
- every **call path**, meaning each way the unit performs LLM inference: the Vercel AI SDK, a provider SDK (`openai`, `@anthropic-ai/sdk`, `google-genai`, `boto3` bedrock-runtime, …), an agent framework (LangChain/LangGraph, LlamaIndex, Mastra, Pydantic AI, OpenAI Agents SDK, CrewAI, …), a gateway library (LiteLLM), or raw HTTP to an inference API (`fetch`/`axios`/`requests`/`httpx` against `/chat/completions`, `/messages`, `:generateContent`, …). Record each library's resolved version (from the lockfile or installed packages), and list the call sites for raw-HTTP and AI SDK call paths.
- existing telemetry: a registered OTel SDK/provider, `@vercel/otel`, Sentry, Datadog `dd-trace`, Logfire, Langfuse/LangSmith/Traceloop SDKs, an existing `instrumentation.ts` or `telemetry.py`
- env mechanism: `.env*` files and their `.gitignore` coverage, deploy config (`vercel.json`, `fly.toml`, `Dockerfile`, k8s manifests)

Search for endpoint paths and base URLs as well as imports: an OpenAI-compatible client pointed at Ollama, vLLM or a LiteLLM proxy is still inference. Done when every unit's entry is filled and every file that imports an LLM library or hits an inference endpoint maps to a call path.

Then gate:

- **No inference anywhere**: tell the user that agent observability doesn't make sense for this project because it makes no LLM calls, say what you searched, and stop.
- **Borderline** (an MCP or tool server that models call but that never calls one itself; an app that only calls a hosted agent platform; inference that lives in another repo): explain what you found and ask whether to proceed with manual spans around those calls, or stop.
- **Several units with call paths**: list each unit with its call paths and ask which to instrument (default: all).

## Step 2: Plan

Load `references/instrumentation-matrix.md`. Resolve every call path in the chosen units to one **route**, taking the first that applies to the library's **resolved** version (rows are version-ranged):

1. **native**: the library, SDK or framework emits OTel itself (AI SDK, the Anthropic SDKs, Pydantic AI, …). Configure it.
2. **official**: an OpenTelemetry-maintained instrumentation covers the library. Install and register it.
3. **community**: an OpenLLMetry per-library package, else an OpenInference one. Install it and register it on the plain OTel SDK, never through the `traceloop-sdk` or `phoenix.otel` bootstraps.
4. **manual**: raw HTTP, or nothing covers the library. Hand-written GenAI spans through one shared helper.

For frameworks, instrument the framework's layer and add provider-SDK instrumentation underneath only when the framework's spans lack model and token data. Note any duplicate LLM spans that result, for the report.

Check every package against its registry (`npm view <pkg> version`, `pip index versions <pkg>`) for existence and latest version. For a library the matrix doesn't list, search the OpenTelemetry contrib repos, then OpenLLMetry, then OpenInference, before settling on manual.

Done when every call path has a route and a concrete package with a verified version (or "manual").

## Step 3: Gather

Ask the user, in one batch, everything the plan still needs:

- **Destination**: OTLP endpoint, protocol (`http/protobuf` default, or `grpc`), auth headers. If they have no backend yet or want to look locally first, offer a local viewer from `references/configuration.md`.
- **Content capture**: record prompts, completions and tool arguments? Recommend yes, and say they can contain PII and secrets.
- **Manual spans** (only when a route is manual): list the call sites and ask once whether to wire spans around them.
- **Service names**, only when a unit's name doesn't make an obvious `OTEL_SERVICE_NAME`.

Done when every question has an answer. If the user declines manual spans, drop those call paths and note it for the report.

## Step 4: Implement

For each chosen unit:

1. **Bootstrap.** Load `references/bootstrap-typescript.md`, `references/bootstrap-python.md`, or `references/bootstrap-other.md`. When the inventory found an existing OTel setup, extend it: register the new instrumentations on it, and add an OTLP exporter only when the destination is new. One global provider per process, always.
2. **Routes.** Install and register each package from the plan. For the AI SDK, load `references/ai-sdk.md`. For manual routes, load `references/manual-spans.md`.
3. **Config.** Load `references/configuration.md`. Write the destination, service name and content-capture setting as env vars into the unit's env mechanism. Real secrets go only in a gitignored file; mirror every key with a placeholder in `.env.example` (create it if missing). Deploy-platform env stays with the user and goes in the report.

Done when every planned call path is wired, the bootstrap runs before any LLM client is imported, and the unit builds or typechecks.

## Step 5: Verify

Load `references/verification.md` and follow it. Done when exported telemetry has been observed for every route, or you have told the user exactly why you couldn't run it and how they can check.

## Step 6: Report

Leave the changes uncommitted and report:

- inventory: units and call paths found
- per call path: route, package and version, and why
- files created or changed
- env vars: what was written where, and what the user must set in each deploy environment
- content capture: on or off, and the knobs that control it
- verification result, plus any signal disabled and the env var that re-enables it
- caveats: duplicate spans, Edge-runtime gaps, call paths skipped
