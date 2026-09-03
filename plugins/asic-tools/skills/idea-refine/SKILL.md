---
name: idea-refine
description: Refine a raw idea into a sharp, build-ready concept before any PRP or code — structured divergent/convergent thinking that ends in a one-pager (problem, recommended direction, assumptions, MVP scope, explicit non-goals). Use when the user says "refine this idea", "ideate", "stress-test my plan", "help me think through X", or invokes /idea-refine — typically when an idea is still vague, or upstream of prp-draft when the feature ask isn't yet concrete. Sits before prp-draft in the pipeline; hands off to it. Pushes back on weak ideas — not a yes-machine.
---

# idea-refine

The cheap filter before the expensive research. `prp-draft` does a heavy codebase sweep and
verification pass — you do not want that budget spent on the wrong idea. This skill is the
upstream step: diverge, converge, and produce a one-pager that becomes a clean `prp-draft`
input. It writes one artifact and no code.

**Prime directive: surface assumptions before committing to a direction.** Untested
assumptions kill more ideas than bad execution. Name them, do not bury them.

**Not a yes-machine.** A weak idea gets pushed back on — with specificity and kindness, not
flattery. KISS and YAGNI govern: steer toward the simplest version that solves the real
problem, and say no to good-but-distracting ideas out loud.

## Phase 0 — Inputs

The idea comes from the argument, the conversation, or a pasted note. If invoked with no
discernible idea, ask for one — do not run the engine on nothing. If running inside a repo,
the existing architecture is both constraint and opportunity: use `Glob`/`Grep`/`Read` to
ground every variation in what actually exists, and cite real paths when relevant.

## Phase 1 — Understand & Expand (divergent)

1. **Restate** the idea as one crisp "How Might We…" problem statement. This forces clarity
   on what is actually being solved before anything else.
2. **Sharpen** with 3–5 questions, no more (`AskUserQuestion` in Claude Code). Do not proceed
   until *who it is for* and *what success looks like* are answered. Cover: who specifically,
   what success looks like, real constraints (time/tech/resources), what's been tried, why now.
3. **Generate 5–8 variations** — quality over quantity. Pick the lenses that fit; do not run
   all mechanically:
   - **Inversion** — what if we did the opposite?
   - **Simplification** — the version that's 10× simpler?
   - **10×** — what would this look like at massive scale?
   - **Constraint removal** — if budget/time/tech weren't factors?
   - **Audience shift** — what if this were for a different user?
   - **Combination** — merged with an adjacent idea?
   - **Expert lens** — what would a domain expert find obvious that outsiders miss?

   Each variation carries a reason it exists. Push one step past what was asked.

## Phase 2 — Evaluate & Converge

After the user reacts to Phase 1 (what resonates, what they push back on):

1. **Cluster** what resonated into 2–3 *meaningfully distinct* directions — not variations on
   one theme.
2. **Stress-test** each direction on three axes:
   - **User value** — who benefits, how much. Painkiller or vitamin?
   - **Feasibility** — technical and resource cost. What's the hardest part?
   - **Differentiation** — what makes it genuinely different? Would anyone switch?
3. **Surface hidden assumptions** per direction — explicitly:
   - what you're betting is true but haven't validated
   - what could kill it
   - what you're choosing to ignore (and why that's acceptable for now)

   This is where ideation usually fails. Do not skip it. Be honest, not supportive — if the
   emperor has no clothes, say so.

## Phase 3 — Sharpen & Ship

Produce the one-pager. Confirm the direction with the user, then write it to
`PRPs/ideas/<idea-slug>.md` (create `PRPs/ideas/` if absent — the only file this skill
writes). Co-located with `PRPs/` so the idea → PRP chain lives in one tree.

```markdown
# <Idea Name>

**Predicted tier:** <S|M|L|XL> — <n> tasks, <n> files (prediction on the two primary axes of
`sizing.md`; `prp-draft` re-counts for real and reports disagreement)

## Problem Statement
<one-sentence "How Might We" framing>

## Recommended Direction
<the chosen direction and why — 2-3 paragraphs max>

## Key Assumptions to Validate
- [ ] <assumption — how to test it>

## MVP Scope
<minimum version that tests the core assumption. What's in, what's out.>

## Not Doing (and Why)
- <thing> — <reason>

## Open Questions
<what must be answered before building>
```

The **Not Doing** list is the most valuable section — focus is saying no to good ideas. Make
the trade-offs explicit.

Resolve the rubric to an absolute path before reading it: compute the skills directory from this
`SKILL.md`'s location (it is `<…>/skills/idea-refine/SKILL.md`, so the skills dir is two levels
up) and read `<asic-tools skills dir>/prp-draft/references/sizing.md`. Never use a relative path
into `prp-draft/references/` — it resolves against the repo being worked on, not against this
plugin. Read only its axes, boundaries and silent-failure modifier; the tier → knob table is not
this skill's business. The prediction is a hint, not a commitment, and a prediction that is
routinely wrong is evidence the rubric's boundaries need re-calibrating.

## Phase 4 — Hand off to prp-draft

The one-pager is built to feed `prp-draft` Phase 0. Offer it: *"Draft a PRP from this?
(`/asic-tools:prp-draft`)"* — do not auto-invoke. When the user accepts, the fields map
straight onto the canonical PRP template:

| one-pager field | PRP destination |
|---|---|
| Problem Statement | §2 Problem Statement (§2.3 Desired Behaviour) |
| Recommended Direction | §1 Objective & Scope, §3 Architecture decisions |
| MVP Scope | §1 scope boundary (what's in) |
| **Not Doing (and Why)** | §1 **Strict non-goals**, §11 anti-patterns |
| Key Assumptions to Validate | §4.4 GOTCHA candidates / `SPECULATIVE — verify` markers |
| Open Questions | `prp-draft` Phase 4 interview inputs |

`idea-refine` settles *what to build and why*; `prp-draft` then does the verified-context
research `idea-refine` deliberately skips. Keep the seam clean — do not start codebase
research here.

## Anti-patterns

- Don't generate 20+ shallow variations — 5–8 considered ones beat them.
- Don't skip "who is this for" or jump straight to Phase 3 output.
- Don't produce a direction without a Not-Doing list and surfaced assumptions.
- Don't yes-machine a weak idea — push back with specificity.
- Don't over-engineer the process or ignore existing codebase constraints.
- Don't bleed into `prp-draft`'s job: no codebase research, no PRP drafting here.

## Verification

Before reporting done:

- [ ] A clear "How Might We" problem statement exists
- [ ] Target user and success criteria are defined
- [ ] Multiple directions explored, not just the first idea
- [ ] Hidden assumptions listed with validation strategies
- [ ] A Not-Doing list makes trade-offs explicit
- [ ] Output is a concrete one-pager at `PRPs/ideas/<slug>.md`, user confirmed before save
- [ ] prp-draft hand-off offered, not forced
