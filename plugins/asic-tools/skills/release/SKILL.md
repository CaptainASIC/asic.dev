---
name: release
description: Cut a release — detect every version location in the repo (pyproject, plugin.json, package.json, Xcode MARKETING_VERSION, …), recommend a SemVer bump from Conventional Commits since the last tag, update CHANGELOG.md matching its existing format, commit on a release branch. Use when the user says "cut a release", "bump the version", "release vX.Y.Z", "prep a release", or invokes /release. Never pushes, never tags — prints the post-merge checklist instead.
---

# release

Prepares a release commit; the user merges, tags, and pushes (GitKraken). The skill's value
is *consistency*: every version string in the repo moves together, and the changelog entry
is derived from what actually shipped, not from memory.

Reference file: `references/version_locations.md` — per-ecosystem version-string table.

## Phase 1 — Survey (read-only)

1. **Find every version location.** Walk the table in version_locations.md against the
   repo; record file, key, current value. Multiple locations must agree — if they already
   disagree, STOP and report the drift before touching anything (fixing drift is its own
   decision, not a side effect).
2. **Find the baseline.** Latest SemVer git tag (`git tag --sort=-v:refname`); if no tags,
   latest version heading in CHANGELOG.md; if neither, treat everything since root as
   unreleased.
3. **Collect what shipped.** `git log <baseline>..HEAD --format='%h %s'` — classify each
   subject by Conventional Commit type. Non-conventional subjects go to an "Other" bucket,
   never silently dropped.
4. **Read CHANGELOG.md** (if present) and note its exact format — heading style, grouping
   names, date format, link conventions. The new entry must be indistinguishable in style
   from the existing entries. No CHANGELOG → create one in Keep a Changelog format.
5. **Plugin preflight (Claude Code plugin repos only).** When the repo holds a
   `.claude-plugin/plugin.json` (at the root or under `plugins/*/`), run
   `claude plugin validate --strict <plugin-dir>` for each plugin, and
   `claude plugin validate --strict .` when `.claude-plugin/marketplace.json` exists. Any failure:
   STOP and report it — a release that fails validation ships a plugin the runtime will not load.

## Phase 2 — Decide the bump

Recommend from the commit set: any `BREAKING CHANGE`/`!` → major; any `feat` → minor;
otherwise → patch. Present the recommendation with the commit counts behind it
("3 feat, 5 fix since v1.2.0 → minor → v1.3.0") and confirm with the user — the
recommendation is mechanical, the decision is theirs (pre-1.0 conventions and
marketing-driven bumps both override mechanics).

## Phase 3 — Apply

1. Branch: `release/vX.Y.Z` from the current main/develop head (confirm base branch if
   the repo uses develop). Never work on main.
2. Update every version location found in Phase 1. Re-grep the old version string
   afterward to catch locations the table missed; add misses to the report.
   uv projects (a `pyproject.toml` with a `[project]` table): cross-check the bump with
   `uv version --bump <major|minor|patch> --dry-run` — its `old => new` line must name the version
   Phase 2 settled on — then apply it with the same command without `--dry-run`. uv rewrites
   `pyproject.toml` and re-locks `uv.lock` in one step; never hand-edit either.
3. CHANGELOG entry: new version heading + date, changes grouped per the file's existing
   convention (typically Added / Changed / Fixed), one line per meaningful change written
   from the commit subjects — reworded for a reader, not pasted raw. "Other" bucket items
   get reviewed into a group or dropped *visibly* (tell the user which).
4. If the project has lint/tests configured, run them (`uv run ruff check .`,
   `uv run pytest` or ecosystem equivalent) — a release commit that breaks CI is a
   failure of this skill.
5. Commit: `chore(release): vX.Y.Z` — Conventional, no AI attribution, not pushed.
6. **Tag consistency check (plugin repos only).** On the clean tree after the commit, run
   `claude plugin tag --dry-run <plugin-dir>` (dry run only — it creates no tag and pushes nothing).
   Exit 0 with `Dry run — would create tag` means `plugin.json` and the marketplace entry agree;
   `Version mismatch` or `Uncommitted changes` means fix and re-run. Ignore the tag name it prints
   (`<name>--vX.Y.Z`): Phase 4's `vX.Y.Z` tag stays the user's action.

## Phase 4 — Report + post-merge checklist

Report: locations updated (file:key old→new), changelog entry verbatim, validation
results. Then the checklist the user executes:

```
1. Push release/vX.Y.Z and merge to main (GitKraken, no-ff)
2. Tag merge commit on main: vX.Y.Z (annotated)
3. Push the tag
4. Optional: GitHub release — draft body below, paste into gh/web
```

Include a ready-to-paste GitHub release body (changelog entry + install/update one-liner
when the repo is a plugin/package). Creating the GitHub release is the user's action, not
the skill's.

## Special case worth knowing

A Claude Code plugin repo (like asic.dev): bumping `plugin.json` version is what makes
`claude plugin update` offer the new version to users — releasing without that bump ships
nothing. The version sweep in Phase 3 covers it; this note is the why.
