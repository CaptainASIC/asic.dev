#!/usr/bin/env bash
# Dev-mode install: symlink Claude skills, install global rules. End users: install the
# plugin instead (see README). Uninstall: rm the ~/.claude/skills/<name> and
# ~/.claude/agents/<name>.md symlinks.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

mkdir -p "$HOME/.claude/skills"
mkdir -p "$HOME/.claude/agents"

# Every plugin skill dir symlinks into ~/.claude/skills (dev mode: bare /names, live edits).
# End users should prefer the plugin install instead — see README.
for skill in "$REPO"/plugins/asic-tools/skills/*/; do
  name="$(basename "$skill")"
  ln -sfn "${skill%/}" "$HOME/.claude/skills/$name"
done

chmod +x "$REPO/plugins/asic-tools/skills/asicdash/asicdash.py"

# Every plugin agent definition symlinks into ~/.claude/agents. Auto-discovery covers the plugin
# install only — a dev checkout is not a plugin, so without this the agents the skills delegate
# to do not exist and every fan-out silently falls back to a generic subagent.
for agent in "$REPO"/plugins/asic-tools/agents/*.md; do
  [ -e "$agent" ] || continue
  ln -sfn "$agent" "$HOME/.claude/agents/$(basename "$agent")"
done

# Global engineering rules -> ~/.claude/CLAUDE.md (copy, not symlink: the desktop app is
# known to skip symlinks in some loaders). Never clobber local edits silently.
RULES_SRC="$REPO/plugins/asic-tools/rules/CLAUDE.global.md"
RULES_DST="$HOME/.claude/CLAUDE.md"
if [ ! -f "$RULES_DST" ]; then
  cp "$RULES_SRC" "$RULES_DST"
  echo "  global rules   -> ~/.claude/CLAUDE.md (installed)"
elif cmp -s "$RULES_SRC" "$RULES_DST"; then
  echo "  global rules   -> ~/.claude/CLAUDE.md (already current)"
else
  echo "  global rules   -> SKIPPED: ~/.claude/CLAUDE.md differs from rules/CLAUDE.global.md"
  echo "                    diff them and reconcile manually (local edits are preserved)"
fi

echo "installed (dev mode):"
echo "  claude skills  -> ~/.claude/skills/* (symlinks to repo, one per plugin skill)"
echo "  claude agents  -> ~/.claude/agents/* (symlinks to repo, one per plugin agent)"
echo "NOTE: dev symlinks duplicate the plugin install — use one or the other."
