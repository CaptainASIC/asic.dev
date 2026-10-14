# Converge pass — Phase C step 1b

Gates prove what the PRP chose to test. This pass checks what the PRP asked for: one fresh,
read-only reviewer compares the branch diff with the PRP's stated intent and reports gaps that
affect correctness or a stated requirement. It never edits code.

## 1. Resolve the inputs (main thread)

- `PRP` — the PRP file path.
- `BASE` — the `Base commit:` line of `PRPs/.work/prp-implement-active.md` (on a resume with no
  file, Phase B step 1 reconstructed it per `run-state.md`). Never a `git merge-base` computed
  here, at close-out.
  Resolve it once, here, and keep that value: every later step (including the re-run) uses the
  held copy and never re-reads `Base commit:` after the reviewer ran.
- `FILES` — `git diff --name-only "$BASE" HEAD`.
- Fingerprint before: save the output of this one command (it hashes content, not only path
  status, and covers the PRP and run-state file even when they sit in gitignored paths):

      { git rev-parse HEAD; git status --porcelain; git diff HEAD --binary | shasum; git ls-files --others --exclude-standard -z | xargs -0 shasum | shasum; shasum "$PRP" PRPs/.work/prp-implement-active.md; }

  It does not see edits to other gitignored paths or outside the repo; say so in the report if
  the reviewer's return hints at one.

## 2. Delegate

Agent tool, `subagent_type: "general-purpose"` named explicitly — a fork would inherit this
conversation and is not a fresh context — with `model: "opus"` and `effort: "high"`. In an
interactive session it runs in the background: wait for its completion notification before any
other Phase C step. Prompt, with the placeholders filled:

    You are reviewing a finished implementation against the PRP that specified it. Read <PRP>:
    §1 (the Goal paragraph and the Strict non-goals), the subsection of §2 whose heading contains
    "Desired Behaviour" (all of §2 if none does), and §9.4. List every requirement those
    sections state, with exactly one row sourced "§9.4 box N" per §9.4 checkbox. Then read the change with
    `git diff <BASE> HEAD` (changed files: <FILES>) and the surrounding code where you need it.
    Classify each requirement:
    `met` — implemented; cite the path:line in the diff that implements it. For a requirement
    no diff line can show (a non-goal absence, a branch, commit or size rule), cite instead the
    read-only command you ran and its result line, as `command → result`. A gate id or a
    passing check is not evidence: prove it yourself.
    `manual` — provable only in a live session or by a human (a live-session probe, a manual
    smoke); say what would prove it. Never use it for anything the diff or a command can show.
    `unmet` — absent from the code.
    `partial` — present but incomplete; say what is missing.
    `contradicts` — the code conflicts with it, or does something a non-goal forbids.
    Add an `unrequested` row for each behaviour change no section asks for.
    Flag only gaps that affect correctness or a stated requirement. Style, naming and extra
    tests are not findings. You are read-only: do not edit, stage, commit, or switch branches.
    Return only a JSON array of {"requirement", "source", "status", "evidence"}, where source is
    "§1 Goal", "§1 non-goal", "§2 Desired Behaviour step N" or "§9.4 box N".

## 3. Check the return

1. Re-take the fingerprint with the same command. Any difference from step 1 means the reviewer
   changed the commit, the working tree, the PRP or the run state:
   discard its verdict, report what changed, and stop (Stop condition C1b). Never clean up its
   changes silently.
2. A prose return, rows missing `status`/`evidence`, a `met` row whose evidence is neither a
   `path:line` in the diff nor a `command → result`, or a count of `§9.4 box N` rows that differs
   from the number of §9.4 checkboxes, is re-requested once; a second malformed return means the
   pass did not run — stop.
3. For each `unmet`, `partial` or `contradicts` row, open the cited evidence yourself. Rejected
   (the reviewer misread) → record the row and the `path:line` that disproves it. Confirmed →
   fix it.
4. Spot-check `met` rows from every source: open the cited `path:line`, or re-run the cited
   command and compare its result line. A row whose evidence does not implement the requirement
   is treated as `unmet` and confirmed or rejected as in step 3.
5. For each `manual` row, confirm the requirement cannot be shown from the diff or a read-only
   command. If it can, treat the row as `unmet` and handle it as in step 3; otherwise it stands
   as `manual` and never triggers the Stop rule.

## 4. Fix and re-run once

Fix confirmed gaps under the PRP's surgical scope. A converge fix is new code and re-enters the
Phase B close-out path before the second pass: B4 (the §9 validation levels), B5 (commit, ruff
clean), B6 (the Snyk gate, scope rule unchanged), then a full Phase C step 1 gate reconciliation
over every task, not only the ones the fix touched. Then run this pass once more with the same
inputs at the new `HEAD`.
A confirmed gap after that second pass is a Stop condition — report it with its evidence.

## 5. Report (final report, Phase C step 7)

Counts by status; every rejected row with its disproving evidence; every `unrequested` row (a
surgical-scope note, never a stop on its own); every `manual` row with what would prove it (left
for the user, never a stop on its own).
