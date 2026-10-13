---
name: sync-rules
description: Install or update Captain ASIC's global engineering rules (~/.claude/CLAUDE.md and ~/.claude/rules/asic-*.md) and merge the plugin's guardrail settings (attribution off, push deny rule, auto-mode hard_deny) into ~/.claude/settings.json, from files bundled with the asic-tools plugin. Use when the user says "sync my rules", "install the global rules", "update my CLAUDE.md rules", "get my rules on this machine", or invokes /sync-rules — typically right after installing the plugin on a new machine, or after a plugin update changed the rule set. Never clobbers local edits silently.
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

The scoped rule files ship beside the core in `rules/scoped/asic-*.md`; resolve that directory
with the same three tiers (first hit wins) and stop if it is missing alongside a found core —
a core without its scoped files would drop rules.

None found → report that the plugin isn't installed and stop.

## Compare and act

Target: `~/.claude/CLAUDE.md`.

If the target still contains `## Python environment`, it is the pre-2.0 single-file rule set.
Say so before the diff: those sections now ship as `~/.claude/rules/asic-*.md`, and keeping the
old file while installing the scoped files loads the Python rules twice.

- **Absent** → copy source to target. Report installed + remind: takes effect next
  session.
- **Identical** (byte-compare) → report "already current", done.
- **Differs** → never overwrite silently. Show the user a readable diff
  (`diff -u target source`), then ask which way to resolve:
  1. **Overwrite** — plugin version wins (local edits lost; say so explicitly).
  2. **Keep local** — no change; note the target has diverged from the shipped rules.
  3. **Merge** — apply the source's changes while preserving the user's local additions;
     show the merged result before writing.

## Scoped rule files

Target: `~/.claude/rules/` (create it if absent). These files load only when Claude touches a
file matching their `paths:` frontmatter. This phase runs after every CLAUDE.md outcome above —
"already current" and Keep local included.

- For each bundled `asic-*.md`, apply the same absent / identical / differs flow as
  `~/.claude/CLAUDE.md` above, one file at a time.
- **Stale:** list every `~/.claude/rules/asic-*.md` with no bundled counterpart. Delete one only
  after the user says yes to that file; otherwise leave it and say it still loads.
- Never read, change or delete a file in `~/.claude/rules/` whose name does not start with `asic-`.

## After writing

- Confirm the file, report its size, and remind: a restart / new session picks it up.

## Settings fragment

After the rules step, merge the bundled guardrail settings — attribution off (`commit`/`pr` empty,
`sessionUrl` false), `permissions.deny` for `git push`, and `autoMode.hard_deny` rules — into
`~/.claude/settings.json`. The script is the only writer; never hand-edit the JSON.

1. Dry-run (writes nothing):
   `python3 "${CLAUDE_SKILL_DIR}/scripts/merge_settings.py" --fragment "${CLAUDE_SKILL_DIR}/../../rules/settings.fragment.json" --target ~/.claude/settings.json`
2. Read the `STATUS:` line.
   - **current** → report "settings already current", done.
   - **pending** → show the diff, say in one line what each added entry does, and ask:
     **Apply** (re-run step 1 with `--write`) or **Skip**.
   - **conflict** → show each `CONFLICT:` line and the diff, and ask:
     1. **Keep mine** — re-run with `--write`: applies only the non-conflicting additions.
     2. **Take plugin's** — re-run with `--write --prefer-fragment` (say which values are replaced).
     3. **Skip** — no change.
3. Exit code 2 → report the `ERROR:` line verbatim and stop. Do not repair the file yourself.
4. Never chain the dry-run and `--write` in one command — the user's choice sits between them.
5. After a write: report the backup path (`~/.claude/settings.json.sync-rules.bak`) and that a new
   session picks the settings up. `claude auto-mode config` shows the effective `hard_deny` list.

## Boundaries

- This skill writes `~/.claude/CLAUDE.md`, `~/.claude/rules/asic-*.md` (create, update, and delete
  stale ones on explicit yes; no other file in that directory is ever touched) and
  `~/.claude/settings.json`, plus the backup `~/.claude/settings.json.sync-rules.bak`. It never edits the bundled sources,
  never touches project-level CLAUDE.md or `.claude/settings*.json`, never removes a settings key,
  and never pushes anything.
