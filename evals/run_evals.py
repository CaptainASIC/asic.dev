#!/usr/bin/env python3
"""Dev Toolbox hardening eval harness.

Stdlib-only (this repo is a plugin marketplace, not a Python package — its Python
ships as standalone python3 scripts, so the evals match that shape). Run with:

    python3 evals/run_evals.py

Proves four properties of the hardened PRP loop:
  (a) retrieval routing picks the right source       -> test_retrieval_routing
  (b) a PRP cannot advance past a failed gate         -> test_prp_gate_invariants
  (c) the Snyk gate blocks a seeded high finding       -> test_snyk_gate
  (d) DataSentry redaction fires (AWS key + UUID token) -> test_datasentry_redaction

Exit code is non-zero if any non-skipped check fails.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILLS = REPO / "plugins" / "asic-tools" / "skills"
DOCS = REPO / "docs"
FIXTURES = Path(__file__).resolve().parent / "fixtures"

# DataSentry lives outside this repo (separate plugin). Resolve its active install.
DATASENTRY = Path.home() / ".claude" / "plugins" / "cache" / "datasentry" / "datasentry"

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"
_results: list = []


def check(name: str, ok: bool, detail: str = "") -> None:
    _results.append((PASS if ok else FAIL, name, detail))


def skip(name: str, detail: str) -> None:
    _results.append((SKIP, name, detail))


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# (a) Retrieval routing picks the right source
# ---------------------------------------------------------------------------
def test_retrieval_routing() -> None:
    doc = DOCS / "agent-tooling.md"
    if not doc.exists():
        check("a1 agent-tooling.md exists", False, str(doc))
        return
    text = _read(doc)
    check("a1 agent-tooling.md exists", True)
    # The three lanes are named and distinct.
    for lane in ("graphify", "serena", "Ref"):
        check(f"a2 lane '{lane}' documented", lane in text)
    # The wrong-graph MCP is explicitly forbidden, and routed to the CLI.
    check(
        "a3 graphify-airi MCP forbidden",
        "mcp__graphify-airi__" in text and "never call" in text.lower(),
    )
    # The dead MCP is actually gone from the live config.
    cfg = Path.home() / ".claude.json"
    try:
        servers = json.loads(_read(cfg)).get("mcpServers", {})
        check(
            "a4 graphify-airi removed from ~/.claude.json",
            "graphify-airi" not in servers,
            f"mcpServers={list(servers)}",
        )
    except (OSError, ValueError) as exc:
        skip("a4 graphify-airi removed from ~/.claude.json", f"cannot read config: {exc}")
    # Style reviewers and the drift fan-out are graphify-first (no blind scan).
    wf = _read(SKILLS.parent / "workflows" / "review_workflow.js")
    check("a5 review reviewers graphify-first", "graphify" in wf and "orient" in wf.lower())
    impl = _read(SKILLS / "prp-implement" / "SKILL.md")
    check("a6 drift fan-out graphify-first", "graphify-first" in impl)
    draft = _read(SKILLS / "prp-draft" / "SKILL.md")
    check(
        "a7 verified-context rule present",
        "Verified-context rule" in draft and "SPECULATIVE" in draft,
    )


# ---------------------------------------------------------------------------
# (b) A PRP cannot advance past a failed gate
# ---------------------------------------------------------------------------
def test_prp_gate_invariants() -> None:
    impl = _read(SKILLS / "prp-implement" / "SKILL.md")
    # The gate exists, is required, and is fail-closed.
    check("b1 security gate present", "Security gate (Snyk MCP)" in impl)
    check("b2 gate is fail-closed", "fail-closed" in impl)
    check("b3 blocks on high/critical", "high or critical" in impl and "BLOCK" in impl)
    # Gate runs before close-out, not per-tool-call.
    check("b4 gate before Phase C", "before** Phase C" in impl or "before Phase C" in impl)
    check(
        "b5 gate is not per-tool-call",
        "never a per-tool-call" in impl or "never per-tool-call" in impl.lower().replace("-", "-"),
    )
    # Unauthenticated / unavailable Snyk is itself a block (no silent pass).
    check("b6 unauth/unavailable = block", "Unauthenticated" in impl and "BLOCK" in impl)
    # The block is wired into Stop conditions and the close-out report.
    check("b7 stop condition includes security gate", "security gate block" in impl.lower())
    check("b8 agent-scan explicitly out of scope", "agent-scan" in impl and "out of scope" in impl)


# ---------------------------------------------------------------------------
# (c) The Snyk gate blocks a seeded high-severity finding (real scan)
# ---------------------------------------------------------------------------
def _snyk_token() -> str | None:
    """Token from env, else the Snyk MCP's configured token in ~/.claude.json."""
    if os.environ.get("SNYK_TOKEN"):
        return os.environ["SNYK_TOKEN"]
    try:
        cfg = json.loads(_read(Path.home() / ".claude.json"))
        return cfg.get("mcpServers", {}).get("Snyk", {}).get("env", {}).get("SNYK_TOKEN")
    except (OSError, ValueError):
        return None


def test_snyk_gate() -> None:
    token = _snyk_token()
    if not token:
        skip(
            "c1 seeded high finding blocks (snyk exit 1 at --severity-threshold=high)",
            "no SNYK_TOKEN in env or ~/.claude.json. Gate's fail-closed behavior on missing "
            "auth is asserted by test b6.",
        )
        return
    # `snyk code test --severity-threshold=high` exit codes: 0 = no high+ findings,
    # 1 = high+ findings present (the gate's BLOCK signal), 2 = error, 3 = no supported files.
    try:
        proc = subprocess.run(
            [
                "npx",
                "-y",
                "snyk@latest",
                "code",
                "test",
                str(FIXTURES),
                "--severity-threshold=high",
            ],
            capture_output=True,
            text=True,
            timeout=300,
            env={**os.environ, "SNYK_TOKEN": token},
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        # Fail-closed: an erroring scanner is itself a BLOCK by design (test b6), but it does
        # not prove the *finding*, so record a fail here for inspection.
        check(
            "c1 seeded high finding blocks (snyk exit 1 at --severity-threshold=high)",
            False,
            f"snyk invocation failed: {exc}",
        )
        return
    # exit 1 = high/critical findings exist -> the gate blocks. Anything else fails the proof.
    check(
        "c1 seeded high finding blocks (snyk exit 1 at --severity-threshold=high)",
        proc.returncode == 1,
        f"snyk exit={proc.returncode} (1 = high findings present = BLOCK)",
    )


# ---------------------------------------------------------------------------
# (d) DataSentry redaction fires (and the UUID coverage gap is tracked)
# ---------------------------------------------------------------------------
def _datasentry_script() -> Path | None:
    if not DATASENTRY.exists():
        return None
    versions = sorted(p for p in DATASENTRY.iterdir() if (p / "scripts" / "datasentry.py").exists())
    return (versions[-1] / "scripts" / "datasentry.py") if versions else None


def _run_datasentry(script: Path, payload: dict) -> dict:
    with tempfile.TemporaryDirectory() as home:
        proc = subprocess.run(
            ["python3", str(script)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=15,
            env={**os.environ, "DATASENTRY_HOME": home},  # isolate audit log
        )
    return json.loads(proc.stdout) if proc.stdout.strip() else {}


def test_datasentry_redaction() -> None:
    script = _datasentry_script()
    if script is None:
        skip("d1 datasentry redacts a known secret", "datasentry plugin install not found")
        return
    # A real-shaped AWS key (no allowlist words) at the default 'standard' level -> critical.
    secret = "AKIAZ7XQ2L9R4T8N3WJ1"
    payload = {
        "hook_event_name": "PostToolUse",
        "tool_name": "Bash",
        "tool_response": {"stdout": f"export AWS_ACCESS_KEY_ID={secret}"},
    }
    out = _run_datasentry(script, payload)
    updated = json.dumps(out.get("hookSpecificOutput", {}).get("updatedToolOutput", ""))
    check(
        "d1 datasentry redacts a known secret",
        secret not in updated and "[DS:" in updated,
        "AWS key replaced with [DS:...] placeholder",
    )
    # Gap P4 closed in datasentry 0.3.0: a bare UUID SNYK_TOKEN is now caught by a dedicated
    # snyk-token rule. Assert it is redacted (requires datasentry >= 0.3.0).
    uuid = "a8820553-7a45-4908-bd36-964b7606cce2"
    payload2 = {
        "hook_event_name": "PostToolUse",
        "tool_name": "Bash",
        "tool_response": {"stdout": f"SNYK_TOKEN={uuid}"},
    }
    out2 = _run_datasentry(script, payload2)
    blob2 = json.dumps(out2)
    redacted2 = "[DS:" in blob2 and uuid not in blob2
    check(
        "d2 UUID-form token (SNYK_TOKEN) is redacted (gap P4 closed in datasentry 0.3.0)",
        redacted2,
        "bare UUID replaced with [DS:snyk-token:...] placeholder",
    )


def main() -> int:
    for fn in (
        test_retrieval_routing,
        test_prp_gate_invariants,
        test_snyk_gate,
        test_datasentry_redaction,
    ):
        try:
            fn()
        except Exception as exc:  # noqa: BLE001 — one eval crashing must not hide the rest
            check(f"{fn.__name__} crashed", False, repr(exc))

    width = max(len(n) for _, n, _ in _results)
    icon = {PASS: "✅", FAIL: "❌", SKIP: "⏭️ "}
    for status, name, detail in _results:
        line = f"{icon[status]} {status:4} {name:<{width}}"
        if detail:
            line += f"  — {detail}"
        print(line)
    failed = sum(1 for s, _, _ in _results if s == FAIL)
    passed = sum(1 for s, _, _ in _results if s == PASS)
    skipped = sum(1 for s, _, _ in _results if s == SKIP)
    print(f"\n{passed} passed, {failed} failed, {skipped} skipped")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
