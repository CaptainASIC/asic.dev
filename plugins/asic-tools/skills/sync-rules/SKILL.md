---
name: sync-rules
description: Install or update Captain ASIC's global engineering rules (~/.claude/CLAUDE.md and ~/.claude/rules/asic-*.md) and merge the plugin's guardrail settings (attribution off, push deny rule, auto-mode hard_deny) into ~/.claude/settings.json, then offer to install or upgrade the companion archify skill, from files bundled with the asic-tools plugin. Use when the user says "sync my rules", "install the global rules", "update my CLAUDE.md rules", "get my rules on this machine", or invokes /sync-rules — typically right after installing the plugin on a new machine, or after a plugin update changed the rule set. Never clobbers local edits silently.
---

# sync-rules

Deploys the plugin's bundled rule set to this machine's global `~/.claude/CLAUDE.md` and
`~/.claude/rules/asic-*.md`, merges the guardrail settings, and offers to install or upgrade the
companion archify skill. The rules file is versioned with the plugin — this skill is how a new machine (or a freshly
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

Part of it may belong to another tool: today, the `# graphify` skill-registration section that
`graphify install` writes and refreshes. Never compare against or write the bare source.
Compose it first, so tool-owned sections survive at EOF:

    python3 "${CLAUDE_SKILL_DIR}/scripts/owned_blocks.py" compose <source> ~/.claude/CLAUDE.md > <scratchpad>/CLAUDE.composed.md

`<source>` is the core file found above; `<scratchpad>` is this session's scratchpad directory.
The composed file is what you compare and what you write.

If the target still contains `## Python environment`, it is the pre-2.0 single-file rule set.
Say so before the diff: those sections now ship as `~/.claude/rules/asic-*.md`, and keeping the
old file while installing the scoped files loads the Python rules twice.

- **Absent** → write the composed file to target. Report installed + remind: takes effect next
  session.
- **Identical** (byte-compare target vs composed) → report "already current", then proceed to the scoped rule files step.
- **Differs** → never overwrite silently. Show the user a readable diff
  (`diff -u target composed`), then ask which way to resolve:
  1. **Overwrite** — composed version wins (local edits lost; say so explicitly; tool-owned sections are kept).
  2. **Keep local** — no change to the file; note the target has diverged from the shipped rules,
     then proceed to the scoped rule files step.
  3. **Merge** — apply the composed file's changes while preserving the user's local additions;
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
- When every bundled file is handled, confirm the writes below, then proceed to the settings step.

## After writing

- Confirm each file written, report its size, and remind: a restart / new session picks it up;
  then proceed to the settings step.

## Settings fragment

After the rules step, merge the bundled guardrail settings — attribution off (`commit`/`pr` empty,
`sessionUrl` false), `permissions.deny` for `git push`, `autoMode.hard_deny` rules, and the
graphify guard hooks (`graphify hook-guard search|read`) — into `~/.claude/settings.json`. The
script is the only writer; never hand-edit the JSON. Hook entries named in the fragment's
`$retire` list are removed — the diff and `RETIRED:` lines show each one before Apply.

1. Dry-run (writes nothing):
   `python3 "${CLAUDE_SKILL_DIR}/scripts/merge_settings.py" --fragment "${CLAUDE_SKILL_DIR}/../../rules/settings.fragment.json" --target ~/.claude/settings.json`
2. Read the `STATUS:` line.
   - **current** → report "settings already current", then proceed to the archify step.
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
6. After any outcome except exit code 2 (Apply, Keep mine, Take plugin's, or Skip),
   then proceed to the archify step.

## Companion skill: archify

Diagrams are archify's job; asic-tools ships no diagram skill (PRP-021). Run this last, after the
settings step, on every outcome except "None found" and a settings exit code 2 (including "already
current", "Keep local", "settings already current" and Skip). This step is read-only until the
user says yes:

```bash
f="$HOME/.claude/skills/archify/skill-release.json"
v=$(grep -o '"version": *"[^"]*"' "$f" 2>/dev/null | grep -oE '[0-9]+' | head -1)
grep -o '"version": *"[^"]*"' "$f" 2>/dev/null || echo "archify: not installed"
[ "${v:-0}" -ge 3 ] && echo "archify current" || echo "archify missing-or-old"
```

- **Current** (major ≥ 3) → report the version; done.
- **Missing or older than 3.x** → say so, and say what the install does: it fetches third-party
  code (MIT, github.com/tt-a1i/archify) that runs on Node.js 18+. Ask: install/upgrade now, or
  skip. Only on an explicit yes, run:

  ```bash
  npx -y skills add tt-a1i/archify --skill archify --agent claude-code --global --yes
  ```

  Then re-run the check and report the new version. On skip, print the command and stop. Never
  run it without asking.

## Boundaries

- This skill writes `~/.claude/CLAUDE.md`, `~/.claude/rules/asic-*.md` (create, update, and delete
  stale ones on explicit yes; no other file in that directory is ever touched) and
  `~/.claude/settings.json`, plus the backup `~/.claude/settings.json.sync-rules.bak`. It never edits the bundled sources,
  never touches project-level CLAUDE.md or `.claude/settings*.json`,
  never removes a settings key, except hook entries the fragment's `$retire` list names,
  and never pushes anything. It never deletes hook scripts; retiring a `~/.claude/hooks/*.sh` file
  is the user's call.
- One exception to the files-written list: the archify step reads `skill-release.json` and, only
  on an explicit yes, runs the third-party `skills` CLI, which installs a copy at
  `~/.claude/skills/archify` (replacing any older copy or link there). Without that yes it writes
  nothing.
