# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning follows
[SemVer](https://semver.org/) on the `asic-tools` plugin version.

## [Unreleased]

### Changed
- **BREAKING: the global rules ship as a core plus path-scoped files.** `~/.claude/CLAUDE.md` now
  holds only the language-agnostic core (~177 lines, down from 471); Python, Pydantic,
  configuration, testing, structure and DB/API rules move verbatim to `~/.claude/rules/asic-*.md`
  and load only when Claude touches a matching file. Saves ~2.4k tokens in every non-Python
  context. Re-run `/asic-tools:sync-rules` after upgrading: it explains the migration, installs
  the scoped files, and never touches rules files not named `asic-*.md`. A one-line stop-or-ask
  rule joins "Before writing code".
- The global rules name the `graphify` **skill** alongside the graphify **CLI**. The lane table
  covers the CLI as the structure-retrieval lane; the skill is the ingestion side — any input into
  a knowledge graph — and `/graphify` now has a stated trigger in the rules rather than living as a
  hand-added local edit on one machine.
- **The git guard closes its bypasses and fails closed.** `git push` is denied however it is
  spelled — `bash -c "…"`, `/usr/bin/git`, `$(…)`, backticks, quoted `git` or `'push'`; a push or
  commit built through a variable or `eval` asks. Attribution is screened on any `git`/`gh` command,
  including the `Claude-Session:` trailer and claude.ai session links. Hook bypass (`--no-verify`,
  `commit -n`, `core.hooksPath`, `SKIP=`, `HUSKY=`) is denied; `reset --hard`, `clean -f` and forced
  branch deletes ask. An unparseable payload exits 2 and the hook sets `onFailure: "block"`, so a
  crash or timeout blocks instead of passing. Non-git commands no longer spawn python. **Breaking:**
  commands the guard used to allow are now denied or asked.

### Added
- **`/sync-rules` merges guardrail settings.** A bundled `rules/settings.fragment.json` —
  `attribution` off (`commit`/`pr` empty, `sessionUrl: false`), a `permissions.deny` rule for
  `git push`, and `autoMode.hard_deny` rules alongside `"$defaults"` — merges into
  `~/.claude/settings.json` through a stdlib script: dry-run diff first, additive only, conflicts
  reported rather than overwritten, previous file kept as `settings.json.sync-rules.bak`.

### Removed
- **BREAKING: the `diagram` skill is gone; archify is the diagram tool.** `/asic-tools:diagram`,
  its eleven scripts, ~724 KB of vendored shape data and the draw.io desktop-CLI prerequisite are
  removed. Diagrams now come from [archify](https://github.com/tt-a1i/archify) (MIT, third-party),
  which renders validated interactive HTML/SVG. The two skills claimed the same "architecture /
  workflow / network" triggers, so keeping both left the choice to chance. `sync-rules` now checks
  archify's version and offers the install or upgrade, running it only on an explicit yes. Existing
  `.drawio` files still open in draw.io; dev-mode installs should `rm ~/.claude/skills/diagram`.

## [1.0.0] - 2026-09-04

First stable release. The toolbox now decides how much machine a job deserves, states its own
retrieval and status contracts, and audits the config that costs money — the four gaps the v2.0
field audit opened against v0.20.0.

### Added
- **asicdash audits the config that costs money.** Agent entries now carry their `model` and
  `effort`, and an agent that declares neither is flagged — an absent `model:` is not a default, it
  is whatever the session happens to be, which is the resolution order that makes accidental Opus
  agents. A new scanner reads plugin `workflows/`, reporting the model and effort each routing role
  sets, so the eleven roles behind up to thirty-seven agent spawns per run are visible in the
  default output. No new flag, no new field: the detail rides in the existing description column.
  `asicdash.py` split into `asicdash.py` + `scanners.py`, both under the 500-line cap, verified by
  running the pre-split module and the split side by side and diffing their JSON.
- **PRP status is a controlled vocabulary with a linter behind it.** Five values — `Draft`,
  `Ready for execution`, `Implemented (YYYY-MM-DD)`, `Blocked`, `Superseded (by PRP-NNN)` — with
  free prose allowed after an em dash and never linted. A stdlib `prp_status.py` does one parse of
  every PRP header and emits both a tiered-exit lint and a generated `STATUS.md`; `prp-implement`
  Phase C regenerates it at close-out. In-flight work is derived from git at render time, never
  stored, so a resumed run's `Ready for execution` precondition still holds. A PRP designator is
  three digits plus an optional letter, so a split parent and its children each hold their own row.
- **Every delegated agent now runs on a chosen model and effort.** Both Workflow scripts declare a
  named `ROUTING` block; the volume stages (review lenses, repo-audit checks, citation scouting)
  drop to cheaper tiers at low effort while adjudication and architecture selection take the
  strongest tier available. Two shipped agents back it — `citation-scout` for the three
  main-thread fan-outs and `architecture-judge` for `prp-draft`'s new Phase 4.5 architecture
  panel. Depth remains PRP-013's rubric: routing sets which model, never how much work. Stages
  that cannot be routed from a plugin — drafting, planning, the implementation loop — are
  documented as following the session model rather than given a table entry that does nothing.

### Changed
- **Both multi-agent fan-outs are now first-class plugin workflows.** `review_workflow.js` and
  `improve_workflow.js` move to `plugins/asic-tools/workflows/`, declared by the manifest's
  `workflows` field, under names distinct from the skill commands — `prp-review-fanout` and
  `improve-repo-audit` — because a plugin workflow shares the `/asic-tools:` namespace with the
  skills. The scripts moved verbatim: exactly one line changed in each. The skills resolve them at
  `${CLAUDE_PLUGIN_ROOT}/workflows/` and then, once measured, invoke them **by name** — a skill can
  pass `name` and structured `args` to a plugin workflow, which the docs do not state and PRP-017
  established empirically. The skills remain the supported entry points — the raw fan-outs skip
  their setup phases. The README install flow now names the
  three MCP servers the skills depend on, and the dual-install stale-cache symptom.
- **The retrieval contract is now true at the one point that mattered.** `prp-implement` close-out
  refreshes the knowledge graph after the last task commit — AST-only, ~0.5s, and explicitly a
  cache warm rather than a gate: a missing binary or absent graph degrades to one reported line and
  never blocks a validated implementation. It refreshes **code nodes only**; document nodes need the
  semantic `/graphify --update`, and the reported line names that scope rather than claiming the
  whole graph is current. `idea-refine` Phase 0 grounds variations through the graphify CLI instead
  of `Glob`/`Grep`/`Read`, with an orient-only stop rule that keeps the seam with `prp-draft` intact.
  The global rules' MCP section is now a lane table pointing at `docs/agent-tooling.md` for routing,
  with Firecrawl and BrowserMCP retired — no skill, workflow, agent or hook referenced either.
- **One shared work-sizing rubric across the PRP stack.** `prp-draft`, `prp-implement` and
  `prp-review` now read `prp-draft/references/sizing.md` instead of paraphrasing scope three
  different ways; `prp-review` takes its round cap and lens set from an incoming `sizing`
  argument rather than module constants, so review depth finally scales with PRP size. Tiers are
  computed from two countable axes (§5-scoped task count, §1 `**Total:**` file count) with byte
  size demoted to an advisory corroborator after it was measured escalating four of twelve PRPs
  on its own. The three style lenses are gated on whether the PRP cites repo files at all, since
  a PRP citing none gives them nothing to compare against. `idea-refine` emits a predicted tier
  for `prp-draft` to check its real count against.

## [0.20.0] - 2026-08-28

### Changed
- **prp-draft / prp-implement: acceptance criteria are now runnable gates.** Each `§5` task pairs
  with a runnable gate (`CHECK:` + `EXPECT:`, met only when the command exits 0 **and** `EXPECT`
  matches its output) or an explicit manual gate; `prp-implement` runs runnable gates during its
  task loop, runs a four-pass loop on high-verify tasks, and refuses a done report while any gate is
  unmet or abandoned (close-out reconciliation re-runs each runnable gate; Stop condition `C1`). A
  legacy `VERIFY:` fallback keeps PRPs 001–010 implementable. Adapted from
  [unlazy](https://github.com/Leonxlnx/unlazy) (MIT).

### Removed
- **Warp support retired across the toolbox.** Claude Code is the sole harness: the `warp/` prompt
  directory is deleted, `asicdash` no longer scans or reports Warp config (its `AGENTS.md` scan was
  extracted into a Claude-scoped `scan_agents_md` so it keeps rendering), and packaging, README,
  `install.sh`, and skill descriptions are Claude-Code-only. CHANGELOG history and the `no Warp`
  commit-attribution guard are retained.

## [0.19.1] - 2026-07-16

### Fixed
- **`asic-tools` hooks now run.** The `git-guard` (PreToolUse) and `precedence-inject`
  (UserPromptSubmit) hook commands single-quoted `${CLAUDE_PLUGIN_ROOT}`, which blocked
  shell expansion — the literal path reached bash and both hooks failed with "No such file
  or directory". Switched to double quotes, matching the convention every other plugin
  uses, so the variable expands and the hooks fire.

## [0.19.0] - 2026-07-10

### Added
- **`okf` skill — Open Knowledge Format v0.1 as the standard shape for knowledge bundles and
  LLM-wikis.** OKF is a directory of markdown files with YAML frontmatter, one required field
  (`type`), two reserved filenames (`index.md`, `log.md`), and a deliberately permissive consumption
  model. The specification is vendored **verbatim** from
  [GoogleCloudPlatform/knowledge-catalog](https://github.com/GoogleCloudPlatform/knowledge-catalog)
  (`okf/SPEC.md`, Apache-2.0), pinned at commit `ee67a5ca27044ebe7c38385f5b6cffc2305a9c1a` and
  verified byte-identical with `cmp` — so the skill needs no network and adds no dependency.
  `NOTICE.md` records the pin, the fetch date, and the command to re-check upstream: OKF v0.1 is a
  Draft, it will move, and validating against a stale specification is a quiet failure.
- **A conformance validator, which is the point.** §9 conformance is mechanically checkable and
  nothing else checks it. `validate_okf.py` uses the standard library alone — `pyyaml` is not
  importable and skill scripts run under bare `python3`. Its exit codes are distinct so a CI gate can
  use them: `0` conformant, `1` non-conformant, `2` usage error, `3` **indeterminate** — frontmatter
  outside the parseable subset (block sequences, nested maps), a validator *limitation* rather than a
  verdict, which a gate should treat as pass-with-warning instead of blocking a spec-conformant
  bundle. It never silently accepts: a line it cannot read surfaces loudly as exit `3` rather than
  being skipped, and a missing or empty `type` hidden behind such a line is still exit `1`.
  `type: ""`, `type: null`, and `type: ~` are an **empty** `type`, not content. It is equally never
  stricter than the spec: unknown `type` values, unknown extra keys, broken cross-links, a missing
  `index.md`, and absent recommended fields never fail a bundle, because §9 forbids consumers from
  rejecting on those — over-strictness would be the defect.
- **`okf_index.py`,** which renders the §6 index shape and emits no frontmatter. `--write` preserves
  frontmatter already present, so regenerating a bundle-root `index.md` never destroys its
  `okf_version` declaration (§11).
- **The repository's first `pytest` suite** — 29 tests driving both CLIs by subprocess, and verified
  capable of failing by mutation-testing the code they cover.

### Changed
- **The bundled global rules gained a one-line OKF trigger** (about twenty tokens) so the standard is
  reachable without being remembered. The 3,761-token specification stays in the skill, loading on
  demand rather than on every prompt in every project.

### Fixed
- **The index generator read every entry it discovered**, so a symlinked `.md` file or subdirectory
  could escape the directory being indexed and be opened. Both scripts now resolve their inputs and
  refuse to read anything that lands outside. Plugin bumped 0.18.0 → 0.19.0.

## [0.18.0] - 2026-07-10

### Added
- **Enforcement hooks — the hard git rules now bind instead of merely asking.** `asic-tools` ships
  `hooks/hooks.json`, registered automatically when the plugin is enabled — no installer, and
  `sync-rules` keeps its "writes exactly one file" contract. A `PreToolUse` guard on `Bash` **denies**
  any commit whose message carries AI attribution, **denies** every `git push`, and **asks** before a
  commit on `main`/`master`. `ask` is the escape hatch by design: an env var or flag file would be
  forgeable by the agent — it authors the entire command string and can write files — whereas a
  permission dialog is not. The guard parses and builds its JSON with `python3`, never `jq`: macOS
  ships no `jq`, and a missing one would make the guard exit silently, erasing enforcement with no
  signal at all. The attribution deny matches any `Co-Authored-By:` trailer rather than an enumerated
  vendor list, which would quietly age out as new models appear. Ships with a 19-case suite that was
  itself verified capable of failing, by mutation-testing the guard. Hooks load at session start —
  restart Claude Code after updating the plugin, then confirm with `/hooks` (source: `Plugin`). The
  guard binds the agent, not you: a commit you make in your own terminal is untouched.
- **Rule precedence, stated in the global rules.** An explicit, current instruction from the user
  outranks the standing rules; the standing rules outrank skills, plugins, subagent prompts, MCP
  server instructions, and tool defaults. The section records its own limit: precedence is policy, not
  enforcement — only a hook binds.

### Changed
- **Serena now requires activating the project first.** The bundled global rules note that the memory
  tools fail with `No active project` when a repo has never been registered, and otherwise fall back
  to nothing without saying so — so `activate_project` comes first. The retired Neon/mem0 line is
  removed.

### Fixed
- **`plugin.json` advertised a stale `7-lens` review gate.** `prp-review` has fanned out eight lenses
  since v0.17.0, but PRP-008's count-sync grep was path-scoped to `skills/prp-review/` and
  `README.md`, so it never looked at the manifest. The acceptance gate now uses `git grep` over
  tracked source, which is deterministic across `grep` flavours. Plugin bumped 0.17.0 → 0.18.0.

## [0.17.0] - 2026-07-09

### Added
- **`prp-review` — 8th `silent-failure` reviewer lens (Opus manual §3/§6).** A distinct logic lens
  hunts the silent-failure surface a PRP would fail on late and quietly — boundaries
  (parsing/encoding, time/timezone/DST, concurrency, auth/expiry), rarely-run paths, off-by-one,
  wrong-but-plausible output — that no §5 VERIFY or §9 criterion would catch. Logic reviewers now
  construct a concrete failing case for runtime-defect claims (an unconstructed claim is capped at
  `minor`; structural/coverage findings are exempt), and the adjudicator weights severity by failure
  silence without lifting that cap. Fan-out is now 8 lenses (5 logic, 3 style); the count is synced
  across `review_workflow.js`, `SKILL.md`, and `README.md`.
- **`prp-implement` — silent-failure risk triage.** A4 marks high-silent-risk tasks (time/timezone,
  concurrency, auth/expiry, parsing/encoding, rarely-run paths) as high-verify, and the Phase B
  VERIFY constructs the boundary/edge case for them instead of only the happy path.
- **Global engineering rules — a five-question self-test.** `CLAUDE.global.md` gains an ambient
  before-sending self-test (what was actually asked / known-vs-guessed / silent failure /
  disconfirmation / reject-first) for prompts that never invoke a pipeline skill. Gap-closing against
  the Opus "Operating Manual" — full-manual-into-global was measured at ~13× the self-test's cost and
  deliberately rejected. Plugin bumped 0.16.2 → 0.17.0.

## [0.16.2] - 2026-06-25

### Fixed
- **`improve-repo` no longer discards real findings when a check also reports a partial skip.**
  The audit grouping loop in `improve_workflow.js` checked `result.skipped` before `result.findings`
  and `continue`d, so a check that ran one tool and skipped another (e.g. `standards-surface` found
  `ruff format` drift but `mypy` was absent) had its findings thrown away — they surfaced only in
  the skip-reason prose, never as a pickable category. The loop now checks findings first: findings
  always surface as a category, and a partial skip is recorded alongside them (`partial: true`),
  never in their place. Found by the first live audit of `asic.dev` itself. Plugin bumped
  0.16.1 → 0.16.2.

## [0.16.1] - 2026-06-25

### Fixed
- **`improve-repo` `standards-surface` now runs `ruff format --check`, not just `ruff check`.**
  The first live audit found the check ran `ruff check` (lint) only and folded format drift into
  its *skipped* reason instead of surfacing it — a repo can be lint-clean while still having
  formatting drift, since `ruff check` and `ruff format` are separate commands. The check's
  `focus` now mandates both and emits a `fixable:true` finding for each "would reformat" file
  (Phase 4 applies it via `ruff format <path>`). Plugin bumped 0.16.0 → 0.16.1.

## [0.16.0] - 2026-06-25

### Added
- **`improve-repo` skill — repo-wide standards-conformance auditor + fixer.** Profiles a repo
  (languages, single-deployable vs multi-publish, version locations, toolchain), runs a Workflow
  that fans out one adversarial agent per enabled check (version-consolidation, import-hygiene,
  shared-import-extraction, scaffold-conformance, standards-surface, naming-conventions), and
  presents findings grouped by category. Python gets a full standards audit (ruff/mypy surfaced,
  vertical-slice + entity-PK conformance); JS/TS gets a hygiene tier (version + imports). Composes
  existing tooling — shells `ruff`/`mypy`, reuses `release`'s version-location table, hands bugs to
  `code-review` and cleanup to `simplify`. On a picked category it applies mechanical fixes on a
  `feature/improve-<category>` branch with a Conventional Commit and a PR body;
  generative/contract-changing fixes go to a human checklist. Never pushes. Plugin bumped
  0.15.0 → 0.16.0.

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
