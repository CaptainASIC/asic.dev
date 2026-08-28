#!/usr/bin/env bash
# Dev-mode install: symlink Claude skills, install global rules. End users: install the
# plugin instead (see README). Uninstall: rm the ~/.claude/skills/<name> symlinks.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

mkdir -p "$HOME/.claude/skills"

# Every plugin skill dir symlinks into ~/.claude/skills (dev mode: bare /names, live edits).
# End users should prefer the plugin install instead — see README.
for skill in "$REPO"/plugins/asic-tools/skills/*/; do
  name="$(basename "$skill")"
  ln -sfn "${skill%/}" "$HOME/.claude/skills/$name"
done

chmod +x "$REPO/plugins/asic-tools/skills/asicdash/asicdash.py"

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
echo "NOTE: dev symlinks duplicate the plugin install — use one or the other."
