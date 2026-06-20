# PRP-Loop Hardening — Prioritized Fix List

Adversarial audit of `prp-draft`, `prp-review`, `prp-implement` for context leakage, skippable
gates, spec drift, and the missing security gate. Most damaging first. Each item names the
concrete edit; ✅ = applied in this changeset.

---

## P0 — No security gate exists in the loop ✅

**Damage:** `prp-implement` commits code and closes out a PRP with zero SAST/SCA. The Snyk MCP
is registered (`~/.claude.json`, `SNYK_TOKEN` set) but **no skill ever calls it**. Vulnerable
code ships to merge unreviewed for security.

**Fix (applied):** New required step `prp-implement` Phase B step 6 — **Security gate (Snyk
MCP), fail-closed**:
- Runs once, after all §9 validation levels pass, **before** Phase C close-out. Gate only —
  never per-tool-call.
- **Adaptive scans:** `snyk_code_scan` always; `snyk_sca_scan` if a real dependency manifest+lock
  exists; `snyk_iac_scan` if IaC (terraform/k8s/cloudformation) present; `snyk_container_scan` if
  a Dockerfile/image build is present.
- **Blocks on any `high` or `critical` finding.** No close-out, no acceptance check-off until
  resolved. Fix → re-scan → must come back clean. `medium`/`low` → reported as advisory, proceed.
- **Fail-closed:** Snyk unauthenticated, MCP unavailable, or scan errors → treat as BLOCK; stop
  with a precise state report. Never proceed on an unknown security state.
- `snyk agent-scan` is explicitly **out of scope** (user runs supply-chain scanning separately).

**Files:** `plugins/asic-tools/skills/prp-implement/SKILL.md` (Phase B step 6, Phase C
acceptance + final report lines, Stop conditions).

---

## P1 — graphify MCP queries the wrong repo's graph ✅

**Damage:** `mcp__graphify-airi__*` was hardwired to `…/Airi/graphify-out/graph.json`. Any
graphify-MCP call from asic.dev (or any repo ≠ Airi) returns Airi's nodes — confident,
silent cross-repo context poisoning into a PRP.

**Fix (applied):** Drop `graphify-airi` from `~/.claude.json` `mcpServers`. All graphify
retrieval routes through the **CLI**, which reads the correct local `graphify-out/`. Routing
rule added to `docs/agent-tooling.md`: never call `mcp__graphify-airi__*`.

---

## P2 — Verified-context is unenforced; reviewers + drift fan-out scan blind ✅

**Damage:** The graphify guard hooks are **advisory only** (`additionalContext`, never `exit 2`).
`review_workflow.js` style reviewers were told to "Read the repo files" with no graphify-first
discipline; `prp-implement` A3/A2.5 Explore fan-out likewise. Unverified/blind-scanned context
can enter a PRP or a drift verdict.

**Fix (applied):**
- `review_workflow.js`: style-lens `readRepo` instruction now mandates graphify-first
  orientation before reading cited files, and every finding must cite a PRP quote **or** a
  `file:line` the reviewer actually read (adjudicator rejects uncited findings).
- `prp-implement` A3 + A2.5 fan-out prompts now carry the graphify-first rule for subagents.
- `prp-draft` Phase 2 already led with graphify; the **verified-context rule** (every claim =
  graph node / `path:line` / Ref URL, else `SPECULATIVE`) is now stated explicitly and
  cross-referenced to `docs/agent-tooling.md`.

---

## P3 — prp-review final-round verify self-grades ✅ (mitigated)

**Damage:** The round-3 verifier re-reads **only the PRP it just edited** to decide `resolved`.
A `suggested_fix` whose wording was pasted in (but is wrong vs the real repo) passes verification.
Spec drift survives the gate.

**Fix (applied):** Verify prompt now requires, for any **style-lens** finding, that the verifier
re-confirm against the **cited repo file** (not just the PRP text) before marking `resolved=true`.
Logic-lens findings still verify against PRP text. Unverifiable → residual (unchanged).

---

## P4 — DataSentry missed UUID-form secrets (e.g. SNYK_TOKEN) ✅ CLOSED in datasentry 0.3.0

**Damage (was):** DataSentry `PostToolUse:*` redaction fires on Bash output (the Ref API key came
back `[DS:generic-api-key:a47b]`), proving redaction is not bypassed on the fan-out/tool path.
**But** the `SNYK_TOKEN` (a bare UUID) passed through in **cleartext** — the generic-api-key
pattern did not match UUID-shaped tokens.

**Resolution:** DataSentry 0.3.0 adds a dedicated `snyk-token` rule; the UUID now redacts to
`[DS:snyk-token:…]` (verified: `SNYK_TOKEN=…` → `[DS:snyk-token:a564]`). Eval `d2` was flipped
from *tracking the gap* to *asserting redaction* (requires datasentry ≥ 0.3.0). DataSentry is a
separate plugin — the rule was patched in the datasentry repo, not here. Operational hygiene
unchanged: `SNYK_TOKEN` stays in the MCP `env` block, never echoed by a skill.

---

## P5 — prp-implement A2 review-log gate is advisory ⚠️ (intentional, documented)

**Observation:** A2 treats a missing/blocker-laden `## Review Log` as a warning, then proceeds on
user confirm. This is by design (review is offered, not forced). **No change** — but flagged so
it's a conscious posture: a PRP can be implemented without ever passing `prp-review`. The Snyk
gate (P0) is the hard backstop regardless of review status.

---

## Scope confirmations

- Snyk gate runs **only** at the Phase B→C boundary, never per-tool-call.
- DataSentry runtime redaction confirmed firing; coverage gap (UUID) tracked via eval.
- `snyk agent-scan` deliberately **not** wired in.
- Plain files remain source of truth; the only global-config change is dropping one dead MCP.
