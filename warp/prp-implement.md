# prp-implement — Warp prompt

Save as a Warp Drive prompt named `prp-implement`. Two-phase: invoking it reviews + plans
and then PAUSES; saying "go" / "execute the plan" runs Phase B.

---

Implement the PRP I name (or the newest "Status: Ready for execution" in PRPs/ — confirm
if ambiguous). The PRP is a contract; never drift from it silently.

PHASE A — REVIEW & PLAN (no file touched; ends with a pause):
1. Read the PRP fully, then actually read every §4.1 MUST READ file.
2. Preconditions: Status is Ready for execution (Implemented → ask before re-running);
   front-matter dependency PRPs are implemented (check .serena/memories/prp/ + the
   artifacts they name); §7/§9 commands runnable in this repo.
3. DRIFT CHECK: PRP was written as of its Date — verify every file in the §1 table and
   §4.2 tree exists; spot-check §4.4 gotchas and §6 before/after snippets against current
   code; compare §4.1 dependency versions vs lockfile. Material drift → STOP, report each
   mismatch, propose the PRP amendment, wait for my decision.
4. Present the plan: §5 tasks with current-state notes, test-first ordering where §7
   defines tests, §9 validation checkpoints, branch name. Flag any deviation as a
   question. Then WAIT for my go.

PHASE B — EXECUTE (on my approval):
1. Branch feature/prp-NNN-slug per front matter — never main.
2. Task loop in §5 order: failing test first (when §7 defines it) → implement per §6,
   re-reading the relevant §4.4 CRITICALs right before touching each file → run the
   task's VERIFY before moving on. Only files in the PRP's summary table; a needed but
   unlisted change → stop and ask; noticed-but-unneeded work → log for "Discovered During
   Work", don't do it.
3. §9 levels in order (syntax → unit → integration → e2e), green before advancing, never
   mock-to-pass, never skip. Unrecoverable failure → stop with exact state.
4. Commits per logical group: Conventional format, ruff clean BEFORE each commit, no AI
   attribution of any kind, never push.

PHASE C — CLOSE-OUT (mandatory):
1. Verify every §9 acceptance checkbox against reality; tick them in the PRP file.
2. PRP front matter → Status: Implemented (date); add Branch if absent.
3. Apply §10 verbatim: PLANNING.md, TASKS.md (dated completion + Discovered During Work
   items), CHANGELOG if mandated, Serena memory prp/NNN_name.
4. Report: checklist status, files touched vs PRP table (differences explained), one line
   per validation level, commits, and what's left for me (push + merge via GitKraken).
