---
name: prp-review
description: Adversarial review gate for a drafted PRP — fans out tier-sized distinct-lens reviewers (six on logic, three on style/convention drift against the real target repo, gated on citations) via a Workflow, adjudicates their findings to drop false positives, applies blocker/major fixes to the PRP in place, and re-reviews up to the tier's round cap before appending a review-log. Use when the user says "review this PRP", "harden the PRP", "adversarial review", "stress-test PRP-NNN", or invokes /prp-review — after prp-draft and before prp-implement. Sits between prp-draft and prp-implement in the pipeline.
---

# prp-review

The gate between a drafted PRP and its implementation. `prp-implement` trusts the PRP
completely — a flawed spec yields confident wrong code. This skill runs an independent
adversarial pass over a PRP before any implementation budget is spent: tier-sized reviewers each with
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

**Then size the review.** That citation note is the same read that produces `citedFileCount` — do
not add a second pass. Compute the skills directory from this `SKILL.md`'s location (it is
`<…>/skills/prp-review/SKILL.md`, so the skills dir is two levels up) and read
`<asic-tools skills dir>/prp-draft/references/sizing.md`. Never use a relative path into
`prp-draft/references/` — it resolves against the repo being reviewed, not against this plugin.
Confirm the file exists. Count tasks and files by the rubric's own rules, apply it, and emit the
`SIZING:` verdict block. The tier sets the round cap; `citedFileCount` sets the style lenses.

## Phase 1 — Run the review Workflow

Invoking this skill is the user's opt-in to multi-agent orchestration. Call the **Workflow**
tool directly — do not ask again:

**Ultracode.** Turning it on keeps that multi-agent opt-in standing across a multi-PRP session,
rather than re-establishing it per invocation. It is the user's session-level choice and
no skill invokes it — including this one.

- `name`: `asic-tools:prp-review-fanout` — the plugin workflow, invoked by name. There is no path
  to resolve. (It is also a command; the skill is the supported entry point, because invoking the
  fan-out directly skips Phase 0's PRP resolution and sizing and Phase 2's review-log append.)
- `args`: `{ "prpPath": "<resolved PRP path>", "sizing": { "tier": "S|M|L|XL", "tasks": <int>,
  "files": <int>, "citedFileCount": <int>, "rounds": <int>, "styleLenses": 0 | 3,
  "note": "<escalation reason, or empty>" },
  "topTierModel": "${user_config.top_tier_model}" }` — the verdict computed in Phase 0, plus the
  user's `top_tier_model` setting passed through verbatim (the workflow honours only `mythos`).

The script fans out <n> lenses in parallel. The six logic lenses always run
(requirements-coverage, architecture-soundness, over-build, edge-cases & verifiability,
silent-failure — including errors swallowed by proposed code — and type-design, which returns
nothing when the PRP introduces no types). The three style lenses (naming, structure,
conventions — each reading the cited
repo files) run only when `citedFileCount > 0`, since a PRP citing no repo files gives them
nothing to compare against. It adjudicates, applies blocker/major fixes to the PRP in place, and
repeats up to the tier's round cap, exiting early when a round yields no blocker/major findings.
It returns `{ reviewLog, residual }`.

## Phase 2 — Append the review-log

After the Workflow returns, append a `## Review Log` section to the PRP (do not duplicate one
if a prior run left it — replace it). Record, from `reviewLog`: per round the raw vs. valid
finding counts and what was applied; the advisory (minor/nit) findings; and the `residual`
blocker/major findings if any survived three rounds.

```markdown
## Review Log

Reviewed YYYY-MM-DD by prp-review (<n> lenses, N round(s), tier <T> — converged | stopped at cap).

- Round 1: 14 raw → 6 valid → 4 blocker/major applied.
- Round 2: 3 raw → 1 valid → 1 applied.
- Round 3: clean.

**Residual blockers:** none.  <!-- or a list when blockers survived round 3 -->
**Advisory (not applied):** <minor/nit findings, one per line>
```

(Use today's date from the environment context — do not invent one.)

`<n>` is the lens count that actually ran and `<T>` the tier, both from the Phase 0 verdict.
Write **`converged`** when the loop broke early — a round produced no findings, or none at
blocker/major — and **`stopped at cap`** when the final round was still producing blocker/major
findings when the tier's cap was reached. A capped run is an accepted cost, but a reader must be
able to tell a clean review from a truncated one without inferring it from the size of the
residual section. A residual section routinely populated at M is the evidence that M's cap
should move in `sizing.md`.

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
