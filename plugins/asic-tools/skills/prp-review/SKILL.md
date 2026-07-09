---
name: prp-review
description: Adversarial review gate for a drafted PRP — fans out eight distinct-lens reviewers (five on logic, three on style/convention drift against the real target repo) via a Workflow, adjudicates their findings to drop false positives, applies blocker/major fixes to the PRP in place, and re-reviews up to three rounds before appending a review-log. Use when the user says "review this PRP", "harden the PRP", "adversarial review", "stress-test PRP-NNN", or invokes /prp-review — after prp-draft and before prp-implement. Sits between prp-draft and prp-implement in the pipeline.
---

# prp-review

The gate between a drafted PRP and its implementation. `prp-implement` trusts the PRP
completely — a flawed spec yields confident wrong code. This skill runs an independent
adversarial pass over a PRP before any implementation budget is spent: eight reviewers each with
a distinct lens, an adjudicator that filters false positives, and a bounded fix-and-re-review
loop. It edits the PRP in place and appends a review-log. It writes no code and runs nothing
the PRP describes.

**Prime directive: harden the spec, do not rewrite it.** Apply only validated blocker/major
findings. Minor/nit findings are advisory — recorded, not auto-applied. Residual blockers are
surfaced to the human, never silently dropped.

## Phase 0 — Resolve the PRP

The target PRP comes from the argument (a number like `PRP-007` or a path) or the conversation.
Otherwise pick the newest `Status: Ready for execution` PRP in `PRPs/` — confirm when ambiguous.
Read the PRP fully. If it does not exist or is not a PRP, stop and say so. Note the repo files
it cites in §4.1/§4.2 — those are the style reviewers' ground truth.

## Phase 1 — Run the review Workflow

Invoking this skill is the user's opt-in to multi-agent orchestration. Call the **Workflow**
tool directly — do not ask again:

- `scriptPath`: the bundled `references/review_workflow.js` (this skill's directory).
- `args`: `{ "prpPath": "<resolved PRP path>" }`.

The script fans out eight reviewers in parallel (5 logic: requirements-coverage,
architecture-soundness, over-build, edge-cases & verifiability, silent-failure; 3 style: naming, structure,
conventions —
each reading the cited repo files), adjudicates, applies blocker/major fixes to the PRP in
place, and repeats up to three rounds, exiting early when a round yields no blocker/major
findings. It returns `{ reviewLog, residual }`.

## Phase 2 — Append the review-log

After the Workflow returns, append a `## Review Log` section to the PRP (do not duplicate one
if a prior run left it — replace it). Record, from `reviewLog`: per round the raw vs. valid
finding counts and what was applied; the advisory (minor/nit) findings; and the `residual`
blocker/major findings if any survived three rounds.

```markdown
## Review Log

Reviewed YYYY-MM-DD by prp-review (8 lenses, N round(s)).

- Round 1: 14 raw → 6 valid → 4 blocker/major applied.
- Round 2: 3 raw → 1 valid → 1 applied.
- Round 3: clean.

**Residual blockers:** none.  <!-- or a list when blockers survived round 3 -->
**Advisory (not applied):** <minor/nit findings, one per line>
```

(Use today's date from the environment context — do not invent one.)

## Phase 3 — Report & hand off

Report: rounds run, net findings applied, residual blockers (if any). If residual blockers
remain, recommend a fix-and-rerun before implementing. Otherwise offer the next step:
*"Implement this PRP? (`/asic-tools:prp-implement <PRP-NNN>`)"* — offered, not auto-run.

## Anti-patterns

- Don't invoke `/goal` — it is a single-session loop, not a fan-out orchestrator.
- Don't apply minor/nit or unvalidated findings — only adjudicated blocker/major.
- Don't run more than three rounds or loop "until everyone agrees" — report residuals instead.
- Don't rewrite the PRP wholesale or touch any file other than the PRP under review.
- Don't re-run prp-draft's codebase research — style reviewers read only the cited files.
- Don't drop residual blockers silently — they go in the review-log and the report.

## Verification

- [ ] The named PRP was resolved and read before reviewing.
- [ ] The Workflow ran with `args.prpPath` set to the resolved path.
- [ ] Only validated blocker/major findings were applied to the PRP.
- [ ] A `## Review Log` section records rounds, applied fixes, advisory, and residuals.
- [ ] Residual blockers (if any) are reported with a fix-and-rerun recommendation.
- [ ] `prp-implement` hand-off offered, not forced.
