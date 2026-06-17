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
  user decision). In-progress branch already exists → report its state first.
- **Dependencies** (front matter `Depends on`) are implemented — check
  `.serena/memories/prp/` status memos and the codebase artifacts they name.
- **Tooling** named in §7/§9 commands actually runs in this repo.
- **Review log** (advisory, never blocking): if the PRP has no `## Review Log` section, or its
  log records residual blockers, warn the user that the PRP was not (cleanly) hardened by
  `prp-review` and recommend running `/asic-tools:prp-review` first — then proceed if they
  confirm. Do not refuse on this basis.

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
that proves it, or the mismatch found). This phase stays read-only — no file is touched.
Merge the verdicts into a drift table.

Any `drifted` row — file gone, contract changed, gotcha invalidated → STOP. Present the
drift table, propose the PRP amendment per row, let the user decide. Executing a stale PRP
produces confident wrong code — the exact failure PRPs exist to prevent.

### A4. Plan

Produce the implementation plan: §5 task list restated with current-state notes per task,
test-first ordering where §7 defines the tests, validation checkpoints (§9 levels mapped
to when they run), branch name from front matter, and any risks or SPECULATIVE markers
found in the PRP. Include a **scratchpad decision**: whether this run keeps a working
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
3. **Task loop** — §5 order, strictly:
   - **Scratchpad turn** (when one exists): read it at the top of the task to orient from the
     map and prior decisions instead of re-reading source already mapped; at the bottom append
     the run's new findings — the decision taken and why, drift discovered, and any
     "Discovered During Work" items. This is the anti-decay step on a long run.
   - Tests for the task first when §7 defines them (write failing → implement → green).
   - Implement per §6; re-read the relevant §4.4 CRITICALs immediately before touching
     each file they concern.
   - Run the task's VERIFY pairing before moving on. Red verify = fix now, not later.
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

## Phase C — Close-out (part of execute, not optional)

1. **Acceptance checklist** (§9): verify every box against reality; check them off in the
   PRP file itself.
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
   level), commits made, and what remains for the user — push + merge via GitKraken, plus
   any deferred items with where they're recorded.

## Stop conditions (anywhere)

Stale PRP (A3), unmet dependency (A2), scope wall (B3), unrecoverable validation failure
(B4). Stopping with a precise state report is success; powering through the contract is
the failure mode. When a scratchpad was seeded, the stop-state report names the surviving
`PRPs/.work/PRP-NNN-scratchpad.md` — it is intentionally retained as resumable working memory,
unstaged so it never enters a commit; only a successful Phase C close-out deletes it.
