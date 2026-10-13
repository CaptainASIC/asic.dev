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

# Global engineering rules: the core -> ~/.claude/CLAUDE.md (loaded every session) and the
# path-scoped files -> ~/.claude/rules/asic-*.md (loaded when a matching file is touched).
# Copy, not symlink: the desktop app is known to skip symlinks in some loaders. Never clobber
# local edits silently, and never touch a rules file that is not ours (asic-*.md).
RULES_DIR="$REPO/plugins/asic-tools/rules"
install_rule() {  # $1 = bundled source, $2 = destination, $3 = label
  if [ ! -f "$2" ]; then
    cp "$1" "$2"
    echo "  $3 -> installed"
  elif cmp -s "$1" "$2"; then
    echo "  $3 -> already current"
  else
    echo "  $3 -> SKIPPED: differs from the bundled copy; diff and reconcile manually"
  fi
}
install_rule "$RULES_DIR/CLAUDE.global.md" "$HOME/.claude/CLAUDE.md" "global rules (core)"
# Reason: a SKIPPED 1.x monolith plus the scoped files below loads the Python rules twice.
if grep -q '^## Python environment' "$HOME/.claude/CLAUDE.md"; then
  echo "  WARNING: ~/.claude/CLAUDE.md is the pre-2.0 single-file rule set; with ~/.claude/rules/asic-*.md it loads the Python rules twice. Run /asic-tools:sync-rules or reconcile by hand."
fi
mkdir -p "$HOME/.claude/rules"
for rule in "$RULES_DIR"/scoped/asic-*.md; do
  [ -e "$rule" ] || continue
  install_rule "$rule" "$HOME/.claude/rules/$(basename "$rule")" "$(basename "$rule")"
done
for deployed in "$HOME"/.claude/rules/asic-*.md; do
  [ -e "$deployed" ] || continue
  [ -e "$RULES_DIR/scoped/$(basename "$deployed")" ] && continue
  echo "  STALE: ~/.claude/rules/$(basename "$deployed") is no longer shipped; remove it by hand"
done

echo "installed (dev mode):"
echo "  claude skills  -> ~/.claude/skills/* (symlinks to repo, one per plugin skill)"
echo "  claude agents  -> ~/.claude/agents/* (symlinks to repo, one per plugin agent)"
echo "  global rules   -> ~/.claude/CLAUDE.md + ~/.claude/rules/asic-*.md (copies)"
echo "NOTE: dev symlinks duplicate the plugin install — use one or the other."
