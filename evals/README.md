# evals/ — Dev Toolbox hardening harness

Stdlib-only eval harness for the PRP loop's static invariants. Its Python matches the plugin's own
shape — standalone `python3` scripts, no imports beyond the standard library. Run it through the
repo's locked toolchain (`uv sync` once):

```bash
uv run python evals/run_evals.py              # all groups; (c) uploads the fixture to Snyk if a token is found
uv run python evals/run_evals.py --skip-snyk  # local gates and CI: (c) recorded as skipped
```

Skill-triggering behaviour is measured separately by the `claude plugin eval` suite in
`plugins/asic-tools/evals/` (see the repo README, Development).

Exit 0 = all non-skipped checks pass; non-zero = a failure to inspect.

## What each group proves

| Group | Proves | How |
|---|---|---|
| **a** retrieval routing | The agent pulls the right source | Asserts `docs/agent-tooling.md` names the three lanes, forbids `mcp__graphify-airi__*`, that the dead MCP is gone from `~/.claude.json`, that reviewers + drift fan-out are graphify-first, and that the verified-context rule is in `prp-draft`. |
| **b** gate can't be skipped | A PRP cannot advance past a failed gate | Asserts `prp-implement` contains the required, fail-closed Snyk gate that blocks on high/critical before Phase C, is not per-tool-call, treats unauth/unavailable as a block, and is wired into Stop conditions. |
| **c** Snyk gate blocks | The gate blocks a seeded high finding | Runs the **real** `snyk code test --severity-threshold=high` on `fixtures/vulnerable_app.py`; asserts exit code 1 (high findings present = BLOCK). Token read from env or the Snyk MCP config in `~/.claude.json`. Skips (not fails) if no token is available — that path is covered by test b6. |
| **d** DataSentry redaction | Runtime secret redaction fires for both a key and a UUID token | Pipes a `PostToolUse` payload with a real-shaped AWS key through the installed `datasentry.py` (isolated `DATASENTRY_HOME`); asserts it is replaced with a `[DS:…]` placeholder. Also asserts a bare UUID (the `SNYK_TOKEN` shape) is redacted to `[DS:snyk-token:…]` — the **P4 gap, closed in datasentry 0.3.0**. |

## fixtures/vulnerable_app.py

Intentionally insecure. Untrusted **HTTP request** input flows into eval / `os.system` / SQL
sinks — Snyk Code rates these **HIGH** because the taint source is network input. (The same
sinks fed from `sys.argv` rate only MEDIUM — severity is source-dependent, which is why the
fixture uses Flask request input.) Do not fix, import, or run it.

## Notes

- The live Snyk scan emits a non-fatal `403 Forbidden (SNYK-CLI-0000)` org-association warning;
  findings still return and the threshold exit code is still authoritative.
- A stale Snyk MCP session (token rotated mid-session) will report "not authenticated" until the
  Claude session/MCP restarts — the CLI path the eval uses reads the fresh token directly and is
  unaffected.
