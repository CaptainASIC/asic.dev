# Building the feedback loop

A loop is one command that goes red on this bug and green once it is fixed. Try these in order and
stop at the first one that reaches the bug.

1. **Failing test** at whatever seam reaches the bug — unit, integration, end-to-end. Python:
   `uv run pytest tests/test_x.py::test_symptom -x -q`.
2. **HTTP script** — `curl` against a running dev server, asserting status code and body.
3. **CLI with a fixture** — run the command on a saved input and `diff` its stdout against a
   known-good snapshot.
4. **Headless browser** — a Playwright or Puppeteer script asserting on DOM, console or network.
5. **Replay a capture** — save a real request, payload or event log to disk, then replay it
   through the code path in isolation. Redact it first.
6. **Throwaway harness** — a minimal subset of the system (one service, stubbed dependencies)
   driven by a single function call. Keep it in the session scratchpad.
7. **Property or fuzz loop** — for "sometimes wrong output", run many random inputs and catch the
   failing one. Use Hypothesis only when the project already depends on it.
8. **Bisection harness** — the bug appeared between two known states (commit, dataset, version):
   script "check state X" so `git bisect run` can drive it (`root-cause-tracing.md`).
9. **Differential loop** — the same input through the old and new version (or two configs), with
   the outputs diffed.
10. **Human in the loop** — last resort, when a person must click. Keep the user's part to the
    action itself, then have them run a non-interactive capture command (a log tail, a state
    query) as `! <command>` at the prompt: shell mode adds the command and its output to the
    conversation. Never script interactive prompts — the Bash tool cannot answer them.

## Tighten it

Treat the loop as a product:

- **Faster:** cache setup, skip unrelated initialisation, narrow the test selection.
- **Sharper:** assert the specific symptom, not "no exception".
- **Deterministic:** pin the clock, seed random generators, isolate the filesystem (pytest's
  `tmp_path`), stub the network.

A 2-second deterministic loop is a debugging tool. A 30-second flaky one is barely better than
none.

## Flaky bugs

Aim for a higher reproduction rate, not a clean repro. Loop the trigger
(`for i in $(seq 100); do <loop>; done`), run it in parallel, add load, narrow timing windows. A
bug that reproduces half the time is debuggable; one that reproduces 1% of the time is not, so
keep raising the rate.

Pytest order dependence: run the failing test alone, then with its file, then with the whole
suite. Passing alone and failing in the suite means shared state — find the polluter with the
victim-driven loop for in-memory state (`root-cause-tracing.md`).
