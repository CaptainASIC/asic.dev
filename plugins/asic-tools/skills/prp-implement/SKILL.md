---
name: prp-implement
description: Implement a Product Requirements Prompt (PRP) in two phases matching the author's workflow — first "review the PRP and plan" (drift-checked implementation plan, then PAUSE for approval), then "execute the plan" (task-by-task with per-task verification, leveled validation, and the full §10 close-out ritual). Use when the user says "implement the PRP", "execute PRP-NNN", "review the PRP and plan for implementation", "run this PRP", or invokes /prp-implement.
---

# prp-implement

A PRP is a contract: verified context, ordered tasks, validation levels, acceptance
criteria. This skill executes the contract and refuses to drift from it silently. Two
phases, hard pause between them — plan first, execute only on the user's go.

## Phase A — Review & Plan (ends with a PAUSE)

### A1. Locate & load

PRP from the argument (number or name) or the conversation; otherwise newest
`Status: Ready for execution` in `PRPs/` — confirm when ambiguous. Read the PRP fully.
Then actually load §4.1's MUST READ list — the PRP mandates that context for a reason;
skipping it is the first way implementations go wrong.

### A2. Preconditions

- **Status** is `Ready for execution`. Already-Implemented → stop and ask (re-run is a
  user decision). In-progress branch already exists → this is a **resume**, not a fresh run:
  report its state, then run **A2.5 in place of A3** (A2.5 *is* the resume drift check — the
  full A3 sweep does **not** also run).
- **Dependencies** (front matter `Depends on`) are implemented — check
  `.serena/memories/prp/` status memos and the codebase artifacts they name.
- **Tooling** named in §7/§9 commands actually runs in this repo.
- **Review log** (advisory, never blocking): if the PRP has no `## Review Log` section, or its
  log records residual blockers, warn the user that the PRP was not (cleanly) hardened by
  `prp-review` and recommend running `/asic-tools:prp-review` first — then proceed if they
  confirm. Do not refuse on this basis.

### A2.5 Resume an in-progress run

Entered only when A2 found an existing `feature/prp-NNN-slug` branch for this PRP — work already
started. A2.5 runs **in place of A3**, not before it: it is the resume drift check, so the full A3
sweep does not also run on a resume. Do not re-run from scratch and do not assume the codebase froze
while the run was paused. Resume is **change-aware** and stays read-only, like A3:

1. **Orient.** The **branch commit log is the authority on which §5 tasks are done** — but a commit
   need not map 1:1 to a §5 task (per the commit policy, commits are logical groups, typically per
   task or per §6 file-section). First resolve the merge-base `BASE` exactly as step 2 does
   (`BASE=$(git merge-base HEAD <base>)`, the resumer naming `<base>`), then match
   `git log $BASE..HEAD --oneline` commits to §5 tasks by their
   subject and touched files — the same `$BASE` the own-progress diff uses, so done-detection and
   the diff share one baseline and stay correct under base drift; a task is **done** when a commit
   demonstrably covers it (its files are
   present in that commit and the §5 acceptance is met). When a single logical-group commit covers
   several tasks, mark all of them done; when a commit covers only part of a task (e.g. a per-file
   commit for a multi-file task), treat the task as **not done** and resume it. **Ambiguous → treat
   as not done** (conservative: re-doing an idempotent task is safe, skipping an unfinished one is
   not). Cross-reference the §5 task list and, when present, the scratchpad to disambiguate.
   If `PRPs/.work/PRP-NNN-scratchpad.md` survived (PRP-002 retains it on an aborted STOP), read it to
   *enrich* orientation — architectural map, decisions, prior drift notes — but do not read done-state
   from it: the scratchpad carries no structured done/pending field (that is §12 future work). If it
   is absent (a trivial PRP that elected no scratchpad, or a pre-scratchpad run), orient from the
   commit log alone and **widen step 3** to re-verify the union of **every PRP-cited file** with the
   remaining-task files (i.e. the full A3 citation set rather than only the base-drift intersection),
   compensating for the missing prior drift notes.

2. **Find what changed since the branch forked.** Resolve the base the feature forked from — do
   **not** read it from front matter (the PRP front matter declares only `Branch:`, the feature
   branch, never a base/fork field), and do **not** use `git rev-parse @{upstream}`: that resolves
   the branch's own remote-tracking mirror, not its fork parent, and is unset on a local feature
   branch. Instead, **ask the resumer to name the base branch** the feature forked from (for a
   stacked PRP it is the parent feature branch, e.g. `feature/prp-002-scratchpad` — not `main`).
   Then `BASE=$(git merge-base HEAD <base>)`.
   - Base drift — commits that landed on the base meanwhile: `git diff --name-only "$BASE" <base>`
   - Own progress so far: `git diff --name-only "$BASE" HEAD`

3. **Targeted drift re-check (not the full A3 sweep).** Re-verify only: (a) PRP-cited files (§1
   table, §4) that appear in the **base-drift** set — those may have changed under the plan — and
   (b) the files the **remaining (undone)** tasks will touch. Reuse A3's read-only verdict shape
   `{ citation, status: holds | drifted, evidence }` and its Explore fan-out, scaled to the count.
   Cited files outside the base-drift set have **no observable change since the fork** (git shows
   them unmodified between `$BASE` and `<base>`), so they are safe to trust without re-verifying —
   the skip is justified by git alone, not by any plan-time ledger.
   Any `drifted` row → STOP exactly as A3 (present, propose amendment, user decides). If base drift
   is large or conflicts with the branch, report it and stop — rebasing or merging the base is the
   user's call via GitKraken; this skill never rebases, merges, or pushes.

4. **Plan the remainder.** A4 produces a plan covering only the undone tasks, noting "resuming from
   Task N" and any re-check drift, then PAUSES for "go" as usual. On approval, Phase B re-enters the
   task loop at the first undone task (never re-running a committed one). On a resume the existing
   scratchpad continues as working memory — Phase B's seed step (which initialises Decisions and
   Discovered During Work as empty for a fresh run) is **skipped**: do not re-seed or overwrite the
   surviving scratchpad, append to it.

### A3. Drift check (the step that earns this skill its keep)

The PRP was written against the codebase as of its Date. Verify it still holds across
three axes:

- Every file in the §1 summary table and §4.2 tree exists at the stated path.
- §4.4 gotchas and §6 before/after snippets vs current code — line numbers shifted is
  fine; *semantics changed* is not.
- Dependency versions §4.1 cites vs the lockfile now.

Scale the sweep to the PRP. A contained PRP (a handful of citations) checks inline. A
large PRP (subsystem scope, many §4 citations) fans out read-only subagents (Explore) —
one per cited file or gotcha cluster — each returning a **structured verdict**, never
prose: `{ citation, status: holds | drifted, evidence }` (`evidence` = the `path:line`
that proves it, or the mismatch found). When `graphify-out/graph.json` exists, each
subagent's prompt must instruct **graphify-first** (orient with `graphify query`/`explain`/
`path` before reading the cited file) — the directive applies to subagents, not only the main
thread (see `docs/agent-tooling.md`). This phase stays read-only — no file is touched.
Merge the verdicts into a drift table.

Any `drifted` row — file gone, contract changed, gotcha invalidated → STOP. Present the
drift table, propose the PRP amendment per row, let the user decide. Executing a stale PRP
produces confident wrong code — the exact failure PRPs exist to prevent.

### A4. Plan

Produce the implementation plan: §5 task list restated with current-state notes per task,
test-first ordering where §7 defines the tests, validation checkpoints (§9 levels mapped
to when they run), branch name from front matter, and any risks or SPECULATIVE markers
found in the PRP. **Silent-failure triage (manual §3):** mark §5 tasks whose failure would
surface *late and quietly* — time/timezone/DST, concurrency, auth/expiry, parsing/encoding,
rarely-run paths — as **high-verify** so Phase B scrutinises them harder; effort is lopsided (a
repo-wide rename gets minutes, a ten-line timezone change gets the hour), and loud build-caught
tasks need no flag. Include a **scratchpad decision**: whether this run keeps a working
scratchpad during execution (Phase B). A multi-task or subsystem PRP does; a trivial one- or
two-task PRP that finishes inside one context window does not — scale it to scope as A3 does.
Keep it a plan, not a re-architecture — deviations from the PRP get
flagged as questions, not silently planned in.

**Then stop. Present the plan. Wait for "go" / "execute".** No file is touched in Phase A.

## Phase B — Execute (on approval)

1. **Branch**: `feature/prp-NNN-slug` per front matter (create from main/develop head).
   Never main.
2. **Scratchpad** (only when A4 elected one — skip for a trivial PRP): seed
   `PRPs/.work/PRP-NNN-scratchpad.md` as the run's working memory. Scratch is never committed —
   the commit step's surgical scope (only files in the PRP's summary table) already excludes
   `PRPs/.work/`, so no `.gitignore` edit is needed (a `.gitignore` change would itself fall
   outside the summary table). Seed from Phase A's A3 drift findings (the table when one was built
   on fan-out, else the inline drift verdicts) and §4.1/§4.2 context, four sections:
   **Architectural map** (cited `path:symbol` → role — reused from the A3 drift table on a fan-out
   run, else derived now from the §4.1/§4.2 files already read in A3), **Decisions** (empty),
   **Drift notes** (from A3), **Discovered During Work** (empty — the live home for the items step 3
   collects).
3. **Task loop** — §5 order, strictly (on a **resume** per A2.5, start at the
   first task not already done — never re-run a task already committed):
   - **Scratchpad turn** (when one exists): read it at the top of the task to orient from the
     map and prior decisions instead of re-reading source already mapped; at the bottom append
     the run's new findings — the decision taken and why, drift discovered, and any
     "Discovered During Work" items. This is the anti-decay step on a long run.
   - Tests for the task first when §7 defines them (write failing → implement → green).
   - Implement per §6; re-read the relevant §4.4 CRITICALs immediately before touching
     each file they concern.
   - Run the task's VERIFY pairing before moving on. Red verify = fix now, not later. For a
     **high-verify** task (A4), the VERIFY is not the happy path alone — construct the boundary
     or edge case (a DST transition, concurrent access, an expired token) and confirm it before
     moving on.
   - Surgical scope: only files in the PRP's summary table. Needed-but-unlisted change →
     stop, explain, get a decision. Noticed-but-unneeded work → log it under the scratchpad's
     "Discovered During Work" (or hold it in context if no scratchpad), don't do it.
4. **Validation levels** — §9 in order: syntax/style → unit → integration → e2e. Fix
   until green at each level before the next. Never mock-to-pass, never skip a level. An
   irrecoverable failure (env missing, hardware absent) → stop with exact state, what
   passed, what's blocked.
5. **Commits** — logical groups (typically per task or per §6 file-section), Conventional
   format, ruff clean *before* each commit, no AI attribution, never push. Never commit the
   scratchpad — `PRPs/.work/` is outside every PRP's summary table, so surgical scope excludes it.
6. **Security gate (Snyk MCP) — required, fail-closed.** Runs **once**, after every §9
   validation level is green and all task commits are made, **before** Phase C. This is the only
   security scan in the loop — a gate, never a per-tool-call check. `snyk agent-scan`
   (supply-chain) is **out of scope** here; the user runs it separately.
   - **Auth precondition.** Confirm the Snyk MCP is reachable and authenticated
     (`mcp__Snyk__snyk_auth` if a check is needed). Unauthenticated, MCP absent, or a scan that
     errors → **treat as a BLOCK** (fail-closed): stop with the exact state, never proceed on an
     unknown security posture.
   - **Adaptive scan selection** (scan what the repo actually contains):
     - `mcp__Snyk__snyk_code_scan` — **always** (SAST over the implemented code).
     - `mcp__Snyk__snyk_sca_scan` — only if a real dependency manifest **and** lockfile exist
       (`package.json`+lock, `pyproject.toml`+`uv.lock`/`requirements.txt` with real deps,
       `go.mod`, …). Skip with a logged reason when there are no resolvable dependencies.
     - `mcp__Snyk__snyk_iac_scan` — only if IaC is present (terraform, k8s manifests,
       CloudFormation).
     - `mcp__Snyk__snyk_container_scan` — only if a Dockerfile / image build is present.
   - **Block condition.** Any finding of severity **high or critical** → **BLOCK**: do not enter
     Phase C, do not check off acceptance. Present the findings (rule, file:line, severity), fix
     them under the PRP's surgical scope (new commits), and **re-run the gate** — it must return
     no high/critical before the loop may advance. `medium`/`low` → record as advisory in the
     final report and proceed.
   - Gate result (scans run, counts by severity, pass/block) is reported in Phase C step 5 and,
     when it blocks, becomes a Stop condition.

## Phase C — Close-out (part of execute, not optional)

1. **Acceptance checklist** (§9): verify every box against reality; check them off in the
   PRP file itself. The Phase B step 6 Snyk gate must have passed (no high/critical) — a blocked
   gate means Phase C was never entered.
2. **PRP front matter**: `Status: Implemented (YYYY-MM-DD)`, add `Branch:` if absent.
3. **Apply §10 verbatim**: PLANNING.md merge, TASKS.md completion entry (dated, plus the
   collected Discovered During Work items), CHANGELOG entry if mandated, serena memory
   `.serena/memories/prp/NNN_name.md` (serena MCP `write_memory` when connected, plain
   file otherwise).
4. **Promote & retire the scratchpad** (when one was kept): fold its durable contents into the
   §10 artifacts just written — "Discovered During Work" items into the TASKS.md entry, the
   architectural map and Decisions into the serena memo — then delete
   `PRPs/.work/PRP-NNN-scratchpad.md`. It is working memory, not a deliverable; after a successful
   close-out nothing scratch survives in the tree. (Only a successful close-out deletes it: if the
   run aborted earlier at a documented STOP — B3 scope wall, B4 unrecoverable failure — the
   scratchpad is intentionally left on disk as resumable working memory and is named in the
   stop-state report; it is unstaged, so it never enters a commit.)
5. **Final report**: acceptance checklist status, files touched vs the PRP's summary
   table (any difference is a finding, explain it), test/validation outputs (one line per
   level), **the Snyk gate result (scans run, findings by severity, pass)**, commits made, and
   what remains for the user — push + merge via GitKraken, plus any deferred items with where
   they're recorded.

## Stop conditions (anywhere)

Stale PRP (A3), unmet dependency (A2), scope wall (B3), unrecoverable validation failure
(B4), **security gate block (B6: a high/critical Snyk finding, or Snyk unauthenticated/
unavailable — fail-closed)**. Stopping with a precise state report is success; powering through the contract is
the failure mode. When a scratchpad was seeded, the stop-state report names the surviving
`PRPs/.work/PRP-NNN-scratchpad.md` — it is intentionally retained as resumable working memory,
unstaged so it never enters a commit; only a successful Phase C close-out deletes it.
