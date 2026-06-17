# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning follows
[SemVer](https://semver.org/) on the `asic-tools` plugin version.

## [0.8.1] - 2026-06-17

### Fixed
- **prp-review Workflow now reads `args` when the harness passes it as a JSON
  string.** In `scriptPath` mode the `Workflow` tool can hand the script its
  `args` global as a JSON-encoded string rather than a parsed object, so
  `args.prpPath` was `undefined` and `review_workflow.js` threw
  "args.prpPath is required" before any reviewer ran. The script now coerces a
  string `args` via `JSON.parse` before reading `prpPath`; object `args` still
  works unchanged.

## [0.8.0] - 2026-06-17

### Changed
- **draft-prp renamed to prp-draft.** The three PRP-lifecycle skills now share a
  `prp-*` prefix and group under one tab-completion namespace (`prp-draft`,
  `prp-review`, `prp-implement`); `idea-refine` stays unprefixed as pre-PRP
  ideation. The Claude Code invocation is now `/asic-tools:prp-draft` and the
  Warp twin moved to `warp/prp-draft.md` — update any saved aliases. Skill dir,
  slug, both catalog manifests, the bundled global rules, and all cross-skill
  references moved together; natural-language triggers ("draft a PRP") are
  unchanged.

### Added
- **prp-draft Phase 2 evidence schema.** Fan-out research subagents must now
  return a structured evidence list (`{ path, symbol, line, surprise }`) merged
  into §4.1/§4.4 of the PRP, instead of prose conclusions — any finding that
  cannot trace to a `path:line` is rejected. Tightens the research contract
  without converting the skill to a Workflow; the interview and refusal gates
  stay human-in-loop.
- **prp-implement A3 drift check scales to a structured fan-out.** Contained
  PRPs still check inline; large subsystem PRPs now fan out read-only Explore
  subagents (one per cited §4 file or gotcha cluster) returning structured
  verdicts (`{ citation, status, evidence }`) merged into a drift table. Stays
  read-only per the Phase A no-mutation rule; execution (Phase B) remains
  sequential and human-in-loop by design.

## [0.7.0] - 2026-06-16

### Added
- **prp-review** skill: adversarial review gate between `draft-prp` and
  `prp-implement`. Authors and runs a Workflow that fans out six distinct-lens
  reviewers (three on logic — requirements coverage, architecture soundness,
  edge-cases & verifiability; three on style/convention drift against the real
  target repo — naming, structure, error/test/docstring conventions),
  adjudicates findings to drop false positives, applies blocker/major fixes to
  the PRP in place, and re-reviews up to three rounds before appending a
  `## Review Log`. `draft-prp` now offers it as a hand-off and `prp-implement`
  warns (advisory) when a PRP carries no clean review log. Closes the last open
  seam in the PRP pipeline. Claude Code only for now; Warp twin deferred.

## [0.6.0] - 2026-06-15

### Added
- **idea-refine** skill: structured divergent/convergent ideation that runs
  upstream of `draft-prp`. Takes a raw idea through restate → sharpen (3–5
  questions) → 5–8 variations → cluster to 2–3 directions → stress-test →
  surface assumptions, and ships a one-pager (problem, recommended direction,
  assumptions-to-validate, MVP scope, explicit Not-Doing list) to
  `PRPs/ideas/<slug>.md`. One-pager fields map onto the PRP template (Not Doing
  → §1 strict non-goals, assumptions → §4.4 / SPECULATIVE markers) and the skill
  offers the `draft-prp` hand-off. Fills the raw-idea → formed-feature gap at the
  front of the PRP pipeline. Claude Code only for now; Warp twin deferred.

## [0.5.1] - 2026-06-13

### Added
- **asicdash** heatmap hover tooltips: date, total tokens, session count, and
  per-surface percentage split for the day — glanceable breakdown without
  opening the click-modal. Keyboard focus shows the same tooltip.

### Changed
- **asicdash** usage surfaces relabeled to match what the transcripts actually
  record. Every `~/.claude/projects` transcript is a Claude Code session; the
  only honest split is the launch entrypoint, so "Code/Cowork" is now
  "Terminal" (cli) / "Desktop" (claude-desktop app). The previous labels
  misfiled all desktop-launched Code sessions as "Cowork". Chat (claude.ai)
  still shown as "no local data".

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
