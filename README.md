# agent-observability-skills

Agent skills for observing LLM apps and agents with OpenTelemetry.

## `/setup-agent-observability`

Point your coding agent at a project and it wires in **vendor-neutral OpenTelemetry**: GenAI semantic-convention traces, metrics and logs, exported over OTLP to any backend (or a local viewer if you don't have one yet).

What it does:

1. **Inventories** how the project calls LLMs: the Vercel AI SDK, provider SDKs (`openai`, `anthropic`, `google-genai`, Bedrock, …), agent frameworks (LangChain, LlamaIndex, Mastra, Pydantic AI, OpenAI Agents SDK, …), or raw HTTP. If the project makes no LLM calls, it says so and stops.
2. **Picks the most vendor-neutral route** for each call path: native OTel support, then official OpenTelemetry instrumentation, then OpenLLMetry per-library packages on the plain OTel SDK, then hand-written GenAI spans (only after asking you).
3. **Asks** for your OTLP endpoint and headers, and whether to capture prompt and completion content.
4. **Implements** the bootstrap (extending any existing OTel setup), instrumentation and `OTEL_*` env config, with secrets kept in gitignored files.
5. **Verifies** by triggering a real LLM call and confirming that telemetry exports.
6. **Reports** what it changed. Nothing is committed.

Supports TypeScript/JavaScript and Python in depth, and other languages on a best-effort basis.

## Install

### As a Claude Code plugin

```
/plugin marketplace add moyai-ai/agent-observability-skills
/plugin install agent-observability@moyai
```

Then run `/setup-agent-observability`, or just ask Claude to "add tracing to my agent".

### One-off, via curl

Into the current project:

```sh
mkdir -p .claude/skills/setup-agent-observability && \
curl -fsSL https://raw.githubusercontent.com/moyai-ai/agent-observability-skills/main/plugins/agent-observability/skills/setup-agent-observability/SKILL.md \
  -o .claude/skills/setup-agent-observability/SKILL.md
```

Use `~/.claude/skills/...` instead to install it for all projects. The skill fetches its reference docs from this repo on demand, pinned to the release that matches the SKILL.md you downloaded.

With any other coding agent that can fetch URLs, skip the install and say:

> Follow https://raw.githubusercontent.com/moyai-ai/agent-observability-skills/main/plugins/agent-observability/skills/setup-agent-observability/SKILL.md to set up observability for this project.

## Repo layout

```
.claude-plugin/marketplace.json          marketplace "moyai"
plugins/agent-observability/
  .claude-plugin/plugin.json             plugin manifest (holds the version)
  skills/setup-agent-observability/
    SKILL.md                             the workflow
    references/                          loaded on demand (locally or from GitHub)
fixtures/                                sample projects for testing the skill
scripts/version.sh                       keep versions and pinned URLs in sync
```

## License

MIT
