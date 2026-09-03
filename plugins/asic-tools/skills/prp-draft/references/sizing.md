# Work-Sizing Rubric

## 1. Purpose

One shared definition of "how big is this work", read by `prp-draft`, `prp-implement` and
`prp-review`, and predicted against by `idea-refine`. It yields a **depth verdict only** — how many
agents fan out, how many review rounds run, whether a scratchpad is kept. It never names a model or
an effort level: that seam belongs to PRP-014. Tier in, depth out.

## 2. The two primary axes

**Tasks** — `^Task N:` lines, scoped to §5:

```sh
awk '/^## 5\./{f=1} /^## 6\./{f=0} f&&/^Task [0-9]+:/{c++} END{print c+0}' "$f"
```

- `# GOTCHA: task lines sit inside fenced blocks, not as markdown headings — a ^#{2,4} *Task`
  `# regex returns 0 for every PRP in this repo.`
- `# GOTCHA: scope between '## 5.' and '## 6.', never file-wide. PRPs quote the template's`
  `# illustrative "Task 1: MODIFY path/to/file.py" in §4 and §12 — PRP-011 carries three such`
  `# lines (L92, L417, L423) and a file-wide count reads 8 where the real list holds 5.`
- `# GOTCHA: do NOT anchor on '### 5.2'. PRP-002/003/004 have no 5.2 subsection — their tasks`
  `# sit under '## 5.' — a 5.2-anchored scope returns 0 for three of the twelve calibration PRPs.`

A count of **0** against a PRP that has a §5 task list is a **refusal**, not a tier: report
`§5 yields no task lines — fix the PRP or the counting rule` and stop. An unguarded zero silently
scores S — the minimum depth the rubric can assign — for a list the counter could not read.

**Files** — strip parentheticals first, then sum the integers that remain on the §1 `**Total:**`
line:

```sh
grep -m1 '^\*\*Total:' "$f" | sed 's/([^)]*)//g' | grep -oE '[0-9]+' | paste -sd+ - | bc
```

- `# GOTCHA: "7 new files (plus fixture bundles), 3 modified files" sums to 10; "0 new, 9`
  `# modified, 5 deleted (one deleted directory)" sums to 14. A digit INSIDE a parenthetical —`
  `# "8 new files (replacing 3 legacy modules), 2 modified" — is 10, not 13. No corpus line`
  `# does this today, which is exactly why the rule is written down.`
- `# GOTCHA: never count §1 table ROWS — PRP-012's rows cover whole directories and undercount.`

A `**Total:**` line yielding **no integer** after stripping is a **refusal**, not a tier: report
`§1 **Total:** line carries no integer file count — fix the PRP` and stop. An empty count compared
with `-le` is shell-dependent and would print a tier anyway.

## 3. Advisory corroborators

**Byte size** and the **>500-line cited-file** check are advisory corroborators: each may justify
a *stated* escalation, never a tier on its own. Over PRPs 001–012, byte size alone escalated
**four of twelve** (001, 002, 007, 009) to L while both work axes said M, on a knife edge —
PRP-002 at 41 KB scored L against PRP-011 at 40 KB scoring M. Bytes track verbosity, not work.

## 4. Tier table and the silent-failure modifier

S = ≤4 tasks **and** ≤3 files · M = ≤8 **and** ≤10 · L = anything above. The boundary predicate,
verbatim, so the four numbers live in one place:

```sh
if [ "$t" -le 4 ] && [ "$fc" -le 3 ]; then echo S; elif [ "$t" -le 8 ] && [ "$fc" -le 10 ]; then echo M; else echo L; fi
```

When the two primary axes disagree, **the higher tier wins** — sizing is a risk budget. Escalation
is **one-way**: a skill may raise a tier and must say why; it may never lower one.

**The silent-failure modifier** is the rubric's one judgement axis.

- **Categories**, verbatim from `prp-implement/SKILL.md:120-123`: **time/timezone/DST,
  concurrency, auth/expiry, parsing/encoding, rarely-run paths**.
- **Decision rule**, in that skill's own words: would a failure here surface *late and quietly*?
  Loud, build-caught work does not qualify.
- **Effect: one tier up from wherever the primary axes landed** — S→M, M→L, L→XL. Never L-only.
  Worked case: a three-task, three-file auth/expiry change scores S on both axes and is *entirely*
  silent-failure surface. It is **M** — a small PRP on a dangerous subject never lands on minimum.
- The escalation is **stated** in the verdict `note`, with its triggering category.

## 5. The citation axis

`citedFileCount` sets exactly one knob — whether the three style lenses run — and does **not** vote
on the tier. Those lenses compare a PRP's proposals against the repo files it cites, so zero
citations means zero style lenses at every tier.

- **Count:** distinct repo-relative paths appearing as `- file:` entries in the §4.1 MUST READ
  block, unioned with the file leaves of the §4.2 tree.
- **De-duplicate** by resolved path — a file cited in both §4.1 and §4.2 counts once.
- **Exclude:** `- url:` and `- docfile:` entries, paths under `PRPs/` (context, not comparable repo
  code), and any path absent from the target repo.
- `# GOTCHA: a PRP citing only external doc URLs counts 0 and correctly runs no style lenses.`
  `# That is the axis working, not a miscount — do not floor it at 1.`

## 6. Tier → knob table

| Tier | prp-draft Phase 2 | prp-review | prp-implement A3 | prp-implement A4 scratchpad |
|---|---|---|---|---|
| S | inline research, no fan-out | 1 round | inline drift check | no |
| M | 3 Explore agents | 2 rounds | 3-agent fan-out | no |
| L | one agent per subsystem | 3 rounds | one agent per citation cluster | yes |
| XL | L + adversarial refute pass | 3 rounds (same as L) | L + expert re-read | yes |

Style lenses are orthogonal to this table: 3 when `citedFileCount > 0`, else 0, at every tier.

## 7. The emitted verdict

Every consumer prints one line:

```text
SIZING: tasks=7 files=6 citedFiles=11 → M (bytes 91K advisory: no escalation stated)
```

Prose cannot *prevent* a quiet downgrade; printing the inputs beside the tier makes one visible on
its face, since any reader can recompute the row from them. Auditable, not enforced.

## 8. Calibration basis

Scored over PRPs 001–012 with the rules above: **9 M, 3 L, 0 S**. The three L verdicts are
PRP-005 (31 files), PRP-010 (11 tasks, 10 files) and PRP-012 (14 files).

S is empty here **by observation, not by design** — no PRP in this repo was written for a contained
one-file fix. It stays defined so the tier exists when one is, and §7's emitted inputs make a wrong
S visible at once. Re-score if the corpus grows materially.
