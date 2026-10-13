---
name: sync-rules
description: Install or update Captain ASIC's global engineering rules (~/.claude/CLAUDE.md) from the asic-tools plugin's bundled rules file. Use when the user says "sync my rules", "install the global rules", "update my CLAUDE.md rules", "get my rules on this machine", or invokes /sync-rules — typically right after installing the plugin on a new machine, or after a plugin update changed the rule set. Never clobbers local edits silently.
---

# sync-rules

Deploys the plugin's bundled rule set to this machine's global `~/.claude/CLAUDE.md`. The
rules file is versioned with the plugin — this skill is how a new machine (or a freshly
updated plugin) gets current law without a repo checkout.

## Locate the source

In order, first hit wins:

1. `${CLAUDE_SKILL_DIR}/../../rules/CLAUDE.global.md` — the bundled copy beside this skill;
   this is the normal path. Claude Code substitutes `${CLAUDE_SKILL_DIR}` in skill text; the
   shell never has `CLAUDE_PLUGIN_ROOT` set.
2. `~/.claude/plugins/marketplaces/asic-dev/plugins/asic-tools/rules/CLAUDE.global.md` —
   marketplace clone fallback.
3. A repo checkout's `plugins/asic-tools/rules/CLAUDE.global.md` if the cwd is the
   asic.dev repo (dev mode).

None found → report that the plugin isn't installed and stop.

## Compare and act

Target: `~/.claude/CLAUDE.md`.

- **Absent** → copy source to target. Report installed + remind: takes effect next
  session.
- **Identical** (byte-compare) → report "already current", done.
- **Differs** → never overwrite silently. Show the user a readable diff
  (`diff -u target source`), then ask which way to resolve:
  1. **Overwrite** — plugin version wins (local edits lost; say so explicitly).
  2. **Keep local** — no change; note the target has diverged from the shipped rules.
  3. **Merge** — apply the source's changes while preserving the user's local additions;
     show the merged result before writing.

## After writing

- Confirm the file, report its size, and remind: a restart / new session picks it up.

## Boundaries

- This skill writes exactly one file: `~/.claude/CLAUDE.md`. It never edits the bundled
  source, never touches project-level CLAUDE.md files, and never pushes anything.
