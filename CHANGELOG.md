# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning follows
[SemVer](https://semver.org/) on the `asic-tools` plugin version.

## [0.15.0] - 2026-06-22

### Added
- **YAGNI decision ladder in the global rules.** New `## Decision ladder` section in
  `CLAUDE.global.md` (after Philosophy): a stop-at-first-rung checklist — need-to-exist (YAGNI)
  → stdlib → native platform feature → installed dependency → one line → the minimum that works
  — with a **non-negotiable carve-out** (trust-boundary validation, authn/authz, error/data-loss
  handling, accessibility are never skippable; "lazy, never negligent"). Ladder adapted from
  `ponytail` (MIT). Cross-referenced from `prp-draft`'s `style_guide.md` so every drafted PRP
  encodes it in §3/§11.
- **Over-build lens in `prp-review`.** A 7th reviewer (4 logic, 3 style) walks a PRP's proposed
  design through the ladder rungs; the `architecture` lens narrows to soundness/fit so the two do
  not duplicate. No schema change. Plugin bumped 0.14.1 → 0.15.0. Run `sync-rules` post-merge to
  deploy the new rules to `~/.claude/CLAUDE.md`; paste the same block into the Warp Drive global rule.

## [0.14.1] - 2026-06-20

### Changed
- **Eval `d2` now asserts the SNYK_TOKEN UUID is redacted** instead of tracking it as a gap.
  DataSentry 0.3.0 added a dedicated `snyk-token` rule that redacts bare-UUID tokens
  (`SNYK_TOKEN=…` → `[DS:snyk-token:…]`), closing P4. Requires datasentry ≥ 0.3.0. Docs updated
  (`docs/prp-loop-hardening.md` P4 marked closed, `evals/README.md`). Plugin bumped 0.14.0 → 0.14.1.

## [0.14.0] - 2026-06-20

### Added
- **In-loop security gate (Snyk MCP) in `prp-implement`.** New required Phase B step 6 runs once,
  after all §9 validation passes and before Phase C close-out — a gate, never a per-tool-call
  check. It is **fail-closed**: any high/critical Snyk finding blocks close-out until fixed and
  re-scanned clean, and an unauthenticated or unavailable Snyk is itself a block (never a silent
  pass). Scans are **adaptive**: `snyk_code_scan` always, `snyk_sca_scan` when a real
  manifest+lock exists, `snyk_iac_scan`/`snyk_container_scan` only when IaC/containers are present.
  Wired into the §9 acceptance check, the Phase C final report, and the Stop conditions.
  `snyk agent-scan` (supply-chain) is explicitly out of scope. Plugin bumped 0.13.1 → 0.14.0.
- **Retrieval-lane routing rules (`docs/agent-tooling.md`).** Hard rules fixing the three lanes —
  graphify CLI (structure), serena (symbols/memory), Ref (external docs) — with a per-PRP-step
  source table and a **verified-context rule**: every claim entering a PRP carries a citation
  (graph node, `path:line`, or Ref URL) or is marked `SPECULATIVE`. `prp-draft` now states the
  rule and points at the doc.
- **`evals/` harness.** Stdlib runner proving retrieval routing, the gate cannot be skipped, the
  Snyk gate blocks a seeded high-severity finding (live scan), and DataSentry redaction fires
  (with the UUID-token coverage gap tracked).

### Fixed
- **Reviewers and the drift fan-out no longer scan blind.** `prp-review`'s style-lens reviewer
  prompts and `prp-implement`'s A3/A2.5 Explore fan-out now require graphify-first orientation
  before reading cited files, and review findings must cite a PRP quote or a read `file:line` or
  be rejected by the adjudicator.
- **`prp-review` final-round verify no longer self-grades style fixes.** The verifier now
  re-confirms style-lens fixes against the cited repo file, not the PRP text alone.

### Changed
- **Dropped the dead `graphify-airi` MCP server** from `~/.claude.json`. It was hardwired to the
  Airi repo's graph, so calls from any other repo returned the wrong graph. All graphify retrieval
  now routes through the CLI (correct local graph). (Machine-local config change, not shipped in
  the plugin.)

## [0.13.1] - 2026-06-19

### Added
- **Four global engineering rules** in `CLAUDE.global.md` (and synced to `~/.claude/CLAUDE.md`):
  *reuse first* — exhaust existing implementations and patterns before introducing a new one;
  *no parallel patterns* — delete the old implementation when a new pattern replaces it;
  *no throwaway scripts* — one-off scripts stay in scratch space, never committed as permanent
  files; and *mock data only in tests* — never in dev or prod environments. Plugin bumped
  0.13.0 → 0.13.1.

## [0.13.0] - 2026-06-18

### Added
- **`diagram` skill — draw.io diagram generation.** Turns a natural-language description (or an
  existing repo's structure) into an editable `.drawio` file under `docs/diagrams/` and exports
  PNG/SVG/PDF via the draw.io desktop CLI, with a skippable vision self-check pass, a 2-round
  feedback loop, six diagram types (ERD/UML class/sequence/architecture/ML-DL/flowchart) with a
  selection heuristic, three style presets, vendor AWS/Azure/GCP/Kubernetes icons via a 10k+-shape
  search index, an AI/LLM logo resolver, and Python/JS-TS/Go/Rust code-to-diagram (Graphviz
  auto-layout). Ported and adapted (MIT) from Agents365-ai/drawio-skill (v1.14.0); the eleven helper
  scripts were rewritten to the project's Python conventions. Requires `brew install --cask drawio`;
  fails fast with the install command and a diagrams.net browser fallback when absent. Plugin
  bumped 0.12.1 → 0.13.0.

### Fixed
- **prp-review no longer mislabels applied fixes as residual blockers.** The review Workflow set
  `residual` to every final-round blocker unconditionally, so fixes that were successfully applied
  in the last round were reported as surviving blockers (`residual` equalled `applied_findings`). A
  new Verify phase now re-reads the edited PRP after the final apply and keeps only genuinely
  unresolved findings in `residual`.

## [0.12.1] - 2026-06-18

### Fixed
- **prp-review no longer hangs at the finalize stage.** The review Workflow's
  trailing "apply" agent ran without an output schema, so it returned free text
  with no convergence signal and could thrash (re-read, re-edit) until the
  workflow's final `await` stalled — recovered only by cache-resume. It now
  terminates in a structured `APPLY_SCHEMA` tool call, which is its stop signal.
  The same change fixes a `residual` mislabel: residual blockers were assigned
  before the apply ran on every round, so a final-round apply reported its own
  just-applied fixes as surviving blockers; now only genuinely unverified
  final-round blockers surface as residual.

## [0.12.0] - 2026-06-17

### Fixed
- **asicdash usage heatmap cells now show their activity color.** A CSS cascade
  bug rendered every heatmap cell (and the less→more scale swatches) with the
  empty `--surface-2` background: the base `.u-cell` rule was declared after the
  equal-specificity `.u-{surface}-{level}` color rules, so it always won. Active
  days looked inactive even though they were clickable. The colour rules are now
  emitted last so they paint as intended.

### Added
- **asicdash usage token totals at four granularities.** The Claude usage section
  now leads with a four-card panel — Today / Last 7 days / Last 30 days /
  All-time — each showing output (and input) token totals, so "how many tokens
  have I used" is answered at a glance instead of inferred from the heatmap.
  `collect_usage()` computes the trailing-window sums; the heatmap and per-day
  modal are unchanged.

## [0.11.0] - 2026-06-17

### Added
- **prp-draft directed exploration (graphify-first research).** When
  `graphify-out/graph.json` exists in the target repo, Phase 2 now leads with a
  graphify orientation pass (`graphify query`/`explain`/`path`) to identify which
  files the feature touches before opening any raw file, and the Explore fan-out
  subagent prompts carry the same graphify-first directive; Phase 1 gains a
  pointer to `graphify-out/wiki/index.md` for broad navigation. Gated on the
  graph existing — absent it, research behaves exactly as before. Makes
  prp-draft's own research embody the repo's standing graphify-before-grep/Read
  rule rather than fight it. The structured-evidence citation contract is
  unchanged: graphify orients toward files, the verified `path:line` still comes
  from reading them.

## [0.10.0] - 2026-06-17

### Added
- **prp-implement change-aware resumption.** When a PRP's `feature/prp-NNN-slug`
  branch already exists, A2 now routes through a new A2.5 sub-phase instead of a
  fresh run: it orients from the branch commit log (the authority on which tasks
  are done) enriched by the PRP-002 scratchpad, computes `git merge-base` and
  diffs to find the files that changed since the branch forked — both the run's
  own commits and commits that landed on the base meanwhile — runs a targeted
  drift re-check on only the affected cited files plus the remaining tasks' files
  (in place of the full A3 sweep), and resumes the task loop at the first undone
  task. Stays read-only through Phase A; never rebases, merges, or pushes — large
  base drift is reported for the user to reconcile. Completes the scratchpad story
  opened in 0.9.0.

## [0.9.0] - 2026-06-17

### Added
- **prp-implement working scratchpad.** On multi-task or subsystem PRPs, Phase B
  now seeds a gitignored working-memory file (`PRPs/.work/PRP-NNN-scratchpad.md`)
  from the A3 drift table and §4 context — architectural map, decisions, drift
  notes, and the live home for "Discovered During Work" — reads it at each task
  boundary to resist context decay on long runs, and at close-out promotes its
  durable contents into the existing §10 artifacts (TASKS.md, the serena memo)
  then deletes it. Trivial one- to two-task PRPs skip it; the practice scales to
  scope the same way the A3 drift check does. Builds on the existing "Discovered
  During Work" convention rather than replacing it.

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
