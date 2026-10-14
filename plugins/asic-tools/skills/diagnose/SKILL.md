---
name: diagnose
description: Loop-first debugging for application code — build a red-capable reproduction, minimise it, rank falsifiable hypotheses, then fix at the root cause behind a failing regression test. Use when the user says "debug this", "diagnose", "why is X failing/throwing/slow", "flaky test", "this broke after …", or invokes /diagnose. Not for Claude Code's own hooks, settings or MCP servers — the built-in /debug covers those.
---

# diagnose

Debugging discipline for code in the current repo. Its value is order: a tight pass/fail loop
first, a root cause second, a fix last. Guessing at fixes before the loop exists is the failure
this skill prevents.

Adapted (MIT) from obra/superpowers `systematic-debugging` and mattpocock/skills
`diagnosing-bugs` — see `NOTICE.md`. Technique detail lives in `references/`; read each file
when the phase that names it arrives.

## The iron law

No fix without a red loop and a named root cause. Until Phase 1 has produced a command that goes
red on this bug, do not propose a fix and do not read code to build a theory.

## Scope — route first

- **Claude Code itself** misbehaving (hooks, settings, MCP servers, permissions): stop and point
  the user at the built-in `/debug`, which turns on session debug logging. This skill debugs the
  user's code, not the harness.
- **The fix turns out to be PRP-sized:** Phase 6 hands off.
- Anything else broken, throwing, failing, flaky or slow: proceed.

## Redact

Commands, outputs and captured artifacts get shown back to the user. Redact every secret first:
write `<REDACTED>` in its place. Build loops against environment variables so a credential stays
in the environment, never in the command text. When quoting a log or an HTTP capture, quote only
the lines that carry the signal — auth headers ride along otherwise.

When DataSentry is installed it rewrites secrets in tool output to `[DS:<rule>:<hash>]`
placeholders. Preserve them verbatim; never try to recover the value. DataSentry sees tool output
only — text the user pastes and text you write are yours to redact.

If the redacted output is not enough to diagnose, say so and ask.

## Phase 1 — Build a red-capable loop

This phase is the skill. Spend disproportionate effort here. Read
`references/loop-construction.md` now: it orders the ways to build a loop (failing test first,
human-in-the-loop last) and covers tightening and flaky bugs.

Done when you can name **one command** you have already run — show it and its redacted output —
that is:

- [ ] **Red-capable** — drives the real code path and asserts the user's exact symptom, not
      "didn't crash"
- [ ] **Deterministic** — same verdict every run (flaky bug: a pinned, high reproduction rate)
- [ ] **Fast** — seconds, not minutes
- [ ] **Agent-runnable** — runs unattended; a human step only via a `! <command>` the user runs

Cannot build one: stop, list what you tried, and ask the user for access to the failing
environment, a redacted artifact (log, trace, HAR), or permission to add temporary
instrumentation. Do not move to hypotheses without a loop.

Throwaway harnesses live in the session scratchpad, never in the repo — the global rules keep
one-off scripts out of the tree.

## Phase 2 — Reproduce and minimise

Run the loop and watch it go red. Confirm it is the failure the **user** described, not a nearby
one — wrong bug, wrong fix. Capture the exact symptom.

Then cut inputs, callers, config and steps one at a time, re-running after each cut, until every
remaining element is load-bearing: removing any one turns the loop green. The minimised repro
becomes the regression test in Phase 6.

## Phase 3 — Investigate

1. Read the error completely — the full traceback, every line number and error code.
2. Orient before reading: when `graphify-out/graph.json` exists, run
   `graphify query "<failing area>"` (or `explain` / `path`) first, then read what it points to.
3. Check what changed: `git log` and `git diff` against the last known-good state. A good/bad
   commit pair plus the Phase 1 loop is a `git bisect run` — see
   `references/root-cause-tracing.md`.
4. Trace backward from the symptom to where the bad value originates
   (`references/root-cause-tracing.md`). Fix at the source, not where it surfaced.
5. Find working code that does the same job and list every difference, however small.

## Phase 4 — Hypothesise

Write 3–5 ranked hypotheses before testing any. Each states its prediction:

> If <X> is the cause, then <changing Y> makes the bug disappear / <changing Z> makes it worse.

No prediction, no hypothesis — sharpen it or discard it. Show the ranked list to the user; they
often re-rank it instantly. Do not block on an answer.

## Phase 5 — Instrument

Each probe tests one prediction. Change one variable at a time. Prefer a debugger or REPL;
otherwise targeted logs at the boundary that separates two hypotheses — never "log everything and
grep".

Tag every temporary probe line — imports included — with one unique prefix, e.g. `[DEBUG-a4f2]`,
so Phase 7 removes them with one grep.

Performance regressions: measure a baseline first (timing harness, profiler — the Python rules
say profile before optimising), then bisect. Logs are usually the wrong tool.

## Phase 6 — Fix

1. **Size check.** Count the root-cause fix against
   `${CLAUDE_SKILL_DIR}/../prp-draft/references/sizing.md`. Above S, or a design decision the
   user must make: stop and offer *"Draft a PRP for this fix? (`/asic-tools:prp-draft`)"*,
   carrying the loop, the minimised repro and the confirmed hypothesis. Do not auto-invoke.
2. **Regression test first**, at a seam that exercises the real bug pattern. Watch it fail. No
   correct seam exists: say so — that is a finding about the architecture, not a licence to test
   a shallower seam.
3. One fix, at the root cause. No bundled refactors, no "while I'm here".
4. Watch the test pass, re-run the original un-minimised Phase 1 loop, then the full suite. For
   a flaky bug, re-run the loop the same N times as the Phase 1 baseline and require zero
   failures: one green run proves nothing at a 50% repro rate.
5. **Three strikes.** A third failed fix means the design is wrong, not the hypothesis. Stop and
   discuss the architecture with the user before a fourth attempt.

Once the fix holds, `references/hardening.md` covers validating at each layer the bad value
crossed and replacing sleeps with condition-based waits.

## Phase 7 — Clean up and report

- [ ] The original repro no longer reproduces (re-run the Phase 1 loop; paste the output). Flaky
      bug: N runs at the baseline N, zero failures
- [ ] The regression test passes, or the missing seam is documented
- [ ] A grep for your debug prefix returns nothing
- [ ] `git diff` shows only the fix and the regression test — no untagged probe residue
- [ ] Scratchpad harnesses stayed out of the repo
- [ ] Report: root cause, the hypothesis that held, and the evidence (command + redacted output)

Commit only when the user asks: Conventional Commits, the confirmed hypothesis in the body, no AI
attribution. Never push.

## Red flags — return to Phase 1

"Quick fix now, investigate later" · "let me just try X" · several changes in one run · "skip the
test, I'll check by hand" · "it's probably X" · a fix proposed before the loop exists · each fix
surfacing a new problem somewhere else.
