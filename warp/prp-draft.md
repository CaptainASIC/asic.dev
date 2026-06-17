# prp-draft — Warp prompt

Save this as a Warp Drive prompt (or rule) named `prp-draft`. Invoke it when turning a
discussion or design summary into a PRP. Reference files live in the Claude Code plugin
marketplace clone at `~/.claude/plugins/marketplaces/asic-dev/plugins/asic-tools/skills/prp-draft/references/`
(installed via `/plugin marketplace add CaptainASIC/asic.dev`), or in your repo checkout
under `plugins/asic-tools/skills/prp-draft/references/`.

---

Draft a Product Requirements Prompt (PRP) — an implementation-ready instruction document a
coding agent executes with no other context. Follow this workflow exactly; do not skip the
gate.

PRIME DIRECTIVE: never write a claim you have not verified this session. No invented line
numbers, no guessed API signatures, no assumed paths. Every CRITICAL/GOTCHA traces to source
you read, a lockfile, or official docs (use Ref MCP).

1. INPUTS — feature ask = this conversation or the summary I give you. Target repo = cwd
   unless I name another.

2. CONTEXT SWEEP — read, tolerating absence: README.md, PLANNING.md, TASKS.md,
   CHANGELOG.md, WARP.md, CLAUDE.md; Serena memories (all relevant, plus
   .serena/memories/prp/ for prior PRP status); PRPs/ (next number = max NNN + 1, zero-padded;
   read the 1–2 newest PRPs for local conventions); tooling from pyproject.toml / lockfiles —
   pin real dependency versions.

3. CODEBASE RESEARCH — read every file the feature touches. Record exact paths, symbols,
   line numbers actually seen, surprises (type drift, sync/async boundaries, size-cap
   violations). Verify library behavior against the installed version via Ref.

4. REFUSAL GATE — do not draft unless: goal is concrete; you read the code at every claimed
   integration point; validation commands are known-runnable in this repo; no blocking
   unknown remains. Otherwise stop and reply "Cannot draft PRP yet. Missing:" with a numbered
   list of gaps and what would resolve each.

5. INTERVIEW — open design decisions become batched questions (≤4 per round) with your
   recommendation first. Answers land in §3 as design-decision subsections.

6. DRAFT — read prp_template.md and style_guide.md from
   ~/.claude/plugins/marketplaces/asic-dev/plugins/asic-tools/skills/prp-draft/references/
   (or the repo checkout's plugins/asic-tools/skills/prp-draft/references/), then write
   PRPs/PRP-NNN_TITLE_IN_SNAKE_CAPS.md (mkdir PRPs/ if missing — the only file you write).
   Canonical §1–§12 skeleton; depth scales with scope; outline first, then fill
   section-by-section. Branch in front matter: feature/prp-NNN-short-slug.

7. SELF-AUDIT — before reporting: every referenced path exists (re-check); every line number
   was read; every command copy-pasteable with detected tooling (uv run …); dependency PRPs
   marked hard/soft; strict non-goals and anti-patterns present; §10 has paste-ready
   PLANNING/TASKS/serena snippets plus "Discovered During Work" instruction; git constraints
   embedded (feature branch, ruff-clean before commit, no AI attribution, never push); no
   unannounced SPECULATIVE markers. Report path, size, open questions.
