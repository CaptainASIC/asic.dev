---
name: improve-repo
description: Audit a repo for Captain ASIC standards drift — version sprawl, scaffold gaps, duplicated/repeated imports, structural and naming drift — then ship the fixes as focused, category-scoped PRs. Python gets a full standards audit (ruff/mypy surfaced, vertical-slice + entity-PK conformance); JS/TS gets a hygiene tier (version, imports). Composes existing tools: shells ruff/mypy, reuses release's version-location table, hands bugs to code-review and cleanup to simplify. Use when the user says "improve this repo", "polish the codebase", "audit repo standards", "consolidate versioning", "fix duplicate imports", or invokes /improve-repo. Never pushes — produces feature/improve-<category> branches the user merges.
---

# improve-repo

Finds where a repo drifts from Captain ASIC standards and ships the fixes as reviewable PRs. The
value is *consistency, applied*: an audit that terminates in a focused branch, not another
dashboard. It owns only the checks no existing tool performs — version consolidation, scaffold
conformance, import hygiene, structural/naming drift — and **composes** the rest: it shells out to
`ruff`/`mypy` and surfaces their output, reuses `release`'s version-location table, and hands
bug-hunting to `code-review` and cleanup to `simplify` rather than re-implementing them. It edits
code only on a feature branch, only after you pick a category, and never pushes.

Reference file: `references/improve_workflow.js` — the audit fan-out (one agent per enabled check).

## Phase 0 — Resolve the target

Target repo = current working directory unless the user names another; confirm when ambiguous. If
the working tree is dirty, report the uncommitted state and confirm before proceeding — fixes land
on a new branch off the current `HEAD`. A dirty tree is tolerated, not folded in: Phase 4 stages
**only** the files this skill itself edited for the picked category (never `git add -A`), so
pre-existing uncommitted changes stay out of the category commit. Offer to stash or commit them
first if the user prefers a clean tree.

## Phase 1 — Profile the repo (read-only)

Detect, before auditing:

1. **Languages** — Python (`pyproject.toml` / `*.py`), JS/TS (`package.json` / `*.ts` / `*.tsx`).
   Drives which checks' tiers are enabled.
2. **Repo type** — `multi` (multi-publish monorepo) when a workspace declaration exists
   (`[tool.uv.workspace]`, `package.json` `workspaces`, `pnpm-workspace.yaml`, `nx.json`/
   `lerna.json`) **or** more than one publishable manifest sits in distinct dirs (>1 `pyproject.toml`
   with `[project]`, or >1 non-`private` `package.json` with a `name`). Otherwise `single`. Decides
   version policy.
3. **Version locations** — walk the version-location table the `release` skill bundles (resolve its
   **absolute** path, below) against the repo (reuse it; do not duplicate). Record file / key /
   current value.
4. **Toolchain** — is `ruff` / `mypy` configured, and how is it invoked? Use `uv run` only when the
   repo uses `uv`; otherwise the repo's own invocation. **improve-repo runs against arbitrary
   repos — never assume `uv`.** An absent linter makes `standards-surface` report "skipped", never
   fail. On a JS/TS repo also detect the configured **JS formatter/linter** (prettier / eslint via
   `package.json` config or a `.prettierrc`/`.eslintrc`), so Phase 4 step 4 can validate
   auto-applied `import-hygiene` JS/TS edits with the repo's own tool; if none is configured, those
   edits commit without a JS format/lint pass (Phase 4 step 4 records this).
5. **Project kind** — `api` (FastAPI app factory / `main.py` entrypoint), `agent` (the
   `agent.py`/`tools.py`/`prompts.py` split), `cli` (console-script entrypoint / `main.py`), or
   `library` (no entrypoint, importable package only). Decides which scaffold layout
   `scaffold-conformance` judges against, since `kind_variants.md` makes the expected files
   kind-specific (api/cli need `main.py`, agent needs the agent.py/tools.py/prompts.py split,
   library needs neither). If the kind is genuinely ambiguous, record `kind: 'unknown'` — the
   check then only flags the kind-agnostic canonical files and never over-flags a missing agent
   split on a CLI/library repo (below).

**Resolve the plugin's bundled reference paths to absolute paths.** `improve-repo` audits the
current working directory, which is an *arbitrary* repo — a relative `../release/...` or
`../scaffold/...` path would resolve against the target repo (where those files do not exist), not
against this plugin. So before calling the Workflow, resolve the absolute path of this skill's own
directory and derive the sibling-skill reference files from it:

- `versionLocationsPath` → `<asic-tools skills dir>/release/references/version_locations.md`
- `scaffoldSpecPaths` → the three scaffold references:
  `<…>/scaffold/references/file_templates.md`, `<…>/scaffold/references/kind_variants.md`,
  `<…>/scaffold/SKILL.md`

Compute the skills directory from this `SKILL.md`'s location (it is
`<…>/skills/improve-repo/SKILL.md`, so the skills dir is two levels up). Confirm each file exists.
Pass these absolute paths into the Workflow under `profile` (below) so the check prompts read the
real bundled specs rather than nonexistent paths in the audited repo.

When `graphify-out/graph.json` exists in the target, orient with `graphify query` before reading.

## Phase 2 — Run the audit Workflow

Invoking this skill is your opt-in to multi-agent orchestration. Call the **Workflow** tool
directly — do not ask again:

- `scriptPath`: the bundled `references/improve_workflow.js`.
- `args`: `{ "repoPath": "<resolved path>", "profile": { "python": <bool>, "frontend": <bool>, "repoType": "single|multi", "kind": "api|agent|cli|library|unknown", "ruff": <bool>, "mypy": <bool>, "versionLocationsPath": "<abs path>", "scaffoldSpecPaths": ["<abs file_templates.md>", "<abs kind_variants.md>", "<abs scaffold SKILL.md>"] } }`.

The script fans out one agent per *enabled* check (enabled when its tier matches the profile), each
graphify-first and instructed to report only `file:line`-grounded drift. It returns
`{ categories, skipped }` — findings grouped by check, each tagged severity / safety / estimated
diff size.

## Phase 3 — Present the report + hand off

Render a **markdown report in chat** (no HTML — `asicdash` owns the dashboard lane), grouped by
category. Per category: finding count, severity mix, total estimated diff size, recommendation
strength (Strong / Worth fixing / Speculative). List skipped checks with the reason.

**Recommendation-strength derivation (deterministic).** Compute it from two inputs already in the
Workflow return — the category's `safety` and its highest finding `severity` (rank
`blocker` > `major` > `minor` > `nit`). Apply the first rule that matches, in order:
- **Strong** — an `auto`-safety category (mechanical, auto-applicable fix) whose top severity is
  `blocker` or `major`.
- **Worth fixing** — any other category whose top severity is `blocker` or `major` (i.e. a
  `propose`-safety category at that severity), OR an `auto`-safety category whose top severity is
  `minor`.
- **Speculative** — everything else: a category whose top severity is `nit`, or a `propose`-safety
  category whose top severity is `minor`.

No new schema field is needed; the inputs are the existing per-finding `severity` and the category
`safety`.

Then hand off the lanes improve-repo does not own — offered, never auto-run:
- Bugs → *"Run `/code-review` for correctness findings."*
- Cleanup → *"Run `/simplify` for reuse and dead-code cleanup."*

## Phase 4 — Pick → PR

The user picks one or more categories. For each picked category:

1. Branch `feature/improve-<category>` off the current `HEAD` — never main.
2. **Size guard** — if the category's fixes would touch more than 25 files (26 or more), report the
   count and offer to split by top-level package/area into sub-branches before applying. The count
   is the number of **distinct `file` values across the category's auto-applicable findings** (the
   `auto`-safety findings this step will actually write — `propose` findings go to the checklist and
   do not count). A finding that touches more than one file (e.g. a future cross-file fix) contributes
   each distinct file it edits to the set, and a file edited by several findings is counted once
   (it is a set of paths, not a sum of findings). **The set is the UNION of the findings' files AND
   any extra files an auto fix legitimately edits beyond the files its findings name** — for
   `version-consolidation` this includes the files matched by the mandated repo-wide re-grep of the
   OLD version string (`version_locations.md` requires re-grepping the old string repo-wide, which
   reaches README/docs/usage-example files no finding enumerated). Those re-grep-matched files join
   the set even though no finding names them. The guard fires when that distinct-file set has 26
   or more entries; 25 or fewer applies without splitting.
3. Apply only `safety: auto` fixes (mechanical — a `__version__` literal synced to match the
   pyproject root version, a removed duplicate import). `safety: propose` findings (generative or
   contract-changing —
   creating missing scaffold files, renaming a DB primary key) are written into the PR body as a
   checklist for the human, never auto-applied.
4. If the repo configures a formatter/linter, run it clean before committing. For the
   `standards-surface` (auto) category, the apply mechanism IS the linter's own autofix — but scope
   it to the FILES IN THIS CATEGORY's findings, never the whole tree: run
   `ruff format <those paths>` then `ruff check --fix <those paths>` (or the repo's equivalent) —
   but only for the findings whose `fixable` is `true`. A standards-surface finding whose `fixable`
   is `false` **or absent** routes to the PR-body checklist as a manual item, never auto-applied
   (the gate is total: absent defaults to `false`). A repo-wide `ruff format .` / `ruff check --fix .`
   would (a) reformat files never surfaced as
   findings, breaking the category-scoped unit of work, and (b) touch pre-existing dirty/unrelated
   files in a tolerated dirty tree (Phase 0), making "files this skill edited" unbounded and
   sweeping the user's uncommitted work into the commit. Scope to the finding paths instead.
   **Whole-file rewrite guard (dirty finding-file).** `ruff check --fix` / `ruff format` rewrite the
   ENTIRE file, not just the finding's lines — so if a standards-surface finding-file already
   carries pre-existing uncommitted edits in the tolerated dirty tree (Phase 0), running ruff on it
   would rewrite those dirty lines too and the scoped `git add <path>` (step 5) would sweep them
   into the category commit, violating the clean-commit guarantee. Path-scoping alone does not
   prevent this, because the unit ruff rewrites is the file, not the line. Therefore, before running
   `ruff --fix`/`ruff format` on a standards-surface finding-file, require that file to be clean: if
   it has uncommitted changes, **skip the autofix for that file (route the finding to the PR-body
   checklist as a manual item) or have the user stash/commit it first** — never run whole-file ruff
   over a dirty finding-file. `mypy`
   has no autofix, so its findings are surfaced only — type-hint/typing fixes route to the PR-body
   checklist as manual items, not auto-applied. For every other category, run
   `ruff format <edited paths> && ruff check <edited paths>` (no `--fix`) so the formatter/linter
   only validates the specific fixes the skill itself made.

   **Toolchain-aware validation lane (not ruff-only).** The validation tool is selected by the
   edited file's language, not hardcoded to ruff: `import-hygiene` is `python+frontend` and `auto`,
   so it can auto-apply edits to JS/TS files on a frontend-only repo, which has no ruff. For
   **Python** edited paths, validate with the repo's `ruff`/`mypy` exactly as above (gated on
   presence — an absent linter skips that pass, never fails). For **JS/TS** edited paths, validate
   with the repo's **configured** JS formatter/linter run clean (e.g. `prettier --write` then
   `eslint <those paths>`, or the repo's equivalent), gated on presence the same way
   `standards-surface` gates ruff/mypy: detect the configured JS toolchain in Phase 1 and validate
   only if it exists. If a JS/TS repo configures **no** formatter/linter, the import-hygiene
   auto-fix commits without an automated format/lint pass — state this in the PR body — because the
   fix is a purely mechanical single-file import edit (collapse inline re-imports, de-duplicate
   aliases) that changes no contract and there is no tool to run; do not fabricate or assume one.
5. Commit per category — **stage only the files this skill edited for this category**
   (`git add <those specific paths>`), never `git add -A` / `git add .`. "The files this skill
   edited" is the same union the step-2 size guard counts: the findings' files **plus** any extra
   files an auto fix legitimately touched beyond them — for `version-consolidation`, the files
   matched by the mandated repo-wide re-grep of the old version string (README/docs/usage-example
   files no finding enumerated). Stage that full edited set, not the findings' files alone. The
   working tree may be dirty (Phase 0 only confirms, it does not require a clean tree), so a blanket
   stage would sweep pre-existing uncommitted changes into the category commit and break the
   category-scoped unit of work. Commit message: `refactor(<category>): <subject>` (or `fix`/`chore` as fits) — Conventional
   Commits, imperative, no AI attribution. Do not push.
6. Print a PR body: what changed, the auto-applied fixes, the propose-only checklist, the
   validation run. The user opens and merges via GitKraken.

## Carve-out (non-negotiable)

A consolidation or simplification fix never strips trust-boundary input validation, authn/authz,
error/data-loss handling, or accessibility. Any fix that changes a database or API contract
(renaming a primary key, altering a route) is `propose`, never `auto`. Be lazy, never negligent.

## Anti-patterns

- Don't re-implement `ruff`/`mypy` checks — run them and surface their output. No parallel patterns.
- Don't call `code-review`/`simplify` from inside the Workflow fan-out — they are main-thread
  skills, handed off in Phase 3.
- Don't force single-version on a multi-publish monorepo — detect repo type first.
- Don't auto-apply `propose` findings or anything that rewrites a DB/API contract.
- Don't assume `uv` or that linters exist — improve-repo runs against arbitrary repos.
- Don't push or open the PR — print the branch and body; the user merges via GitKraken.
- Don't produce one whole-repo PR — category-scoped branches are the unit of work.

## Verification

- [ ] Target resolved; dirty-state confirmed before branching.
- [ ] Repo profiled (languages, repo type, version locations, toolchain) before the audit.
- [ ] Workflow ran with `args.repoPath` + `profile`; disabled/uninstrumented checks reported skipped.
- [ ] Report grouped by category in chat (markdown, not HTML); skipped checks listed.
- [ ] Only `auto` fixes applied; `propose` findings went to the PR-body checklist.
- [ ] Branch `feature/improve-<category>`, Conventional Commit, no AI attribution, not pushed.
- [ ] `code-review`/`simplify` hand-off offered, not forced.
