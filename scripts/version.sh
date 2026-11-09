#!/usr/bin/env bash
# Keep the skill version consistent across plugin.json and SKILL.md.
#
#   scripts/version.sh check        exit 1 if the versions disagree
#   scripts/version.sh set 0.2.0    write 0.2.0 everywhere
#
# SKILL.md pins its remote reference URLs to the tag v<version>, so a version
# bump must be tagged and pushed in the same release (see CLAUDE.md).
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
plugin_json="$root/plugins/agent-observability/.claude-plugin/plugin.json"
skill_md="$root/plugins/agent-observability/skills/setup-agent-observability/SKILL.md"

plugin_version() { sed -nE 's/^[[:space:]]*"version":[[:space:]]*"([^"]+)".*/\1/p' "$plugin_json" | head -1; }
skill_version() { sed -nE 's/^Skill version: `([^`]+)`.*/\1/p' "$skill_md" | head -1; }
url_versions() { grep -oE 'agent-observability-skills/v[0-9]+\.[0-9]+\.[0-9]+[^/]*/' "$skill_md" | sed -E 's#.*/v([^/]+)/#\1#' | sort -u; }

check() {
  local p s u
  p="$(plugin_version)"; s="$(skill_version)"; u="$(url_versions)"
  echo "plugin.json:      $p"
  echo "SKILL.md version: $s"
  echo "SKILL.md URL tag: ${u//$'\n'/, }"
  if [[ "$p" == "$s" && "$u" == "$p" ]]; then echo "ok"; else echo "MISMATCH" >&2; exit 1; fi
}

set_version() {
  local v="$1"
  [[ "$v" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.]+)?$ ]] || { echo "not a semver: $v" >&2; exit 2; }
  sed -i.bak -E "s/^([[:space:]]*\"version\":[[:space:]]*\")[^\"]+\"/\1$v\"/" "$plugin_json"
  sed -i.bak -E "s/^Skill version: \`[^\`]+\`/Skill version: \`$v\`/" "$skill_md"
  sed -i.bak -E "s#(agent-observability-skills/)v[0-9]+\.[0-9]+\.[0-9]+[^/]*/#\1v$v/#g; s#(fetch the same path from \`main\` instead of \`)v[^\`]+\`#\1v$v\`#" "$skill_md"
  rm -f "$plugin_json.bak" "$skill_md.bak"
  check
  echo
  echo "Next: git commit -am \"Release v$v\" && git tag v$v && git push && git push origin v$v"
}

case "${1:-}" in
  check) check ;;
  set) set_version "${2:?usage: scripts/version.sh set <version>}" ;;
  *) echo "usage: scripts/version.sh check | set <version>" >&2; exit 2 ;;
esac
