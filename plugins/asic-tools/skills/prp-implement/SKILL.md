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

The PRP was written against the codebase as of its Date. Verify it still holds:

- Every file in the §1 summary table and §4.2 tree exists at the stated path.
- Spot-check §4.4 gotchas and §6 before/after snippets against current code — line
  numbers shifted is fine; *semantics changed* is not.
- Dependency versions §4.1 cites vs lockfile now.

Material drift (file gone, contract changed, gotcha invalidated) → STOP. Report each
mismatch, propose the PRP amendment, let the user decide. Executing a stale PRP produces
confident wrong code — the exact failure PRPs exist to prevent.

### A4. Plan

Produce the implementation plan: §5 task list restated with current-state notes per task,
test-first ordering where §7 defines the tests, validation checkpoints (§9 levels mapped
to when they run), branch name from front matter, and any risks or SPECULATIVE markers
found in the PRP. Keep it a plan, not a re-architecture — deviations from the PRP get
flagged as questions, not silently planned in.

**Then stop. Present the plan. Wait for "go" / "execute".** No file is touched in Phase A.

## Phase B — Execute (on approval)

1. **Branch**: `feature/prp-NNN-slug` per front matter (create from main/develop head).
   Never main.
2. **Task loop** — §5 order, strictly:
   - Tests for the task first when §7 defines them (write failing → implement → green).
   - Implement per §6; re-read the relevant §4.4 CRITICALs immediately before touching
     each file they concern.
   - Run the task's VERIFY pairing before moving on. Red verify = fix now, not later.
   - Surgical scope: only files in the PRP's summary table. Needed-but-unlisted change →
     stop, explain, get a decision. Noticed-but-unneeded work → log it for
     "Discovered During Work", don't do it.
3. **Validation levels** — §9 in order: syntax/style → unit → integration → e2e. Fix
   until green at each level before the next. Never mock-to-pass, never skip a level. An
   irrecoverable failure (env missing, hardware absent) → stop with exact state, what
   passed, what's blocked.
4. **Commits** — logical groups (typically per task or per §6 file-section), Conventional
   format, ruff clean *before* each commit, no AI attribution, never push.

## Phase C — Close-out (part of execute, not optional)

1. **Acceptance checklist** (§9): verify every box against reality; check them off in the
   PRP file itself.
2. **PRP front matter**: `Status: Implemented (YYYY-MM-DD)`, add `Branch:` if absent.
3. **Apply §10 verbatim**: PLANNING.md merge, TASKS.md completion entry (dated, plus the
   collected Discovered During Work items), CHANGELOG entry if mandated, serena memory
   `.serena/memories/prp/NNN_name.md` (serena MCP `write_memory` when connected, plain
   file otherwise).
4. **Final report**: acceptance checklist status, files touched vs the PRP's summary
   table (any difference is a finding, explain it), test/validation outputs (one line per
   level), commits made, and what remains for the user — push + merge via GitKraken, plus
   any deferred items with where they're recorded.

## Stop conditions (anywhere)

Stale PRP (A3), unmet dependency (A2), scope wall (B2), unrecoverable validation failure
(B3). Stopping with a precise state report is success; powering through the contract is
the failure mode.
