# Run state — `PRPs/.work/prp-implement-active.md`

One small file per active `prp-implement` run, at every tier. It holds the two things that must
survive context compaction: the fork point the converge pass diffs against (Phase C step 1b), and
a factual summary the plugin's `SessionStart` (matcher `compact`) hook in `hooks/hooks.json`
prints back into context.

## Lifecycle

| When | Action |
|---|---|
| Phase B step 1, fresh run | Confirm `git branch --show-current` is the base you mean to fork from (main/develop, or the parent feature branch of a stacked PRP), record `git rev-parse HEAD`, create the branch, then write the file. |
| Phase B step 1, the file names a different PRP | Stop and ask — it is another run's resumable state. |
| After each task's commit | Update the `Current task:` line only. |
| Resume (A2.5), file names this PRP | Read `Base commit:`; update `Current task:`; never re-record the base. |
| Resume (A2.5), no file (a pre-v3 branch, or the file was lost) | The branch is unmerged, so its merge-base with the base branch A2.5 named is still the fork point. Record `git merge-base HEAD <base>` once, now, as `Base commit:` followed by `(reconstructed on resume)`, write the file, and name the reconstruction in the final report. Never recompute it later. |
| Successful Phase C close-out (step 6) | Delete it. |
| A documented STOP | Keep it. Name it in the stop-state report. |

It is never staged or committed: `PRPs/.work/` is outside every PRP's summary table, the same
rule that keeps the scratchpad out of commits.

## Format

Fixed labels, one per line, factual statements only. The hook injects this text verbatim, and
text framed as system commands can trip prompt-injection defenses, so describe state; do not
issue orders. Keep it under 1,000 characters.

    prp-implement run state (written by the prp-implement skill; re-injected after context compaction).
    - PRP: PRPs/PRP-NNN_TITLE.md
    - Branch: feature/prp-NNN-slug
    - Base commit: <full SHA recorded before branching>
    - Tier: <S|M|L|XL>
    - Scratchpad: <PRPs/.work/PRP-NNN-scratchpad.md | none>
    - Current task: Task <k> of <n> (Tasks 1-<k-1> committed)
    - Skill file: <absolute path given in SKILL.md Phase B step 1>
    - After compaction only the first 5,000 tokens of an invoked skill are re-attached. This
      skill's Phase C close-out and Stop conditions sit past that point, in the skill file above.
    - Read from that file, `${CLAUDE_SKILL_DIR}` stands for the directory that holds it.

`Skill file:` must be an absolute path. This reference file cannot supply it: `${CLAUDE_SKILL_DIR}`
is substituted only inside `SKILL.md`, so copy the resolved path given there.
