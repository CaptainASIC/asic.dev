# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning follows
[SemVer](https://semver.org/) on the `asic-tools` plugin version.

## [0.5.1] - 2026-06-13

### Added
- **asicdash** heatmap hover tooltips: date, total tokens, session count, and
  per-surface percentage split for the day — glanceable breakdown without
  opening the click-modal. Keyboard focus shows the same tooltip.

## [0.5.0] - 2026-06-12

### Added
- **asicdash** Claude usage section in the HTML report: GitHub-style contribution
  heatmap built from local session transcripts (`~/.claude/projects/**/*.jsonl`),
  color-coded by surface (Code = CLI, Cowork = desktop; Chat shown honestly as
  "no local data"), per-day breakdown modal, and a weekly stacked token chart.
  New `usage.py` collector module, stdlib only.

### Changed
- **agentdash renamed to asicdash** (skill, script, Warp workflow). The skill still
  triggers on `/agentdash` phrasing for muscle memory.
- asicdash default output is now the themed HTML report (opens in the browser);
  the terminal table moved behind a new `--cli` flag. `--json` unchanged.

## [0.4.0] - 2026-06-10

### Added
- Consolidated global engineering rules, bundled inside the plugin
  (`plugins/asic-tools/rules/CLAUDE.global.md`) — single source for `~/.claude/CLAUDE.md`
  and Warp Drive rules, with canonical Pydantic v2 / testing / git / naming examples.
- **sync-rules** skill: deploy/update the bundled rules to `~/.claude/CLAUDE.md` on any
  machine with the plugin installed; diff-aware, never clobbers local edits silently.
- install.sh installs the rules file in dev mode without clobbering local edits.

## [0.3.0] - 2026-06-10

### Added
- **prp-implement** skill: two-phase PRP executor (review/plan with drift check, pause
  for approval, then task-by-task execution with leveled validation and the full §10
  close-out ritual). Warp prompt counterpart.

## [0.2.0] - 2026-06-10

### Added
- **scaffold** skill: standards-enforced Python project bootstrap with a hard
  run-verification gate; kind variants for api/agent/cli/library. Warp prompt counterpart.
- **release** skill: multi-location version survey, SemVer recommendation from
  Conventional Commits, format-matching changelog entries. Warp prompt counterpart.

### Changed
- All Warp prompts/workflows reference the plugin marketplace clone path instead of the
  removed dev symlinks.

## [0.1.0] - 2026-06-10

### Added
- Repo packaged as Claude Code plugin marketplace (`asic-dev` → `asic-tools`,
  "Captain ASIC's Dev Toolbox").
- **agentdash** skill: deterministic config auditor for Claude Code + Warp.
- **draft-prp** skill: research-first Product Requirements Prompt generator with refusal
  gate; canonical template + style guide.
- Dev-mode `install.sh` (symlinks) and Warp counterparts.
