#!/usr/bin/env bash
# Dev-mode install: symlink Claude skills, copy Warp workflows. End users: install the
# plugin instead (see README). Uninstall: rm the ~/.claude/skills/<name> symlinks and
# ~/.warp/workflows/agentdash.yaml.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

mkdir -p "$HOME/.claude/skills" "$HOME/.warp/workflows"

# Every plugin skill dir symlinks into ~/.claude/skills (dev mode: bare /names, live edits).
# End users should prefer the plugin install instead — see README.
for skill in "$REPO"/plugins/asic-tools/skills/*/; do
  name="$(basename "$skill")"
  ln -sfn "${skill%/}" "$HOME/.claude/skills/$name"
done

cp -f "$REPO/warp/agentdash.yaml" "$HOME/.warp/workflows/agentdash.yaml"
chmod +x "$REPO/plugins/asic-tools/skills/agentdash/agentdash.py"

echo "installed (dev mode):"
echo "  claude skills  -> ~/.claude/skills/* (symlinks to repo, one per plugin skill)"
echo "  warp workflow  -> ~/.warp/workflows/agentdash.yaml (copy)"
echo
echo "manual step for Warp: paste each warp/*.md into a Warp Drive prompt of the same name"
echo "(Warp Drive is cloud-stored; no file install possible)."
echo "NOTE: dev symlinks duplicate the plugin install — use one or the other."
