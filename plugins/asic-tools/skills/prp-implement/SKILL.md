---
name: prp-implement
description: Implement a Product Requirements Prompt (PRP) in two phases matching the author's workflow — first "review the PRP and plan" (drift-checked implementation plan, then PAUSE for approval), then "execute the plan" (task-by-task with per-task verification, leveled validation, and the full §10 close-out ritual). Use when the user says "implement the PRP", "execute PRP-NNN", "review the PRP and plan for implementation", "run this PRP", or invokes /prp-implement.
---

# prp-implement

A PRP is a contract: verified context, ordered tasks, validation levels, acceptance
criteria. This skill executes the contract and refuses to drift from it silently. Two
phases, hard pause between them — plan first, execute only on the user's go.

## Phase A — Review & Plan (ends with a PAUSE)

**Phase A's plan and Phase B's task loop run on the session model.** Skill frontmatter can set
`model`/`effort` for the current turn only, and the plan → PAUSE → execute handoff spans turns, so
this skill sets neither; whatever `/model` is set to is what plans and writes the code. Opus is the
recommendation. Only the delegated fan-outs below carry a tier of their own.

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

1. **Orient.** Compute the sizing tier here as A3 does (resolve and read
   `<asic-tools skills dir>/prp-draft/references/sizing.md`, count tasks, files and
   `citedFileCount`, apply the rubric, print the `SIZING:` block). A2.5 runs in place of A3, so
   this is the only place the tier is computed on a resume, and A4's scratchpad decision needs it.
   The **branch commit log is the authority on which §5 tasks are done** — but a commit
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
   When `PRPs/.work/prp-implement-active.md` survives and names this PRP, use its `Base commit:`
   as `BASE` instead — it was recorded at branch creation and cannot move.
   - Base drift — commits that landed on the base meanwhile: `git diff --name-only "$BASE" <base>`
   - Own progress so far: `git diff --name-only "$BASE" HEAD`

3. **Targeted drift re-check (not the full A3 sweep).** Re-verify only: (a) PRP-cited files (§1
   table, §4) that appear in the **base-drift** set — those may have changed under the plan — and
   (b) the files the **remaining (undone)** tasks will touch. Reuse A3's read-only verdict shape
   `{ citation, status: holds | drifted, evidence }` and its `citation-scout` fan-out, **sized by
   the tier** computed in step 1 (`sizing.md`) over the narrowed file set. State that shape in the
   delegation prompt here too — the scout serves two, and emits the one it is asked for.
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

**Size the sweep from the rubric.** Resolve it to an absolute path before reading: `prp-implement`
runs against an arbitrary repo, so a relative path into `prp-draft/references/` resolves against
*that* repo, not against this plugin. Compute the skills directory from this `SKILL.md`'s location
(it is `<…>/skills/prp-implement/SKILL.md`, so the skills dir is two levels up) and read
`<asic-tools skills dir>/prp-draft/references/sizing.md`. Confirm the file exists.

A3 computes the tier before it sizes the sweep: count the `Task N:` lines in §5.2 (scoped
`## 5.`->`## 6.`, per `sizing.md`), count the §1 `**Total:**` file count with parentheticals
stripped first, and count `citedFileCount` from the §4.1/§4.2 citations it is **already resolving**
in this same phase — one pass, not a second one. Apply `sizing.md`: max-wins across the two primary
axes, then the silent-failure modifier one tier up with its triggering category stated. Print the
`SIZING:` verdict block at the head of A3's drift report. Then take the sweep size from the tier →
knob table: inline drift check at S, a 3-agent fan-out at M, **one agent per citation cluster at L**, plus an expert re-read at XL. A
large PRP (subsystem scope, many §4 citations) fans out read-only subagents — the shipped
`citation-scout`, one per cited file or gotcha cluster — each returning a **structured verdict**,
never prose: `{ citation, status: holds | drifted, evidence }`. Naming that agent is what puts the
fan-out on its own tier, and the stated shape is what tells a two-shape scout which to emit (`evidence` = the `path:line`
that proves it, or the mismatch found). When `graphify-out/graph.json` exists, the
**graphify-first** directive still covers the fan-out, but the scout has no `Bash`: the main thread
runs `graphify query`/`explain`/`path` per citation cluster and
pastes the scoped graphify result into each delegation prompt, so the scout reads only what it
points at (see `docs/agent-tooling.md` rule 1). When there is no graph or the query returns nothing for a cluster, write "no graph" in that delegation prompt
so the scout orients by direct reading and says so. This phase stays read-only — no file is touched.
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
scratchpad during execution (Phase B). The tier from `sizing.md` decides:
**S and M keep none, L and XL keep one.**
Print the `SIZING:` verdict block in the plan A4 presents.
Keep it a plan, not a re-architecture — deviations from the PRP get
flagged as questions, not silently planned in.

**Then stop. Present the plan. Wait for "go" / "execute".** No file is touched in Phase A.
After presenting the plan, send one `PushNotification` (`status: "proactive"`, one line under
200 characters, e.g. `PRP-023 plan ready: 5 tasks, tier L — waiting for go`; load it via
`ToolSearch` if deferred). "Not sent" or no tool is normal — never retry.

## Phase B — Execute (on approval)

1. **Branch and run state**: on the head you branch from (main/develop, or a stacked PRP's
   parent branch), record the base commit with `git rev-parse HEAD`, then create
   `feature/prp-NNN-slug` per front matter. Never main. Write `PRPs/.work/prp-implement-active.md`
   per `${CLAUDE_SKILL_DIR}/references/run-state.md` at every tier; its `Skill file:` line is
   `${CLAUDE_SKILL_DIR}/SKILL.md`. If that file already names a different PRP, stop and ask. On
   a resume, follow that reference's resume rows.
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
   - **Run the task's gates before moving on.** A **runnable** gate (`CHECK:`/`EXPECT:`) runs as an
     ordinary permission-gated Bash call — it is **met only when the command exits `0` AND `EXPECT`
     matches its combined stdout+stderr**; a nonzero exit never passes because its error text
     contains the token. A **manual** gate is met by reviewed judgment and recorded as manual. Red
     gate = fix now, not later. There is no gate engine — the `CHECK:` string is untrusted data run
     as a normal command, and the Bash permission prompt is the approval boundary.
   - **Evidence, not assertion (claim-to-evidence).** A gate, §9 level or subagent result counts
     as passed only on output from this run: the command, its exit code and its result line
     (`32 passed in 2.4s`). "Should pass", an earlier session, or a subagent's own success report
     is not evidence; for subagent work, `git diff --stat` is.
   - After each task's commit, update `Current task:` in `PRPs/.work/prp-implement-active.md`.
   - **High-verify tasks (A4) run the four-pass loop before their gate may pass:** (1) implement the
     complete change, (2) reread as a domain expert and upgrade it, (3) hunt defects across
     correctness / integration / boundary behaviour — this is where the boundary or edge case (a DST
     transition, concurrent access, an expired token) is constructed and exercised — and (4) polish;
     repeat passes 2-4 until a full pass finds nothing, then run the gate. Ordinary tasks skip the
     loop (effort stays lopsided — a rename gets minutes, a ten-line timezone change gets the hour).
   - **Legacy fallback.** A task from a pre-gate PRP (PRPs 001–010) that pairs with a prose `VERIFY:`
     and carries no gate runs exactly as before — run its `VERIFY:` pairing and grade it as the
     earlier prose instruction did. Gate execution applies only to tasks that carry gates; it never
     strands a gate-less `VERIFY:` task with no instruction.
   - Surgical scope: only files in the PRP's summary table. Needed-but-unlisted change →
     stop, explain, get a decision. Noticed-but-unneeded work → log it under the scratchpad's
     "Discovered During Work" (or hold it in context if no scratchpad), don't do it.
4. **Validation levels** — §9 in order: syntax/style → unit → integration → e2e. Fix
   until green at each level before the next. Never mock-to-pass, never skip a level. An
   irrecoverable failure (env missing, hardware absent) → stop with exact state, what
   passed, what's blocked.
   Run §9 test and lint levels quietly — pytest `-q --tb=short` (drop `-v`; no `-q` if `addopts`
   has it: `-qq` hides `N passed`), `ruff check --output-format concise`; selection, paths and
   markers unchanged. A failing command returns only a ~10,000-character head-and-tail excerpt.
   Gate `CHECK:` strings are never rewritten.
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
   - **Block condition — scoped to what this PRP touched.** A **high or critical** finding
     **BLOCKS** when its `filePath`, **or any file in its `dataflow`**, is one this PRP changed
     (`git diff --name-only $(git merge-base HEAD <base>) HEAD`). The dataflow half is
     load-bearing: a taint introduced in a touched file whose sink lands in an untouched one is
     this PRP's defect, and a `filePath`-only test would wave it through. On a block: do not enter
     Phase C, do not check off acceptance; present the findings (rule, file:line, severity, the
     touched file that implicates them), fix under the PRP's surgical scope (new commits), and
     **re-run the gate**.
   - **Report every high/critical, blocking or not.** A high/critical in no touched file is
     **pre-existing debt**, not this PRP's defect — it does not block, and it is **still named in
     the final report** under its own count, so debt stays visible and cannot grow silently.
     Never fix one outside the PRP's surgical scope to make a count go green; record it and, when
     it warrants work, raise it as its own PRP.
     - `# GOTCHA: the scope rule is why this gate is usable at all. A repo may hold high findings`
       `# BY DESIGN — this one carries seeded vulnerable fixtures whose whole purpose is to make`
       `# Snyk report HIGH (evals/fixtures/vulnerable_app.py says so in its own docstring), plus a`
       `# real-shaped test key at evals/run_evals.py:199 proving redaction works. An unscoped`
       `# "any high blocks" rule blocks every PRP in such a repo forever, and "fixing" the fixtures`
       `# breaks the evals that prove the gate works. Snyk Code does NOT support per-finding .snyk`
       `# ignores (only whole-file exclusion), so the scope rule is the mechanism, not a policy.`
     - The judgment the rule cannot make: if this PRP made a **pre-existing** finding newly
       reachable without touching its file, say so and treat it as blocking. Scope is the default,
       not a licence to stop thinking.
   - `medium`/`low` → record as advisory in the final report and proceed.
   - Gate result (scans run, counts by severity, pass/block) is reported in Phase C step 7 and,
     when it blocks, becomes a Stop condition.

## Phase C — Close-out (part of execute, not optional)

1. **Acceptance checklist** (§9): verify every box against reality; check them off in the
   PRP file itself — then **reconcile every §5 gate**: **re-run each runnable gate against the
   current tree** as its evidence (re-running a gate is not re-running a task — the committed edits
   are left untouched), so a resumed cross-session run classifies gates from live output rather than
   results captured in a prior session, and classify each met / unmet / abandoned by qualified id
   (`Task N:Gn`). A gate impossible to satisfy is recorded `ABANDON: Gn <reason>` and never counts as
   met. A runnable `CHECK:` must be idempotent and stand on its own against a quiescent tree with no
   external services — service-dependent or single-shot acceptance belongs on a manual gate or must
   re-provision inside the `CHECK`, so re-running it never flips a genuinely-met gate to unmet.
   **Never write `Status: Implemented` or a done report while any gate is unmet or abandoned.** That
   state is a Stop condition (below), not a completion — hand it back to the user with the
   unmet/abandoned ids. The Phase B step 6 Snyk gate must have passed — no **blocking**
   high/critical per its scope rule; pre-existing debt in untouched files does not block, and is
   reported rather than fixed. A blocked gate means Phase C was never entered.
1b. **Converge pass — intent, not gates.** Read `${CLAUDE_SKILL_DIR}/references/converge.md`
   and run its fresh-context reviewer over the diff from the run-state `Base commit:`. Wait for
   the verdict. A confirmed `unmet`, `partial` or `contradicts` row is fixed under surgical
   scope; the fix re-enters B4 (§9 levels), B5 (commit), B6 (Snyk, scope rule unchanged) and a
   full step 1 gate reconciliation, then the pass is re-run once; a gap that survives the re-run
   is a Stop condition. `unrequested` and confirmed `manual` rows are reported, never a stop.
   Never stamp step 2 while the pass is pending or a confirmed gap stands.
2. **PRP front matter**: `Status: Implemented (YYYY-MM-DD)`, add `Branch:` if absent.
3. **Apply §10 verbatim**: PLANNING.md merge, TASKS.md completion entry (dated, plus the
   collected Discovered During Work items), CHANGELOG entry if mandated, serena memory
   `.serena/memories/prp/NNN_name.md` (serena MCP `write_memory` when connected, plain
   file otherwise).
4. **Refresh the PRP registry**: `PRPs/STATUS.md` is generated, never hand-edited — the script
   is the writer, you relay what it says.

   ```bash
   python3 "${CLAUDE_SKILL_DIR}/scripts/prp_status.py" PRPs --write
   ```

   | Exit | Meaning |
   |---|---|
   | `0` | Every PRP conformant. `PRPs/STATUS.md` rewritten. |
   | `1` | **A violation** — a status outside the five allowed values, a missing date or successor, a header with no `**Status:**` line, or a corpus breach (mis-named file, duplicate number). |
   | `2` | Usage error — bad path, empty corpus, or an existing `STATUS.md` without the generated banner. Nothing was written. |
   | `3` | **Indeterminate** — a PRP file is a symlink resolving outside the scanned directory. A script limitation, *not* a verdict. |

   Run it **after** step 2 has stamped this PRP's own front matter, so the row it renders is the
   one you just wrote. An exit `1` whose offender is **this PRP** is your defect: fix the header
   and re-run. An exit `1` naming a **sibling** PRP is recorded in the final report and does not
   stop close-out — Phase C's Stop conditions are about this PRP's own gates, and a sibling's
   stale header is exactly what the repo-level CI gate exists to catch. Never edit a sibling's
   status to make the exit code green.

5. **Refresh the knowledge graph** (best-effort, after the last task commit):

   ```bash
   if test -d graphify-out; then graphify update .; else echo 'graph skipped — no graphify-out/'; fi
   ```

   AST-only, no API cost, ~0.5s on a repo this size, and it re-extracts **code files only** —
   document nodes are refreshed by the semantic `/graphify --update`, not by this step. The
   `test -d` guard is load-bearing: without it, `graphify update .` in a repo with no graph builds
   one from scratch and leaves an untracked `graphify-out/` behind rather than skipping. It is
   written as an `if`, not `test -d … && …`: the `&&` form exits **1** on the skip path, which is
   indistinguishable from a real failure, so a graphless repo would report `graph refresh failed`
   every close-out and train the reader to ignore the line.
   **This never blocks close-out.** Report its outcome as exactly one line in the final report:

   | Outcome | Line |
   |---|---|
   | Updated | `graph refreshed (code nodes; document nodes need /graphify --update)` |
   | No `graphify-out/` — guard skipped the command | `graph skipped — no graphify-out/ in this repo` |
   | Command missing or failed | `graph refresh failed — <reason>` |

   A cache that would not rebuild is **not** an unmet gate and never enters the Stop conditions
   below. If `graphify-out/` is tracked in this repo rather than gitignored, the refresh still
   runs; say so in the report and leave the changes **unstaged** — the close-out never stages a
   regenerable artifact.

6. **Promote & retire the scratchpad** (when one was kept): fold its durable contents into the
   §10 artifacts just written — "Discovered During Work" items into the TASKS.md entry, the
   architectural map and Decisions into the serena memo — then delete
   `PRPs/.work/PRP-NNN-scratchpad.md`. It is working memory, not a deliverable; after a successful
   close-out nothing scratch survives in the tree. (Only a successful close-out deletes it: if the
   run aborted earlier at a documented STOP — B3 scope wall, B4 unrecoverable failure — the
   scratchpad is intentionally left on disk as resumable working memory and is named in the
   stop-state report; it is unstaged, so it never enters a commit.)
   Delete `PRPs/.work/prp-implement-active.md` in the same step, at every tier — a successful
   close-out leaves no run state.
7. **Final report**: acceptance checklist status, **gate reconciliation — counts of met / unmet /
   abandoned, with one line per gate (id, exit status, match result for runnable gates; 'manual —
   reviewed' for manual gates)**, files touched vs the PRP's summary
   table (any difference is a finding, explain it), test/validation outputs (one line per
   level), each passed claim as a claim-to-evidence row (`claim | command | exit | result line`,
   from this run), **the converge verdict (counts by status, rejected rows with evidence)**,
   **the Snyk gate result (scans run, findings by severity, pass)**, **the graph refresh
   outcome line**, commits made, and
   what remains for the user — push + merge via GitKraken, plus any deferred items with where
   they're recorded.
   Close with this optional, priced line (`<base>` = the run-state `Base commit:`): "Before you
   merge you can run `/code-review ultra <base>`: a cloud multi-agent review of this branch. It
   uploads a repo bundle (uncommitted changes included), shows findings only in your session, and
   uses one of three free runs, then ~$5–25 in usage credits." The skill never launches it. Then
   send one `PushNotification` with the outcome (A4 says how).

## Stop conditions (anywhere)

Stale PRP (A3), unmet dependency (A2), scope wall (B3), unrecoverable validation failure
(B4), **security gate block (B6: a high/critical Snyk finding in a file this PRP touched or in
its dataflow, or Snyk unauthenticated/unavailable — fail-closed)**, unmet or abandoned gate at
close-out (C1), **a confirmed gap surviving the converge re-run, or a converge reviewer that changed
the tree (C1b)**. Stopping with a precise state report is success; powering through the contract is
the failure mode. The stop-state report names `PRPs/.work/prp-implement-active.md` and, when one
was seeded, the surviving `PRPs/.work/PRP-NNN-scratchpad.md` — both intentionally retained as
resumable working memory, unstaged so they never enter a commit; only a successful Phase C
close-out deletes them. On any stop, send one `PushNotification` naming the condition (A4 says
how).
