# agent-observability-skills

A Claude Code plugin marketplace (`.claude-plugin/marketplace.json`, marketplace name `moyai`) shipping one plugin, `agent-observability`, with one skill, `setup-agent-observability`. The skill is also distributed as a single curl-able `SKILL.md`, so it must work on its own.

## Constraints the skill depends on

- **SKILL.md stands alone.** A curl install gets only SKILL.md. Every reference it needs is loaded through its "Loading references" procedure: local `references/` first, else raw GitHub pinned to tag `v<version>`, else `main`. Any new reference file must be reached through that procedure, never by a bare relative path.
- **Vendor-neutral first.** Route order is native → official OpenTelemetry → OpenLLMetry per-library packages on the plain OTel SDK → OpenInference → manual GenAI-semconv spans. Configuration goes through standard `OTEL_*` env vars. Vendor bootstraps (`traceloop-sdk`, `phoenix.otel`, Logfire, Langfuse SDKs) stay out of the skill's output.
- **Facts live in references, not SKILL.md.** Package names, versions and APIs churn. Keep them in `references/*.md` (mostly `instrumentation-matrix.md`) so a fix is a one-file edit, and date the "last verified" line at the top of a reference when you re-verify it.
- **Claude-first, degrades gracefully.** Claude Code tool names (AskUserQuestion, `${CLAUDE_SKILL_DIR}`) are fine, but each instruction must still make sense to an agent without them.

## Releasing

The version lives in `plugin.json` and twice in SKILL.md (the `Skill version:` line and the pinned reference URL). Keep them in sync with `scripts/version.sh`:

```sh
scripts/version.sh check
scripts/version.sh set 0.2.0
git commit -am "Release v0.2.0" && git tag v0.2.0 && git push && git push origin v0.2.0
```

Push the tag together with the bump commit: until the tag exists, curl users of `main` fall back to fetching references from `main`. Bump the version on every release, because marketplace users only receive updates when `plugin.json`'s version changes.

Validate before tagging:

```sh
claude plugin validate . --strict
claude plugin validate ./plugins/agent-observability --strict
```

## Testing the skill

`fixtures/` holds small projects, one per branch of the skill. `fixtures/README.md` lists the behavior each one should produce. Copy a fixture somewhere scratch, run the skill on it, and compare the outcome to that list.
