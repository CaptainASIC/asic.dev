#!/usr/bin/env bash
# Install asic.dev tools: symlink Claude skills, copy Warp workflows.
# Uninstall: rm ~/.claude/skills/{agentdash,draft-prp} ~/.warp/workflows/agentdash.yaml
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

mkdir -p "$HOME/.claude/skills" "$HOME/.warp/workflows"

# Every skill dir symlinks into ~/.claude/skills (repo stays source of truth)
for skill in "$REPO"/skills/*/; do
  name="$(basename "$skill")"
  ln -sfn "${skill%/}" "$HOME/.claude/skills/$name"
done

cp -f "$REPO/warp/agentdash.yaml" "$HOME/.warp/workflows/agentdash.yaml"
chmod +x "$REPO/skills/agentdash/agentdash.py"

echo "installed:"
echo "  claude skills  -> ~/.claude/skills/{agentdash,draft-prp} (symlinks to repo)"
echo "  warp workflow  -> ~/.warp/workflows/agentdash.yaml (copy)"
echo
echo "manual step for Warp: paste warp/draft-prp.md into a Warp Drive prompt named"
echo "'draft-prp' (Warp Drive is cloud-stored; no file install possible)."
echo "run agentdash: python3 ~/.claude/skills/agentdash/agentdash.py"
