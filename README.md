# asic.dev

Agent-harness tooling for Claude Code, shipped as a Claude Code plugin marketplace.

| Tool | What it does |
|---|---|
| [asicdash](#asicdash) | Config + usage dashboard: audit visible and invisible agent config, chart Claude usage |
| [idea-refine](#idea-refine) | Refine a raw idea into a build-ready one-pager — upstream of prp-draft |
| [prp-draft](#prp-draft) | Research-first generator for Product Requirements Prompts |
| [prp-review](#prp-review) | Adversarial review gate: 8-lens Workflow hardens a PRP before implementation |
| [prp-implement](#prp-implement) | Two-phase PRP executor: drift-checked plan → pause → verified execution + close-out |
| [scaffold](#scaffold) | Standards-enforced Python project bootstrap — verified runnable, not a paper template |
| [release](#release) | Multi-location version bump + changelog, derived from Conventional Commits |
| [improve-repo](#improve-repo) | Repo-wide standards-conformance auditor: finds version/scaffold/import/naming drift, ships category-scoped fix PRs |
| [sync-rules](#global-rules) | Deploy the bundled global engineering rules to `~/.claude/CLAUDE.md` on any machine |
| [diagram](#diagram) | Generate editable draw.io architecture/network/system diagrams from a description, or visualize a repo |
| [okf](#okf) | Open Knowledge Format: vendored spec, offline conformance validator, index generator |

## Install

### As a plugin (recommended)

New machine, start to finish:

```
/plugin marketplace add CaptainASIC/asic.dev      # 1. add the marketplace
/plugin install asic-tools@asic-dev               # 2. install the plugin
                                                  # 3. restart Claude Code (skills register at startup)
/asic-tools:sync-rules                            # 4. optional: deploy the global engineering
                                                  #    rules to ~/.claude/CLAUDE.md (diff-aware)
```

Skills are namespaced: `/asic-tools:asicdash`, `/asic-tools:idea-refine`,
`/asic-tools:prp-draft`, `/asic-tools:prp-implement`, `/asic-tools:scaffold`,
`/asic-tools:release`, `/asic-tools:sync-rules`, `/asic-tools:diagram`. Plugin skills show up in the desktop app's customize page;
filesystem personal skills currently do not
([claude-code#66998](https://github.com/anthropics/claude-code/issues/66998)).

### Updating

Plugin versions are pinned — merging new commits to this repo ships nothing until the
plugin version bumps and you pull it:

```
claude plugin marketplace update asic-dev         # refresh the marketplace clone
claude plugin update asic-tools@asic-dev          # pull the new plugin version
                                                  # restart Claude Code
/asic-tools:sync-rules                            # re-sync if the release changed the rules
```

### Dev mode (this repo checked out)

```bash
./install.sh
```

Symlinks each skill under `plugins/asic-tools/skills/` into `~/.claude/skills/` — bare
`/asicdash` and `/prp-draft` names, and edits in the repo are live without reinstalling.
Don't combine both installs: you'd get duplicate skill registrations.

### Global rules

[plugins/asic-tools/rules/CLAUDE.global.md](plugins/asic-tools/rules/CLAUDE.global.md) is
the consolidated engineering rule set the skills assume (structure caps, uv-only, test
trio, git constraints, naming standards, canonical code examples). It ships inside the
plugin, so on any machine with the plugin installed:

```
/asic-tools:sync-rules
```

installs or updates `~/.claude/CLAUDE.md` — diff-aware, never silently clobbering local
edits. Dev mode: `install.sh` does the same copy. Always a copy, not a symlink — the desktop app
skips symlinks in some loaders.

### Enforcement hooks

`asic-tools` ships `hooks/hooks.json`, registered automatically when the plugin is enabled. It binds
three standing rules that prose alone could not:

| Rule | Behaviour |
|---|---|
| AI attribution in a commit message | **denied** — no escape. AI is a tool, not an author. |
| `git push` | **denied** — the user pushes and merges via GitKraken. |
| `git commit` on `main` / `master` | **asks** — you approve or reject in a permission dialog. |

`ask` is the escape hatch by design: an env var or flag file would be forgeable by the agent, a
permission dialog is not. Hooks load at session start — **restart Claude Code after updating the
plugin**, then confirm with `/hooks` (source: `Plugin`).

These hooks bind the agent, not you: a commit you make yourself in a terminal is untouched.

---

## asicdash

Config + usage dashboard for Claude Code (formerly **agentdash**). Audits visible and
invisible agent-harness config across global and project scope, and charts Claude usage from
local session transcripts. One deterministic CLI; the Claude skill is a thin
wrapper around it.

### Why

A plain inventory of skills and agents is `ls` with extra steps. The value is in what you cannot
see by listing directories:

- **Hook registrations** — commands firing invisibly on session events (flattened from
  `settings.json`, deduplicated, executable-existence checked)
- **Plugin-injected surface** — skills, agents, commands, and hooks shipped by installed plugins
- **Always-loaded context cost** — token estimates for `CLAUDE.md`, rules, memory, `AGENTS.md`
  loaded into every session
- **Rot and shadowing** — hook scripts on disk that nothing references, project entries shadowing
  global ones, broken frontmatter, missing executables
- **Claude Code usage** — per-day activity from `~/.claude/projects/**/*.jsonl` (every transcript
  there is a Claude Code session): GitHub-style contribution heatmap colored by launch surface
  (Terminal = CLI, Desktop = the Claude desktop app; claude.ai Chat leaves no local transcript and
  is labeled "no local data"), at-a-glance token totals for today / last 7 days / last 30 days /
  all-time, hover tooltips, per-day breakdown modals, weekly stacked token chart

### Usage

```bash
# plugin install path (marketplace clone); dev-mode symlink path is ~/.claude/skills/asicdash/
DASH=~/.claude/plugins/marketplaces/asic-dev/plugins/asic-tools/skills/asicdash/asicdash.py
python3 "$DASH"                              # themed HTML report, opens in browser (default)
python3 "$DASH" --cli                        # aligned table on stdout
python3 "$DASH" --json                       # machine-readable
python3 "$DASH" --html report.html --no-open # explicit path, no browser launch
python3 "$DASH" --project ~/Repositories/Airi
```

The HTML report (`html_report.py` + `usage.py`, stdlib only like the scanner) is a single
self-contained file: collapsible sections per scope, plugins folded to one block each with
skill/agent chips, attention banners, the usage heatmap, a context-cost bar, and ASIC
Light/Dark themes (follows the system scheme, toggle persisted in `localStorage`).

In Claude Code: ask "show my config dashboard" (triggers the `asicdash` skill).

### Coverage

| Source | Scope | Method |
|---|---|---|
| `~/.claude/{skills,agents,commands,rules}` | global | frontmatter parse |
| `.claude/{skills,agents,commands,rules}` | project | frontmatter parse |
| `settings.json` / `settings.local.json` (both scopes) | hooks, statusLine, permissions, env | JSON flatten + executable check |
| `installed_plugins.json` → plugin contents | plugin | walk install path |
| `~/.claude/hooks/` | orphan detection | cross-ref vs registrations |
| `CLAUDE.md`, `CLAUDE.local.md`, managed memory `MEMORY.md` | global + project | token estimate |
| `.mcp.json`, `~/.claude.json` mcpServers | global + project | names + command |
| `AGENTS.md` | project | token estimate |
| `~/.claude/projects/**/*.jsonl` session transcripts | usage (HTML report) | per-day token/session aggregation |

### Known gaps, on purpose

- **Claude routines / scheduled cloud agents**: stored server-side, no local file. Reported as
  `n/a`; list with `/schedule` in Claude Code.
- **claude.ai Chat usage**: web sessions leave no local transcript; the usage section labels
  Chat "no local data" rather than guessing.
- Token counts are `bytes / 4` estimates, not tokenizer output.

### Maintenance

Claude Code's config layout shifts between versions. All scanned locations live in one table:
`known_paths()` in [asicdash.py](plugins/asic-tools/skills/asicdash/asicdash.py). Fix
breakage there. Transcript field assumptions (entrypoint values, usage keys) live in
[usage.py](plugins/asic-tools/skills/asicdash/usage.py).

---

## idea-refine

Refines a raw idea into a sharp, build-ready concept **before** any PRP or code — the cheap
filter that runs upstream of `prp-draft` so its expensive research budget never lands on the
wrong idea.

### Why

`prp-draft` assumes the feature ask is already concrete; it does verified-context research, not
"is this the right thing to build". That leaves a gap at the front of the pipeline: raw idea →
formed feature. This skill fills it with structured divergent/convergent thinking, and it is
deliberately *not* a yes-machine — weak ideas get pushed back on, KISS/YAGNI steer toward the
simplest version that solves the real problem.

1. **Understand & expand** — restate as "How Might We", 3–5 sharpening questions, 5–8 idea
   variations through lenses (inversion, simplification, 10×, audience-shift, …)
2. **Evaluate & converge** — cluster to 2–3 distinct directions, stress-test on
   value/feasibility/differentiation, surface hidden assumptions
3. **Sharpen & ship** — a one-pager: problem, recommended direction, assumptions-to-validate,
   MVP scope, and an explicit **Not Doing** list

Writes exactly one file: `PRPs/ideas/<slug>.md` (creates `PRPs/ideas/` if missing), co-located
with `PRPs/` so the idea → PRP chain stays in one tree. The one-pager's fields map straight onto
the `prp-draft` template (Not Doing → §1 strict non-goals, assumptions → §4.4 / SPECULATIVE
markers), and the skill offers the `prp-draft` hand-off rather than forcing it.

### Usage

In Claude Code: `/idea-refine`, or say "refine this idea" / "stress-test my plan" mid-chat.

Layout: [SKILL.md](plugins/asic-tools/skills/idea-refine/SKILL.md) is self-contained — the
ideation lenses and evaluation criteria are inlined, no reference files.

---

## prp-draft

Turns a feature discussion (mid-chat "let's make this a PRP", or a pasted design summary) into
a **Product Requirements Prompt** — a self-contained, implementation-ready instruction document
that a coding agent (Claude Code) executes with no other context.

### Why

A PRP is only as good as its specifics. The failure mode of template-driven generation is
confident garbage: invented line numbers, guessed API signatures, gotchas recalled from
training data instead of read from source. An implementing agent trusts those and burns hours.
So this skill is ~20% template, ~80% enforced process:

1. **Context sweep** — README, PLANNING, TASKS, Serena memories, prior PRPs, tooling/lockfiles
2. **Codebase research** — when a graphify knowledge graph exists, leads with `graphify
   query`/`explain`/`path` to scope which files the feature touches, then reads them; library
   claims verified against installed versions; evidence required for every CRITICAL/GOTCHA
3. **Refusal gate** — if context is insufficient, it stops and lists what's missing instead
   of drafting thin
4. **Interview** — open design decisions become batched questions, recommendation first
5. **Draft** — canonical 12-section format (objective → problem → architecture decisions →
   verified context → blueprint → per-file instructions → tests → smoke → acceptance →
   doc updates → anti-patterns → future work)
6. **Self-audit** — paths re-verified, commands copy-pasteable, git constraints embedded

Writes exactly one file: `PRPs/PRP-NNN_TITLE.md` (creates `PRPs/` if missing). TASKS/PLANNING/
memory updates are the *implementing* agent's job, spelled out in the PRP's §10.

### Usage

In Claude Code: `/prp-draft`, or just say "turn this into a PRP" mid-conversation.

Layout: [SKILL.md](plugins/asic-tools/skills/prp-draft/SKILL.md) is the workflow driver;
[prp_template.md](plugins/asic-tools/skills/prp-draft/references/prp_template.md) and
[style_guide.md](plugins/asic-tools/skills/prp-draft/references/style_guide.md) hold the
section skeleton and the standing engineering rules (structure caps, stack defaults, DB
naming, test minimums, git constraints) loaded only when drafting.

---

## prp-review

Adversarial review gate between `prp-draft` and `prp-implement`. Given a drafted PRP, it runs a
Workflow that fans out eight distinct-lens reviewers — five on logic (requirements coverage,
architecture soundness, over-build, edge-cases & verifiability, silent-failure) and three on style/convention drift against
the real target repo (naming, structure, error/test/docstring conventions) — adjudicates their
findings to drop false positives, applies the blocker/major fixes to the PRP in place, and
re-reviews up to three rounds. It appends a `## Review Log` to the PRP and surfaces any residual
blockers.

### Why

`prp-implement` trusts the PRP completely, and `prp-draft`'s self-audit is a single agent
checking its own work. An independent adversarial pass catches logic gaps and convention drift
before any implementation budget is spent — the cheap gate before the expensive run.

### Usage

In Claude Code: `/asic-tools:prp-review PRP-NNN`, or `/prp-review` to target the newest
ready PRP, or accept the hand-off `prp-draft` offers after a draft. Invoking it opts into the
multi-agent Workflow. Claude Code only.

Layout: [SKILL.md](plugins/asic-tools/skills/prp-review/SKILL.md) is the driver;
[references/review_workflow.js](plugins/asic-tools/skills/prp-review/references/review_workflow.js)
is the fan-out/adjudicate/apply/re-review Workflow script.

---

## prp-implement

Executes a PRP in the same two-prompt rhythm the format was designed for: **"review the
PRP and plan for implementation"** → **"execute the plan"** — formalized so neither half
gets skipped under time pressure.

Phase A loads the PRP *and* its §4.1 MUST READ context, checks preconditions (status,
dependency PRPs, runnable tooling), then runs a **drift check**: the PRP was written
against the codebase as of its date, so every referenced file, gotcha, and code snippet is
verified against current reality before anything executes. Material drift stops the run
with a proposed amendment — executing a stale PRP produces confident wrong code. On a resume
(the PRP's branch already exists), it orients from the working scratchpad and re-checks only the
cited files that changed since the branch forked — including any that landed on the base
meanwhile — rather than re-running the whole sweep. It ends by presenting the plan and pausing
for approval.

Phase B executes task-by-task in §5 order (test-first where §7 defines tests, per-task
verify, surgical scope — unlisted changes stop and ask), walks the §9 validation levels in
order without skipping, and commits in Conventional format. On multi-task or subsystem PRPs it
keeps a gitignored working scratchpad (`PRPs/.work/PRP-NNN-scratchpad.md`) — architectural map,
decisions, and "Discovered During Work" — read at each task boundary to resist context decay on
long runs, then promoted into the close-out artifacts and deleted. Phase C is the close-out
ritual: acceptance checklist ticked against reality, PRP status flipped, §10 doc updates
applied (PLANNING/TASKS/CHANGELOG/Serena memory), and a final report of files-touched vs
the PRP's own table.

In Claude Code: `/asic-tools:prp-implement PRP-040`.

---

## scaffold

Bootstraps a new Python project to a strict standard: uv + ruff (line-length 100) + mypy +
pytest with coverage, Pydantic v2 settings (`get_settings()` singleton), structured
exceptions and logging, vertical-slice layout, and project docs that drive the agent
workflow from day one (`PLANNING.md`, `TASKS.md`, `CHANGELOG.md`, `CLAUDE.md`, `PRPs/`).

The defining constraint: **the scaffold must run before it's reported done** — `uv sync`,
`uv run pytest`, `uv run ruff check .`, `uv run mypy src/` all green, with generated tests
demonstrating the expected/edge/failure pattern against real code. Four kinds: `api`
(FastAPI), `agent` (canonical `agent.py`/`tools.py`/`prompts.py` split), `cli` (argparse +
entry point), `library`. Git ends on `feature/initial-scaffold`, never main.

In Claude Code: `/asic-tools:scaffold`. Templates:
[file_templates.md](plugins/asic-tools/skills/scaffold/references/file_templates.md),
[kind_variants.md](plugins/asic-tools/skills/scaffold/references/kind_variants.md).

---

## release

Cuts a release without version drift: surveys every version location in the repo
(pyproject, `__version__`, Claude plugin manifests, package.json, Xcode
`MARKETING_VERSION`, README install snippets — see
[version_locations.md](plugins/asic-tools/skills/release/references/version_locations.md)),
recommends the SemVer bump from Conventional Commits since the last tag, writes a
CHANGELOG entry that matches the file's existing style, and commits on `release/vX.Y.Z`.

Deliberately stops there: pushing, merging, tagging, and the GitHub release are the
user's actions — the skill emits the post-merge checklist and a ready-to-paste release
body. It also re-greps the old version string after updating to catch locations the
survey missed, and refuses to proceed if existing version locations already disagree.

In Claude Code: `/asic-tools:release`.

---

## improve-repo

Audits an existing repo for drift from the standing engineering rules and ships the fixes as
focused, reviewable PRs — the counterpart to `scaffold` (which enforces standards at birth) and
`prp-review`/`prp-implement` (which enforce them per PRP). It profiles the repo (languages,
single-deployable vs multi-publish, version locations, toolchain, project kind), then runs a
Workflow that fans out one adversarial agent per enabled check: version-consolidation,
import-hygiene, shared-import-extraction, scaffold-conformance, standards-surface, and
naming-conventions. Python gets the full standards tier; JS/TS gets a hygiene tier (version +
imports).

It **composes** rather than reinvents: shells out to the repo's own `ruff`/`mypy`, reuses
`release`'s [version_locations.md](plugins/asic-tools/skills/release/references/version_locations.md)
table, and hands bug-hunting to `code-review` and cleanup to `simplify`. Findings come back as a
markdown report grouped by category; once you pick a category, the skill applies the mechanical
fixes on a `feature/improve-<category>` branch with a Conventional Commit and a ready-to-paste PR
body, while generative or contract-changing fixes go to a human checklist. Like `release`, it never
pushes.

In Claude Code: `/asic-tools:improve-repo`.

## diagram

Turns a natural-language description — or an existing repo's structure — into an editable
`.drawio` file plus a rendered image, via the native draw.io desktop CLI. Diagrams become
version-controllable artifacts: the editable source is committed beside the picture under
`docs/diagrams/`. Picks one of six types (ERD, UML class, sequence, architecture, ML/DL,
flowchart), resolves vendor-correct AWS/Azure/GCP/Kubernetes icons and AI/LLM brand logos via a
10k+-shape search index, applies a semantic color system, vision-self-checks the render for
overlaps/clipping, iterates with you, then exports PNG/SVG/PDF and offers to embed the result into
a PRP or README. Also visualizes a Python/JS-TS/Go/Rust repo's import graph or a Python class
hierarchy (Graphviz auto-layout). Ported and adapted (MIT) from
[Agents365-ai/drawio-skill](https://github.com/Agents365-ai/drawio-skill).

**Prerequisite:** the draw.io desktop CLI — `brew install --cask drawio`. Optional Graphviz
(`brew install graphviz`) enables auto-layout for large code-structure graphs. When the CLI is
absent the skill fails fast with the install command and falls back to a diagrams.net browser URL.

In Claude Code: ask "draw a diagram of …" / "visualize this module structure" (triggers the
`diagram` skill), or `/asic-tools:diagram`.

---

## okf

Adopts Google's [Open Knowledge Format](https://github.com/GoogleCloudPlatform/knowledge-catalog)
v0.1 as the standard shape for knowledge bundles and LLM-wikis — a directory of markdown with YAML
frontmatter, one required field (`type`), two reserved filenames (`index.md`, `log.md`). The spec is
vendored offline and pinned (Apache-2.0, see `NOTICE.md`), so the skill needs no network and adds no
dependency: stdlib `python3` only.

The value is the **validator**. OKF §9 conformance is mechanically checkable, and nothing else
checks it.

| Exit | Meaning |
|---|---|
| `0` | Conformant (recommendation warnings may print; `--quiet` silences them) |
| `1` | Non-conformant — each violation named by path |
| `2` | Usage/IO error |
| `3` | Indeterminate — frontmatter outside the parseable subset; a validator limitation, not a verdict |

It deliberately **never fails** a bundle for missing optional fields, unknown `type` values, unknown
extra keys, broken cross-links, or a missing `index.md` — §9 forbids consumers from rejecting on
those, so over-strictness would be a defect. It equally never *silently accepts*: a line it cannot
read surfaces as exit `3`, never a skip, and a missing or empty `type` behind such a line is still
exit `1`. `type: ""`, `type: null`, and `type: ~` are an empty `type`, not content.

### Usage

```bash
S="${CLAUDE_PLUGIN_ROOT:-$HOME/.claude}/skills/okf"
python3 "$S/scripts/validate_okf.py" ./my-bundle
python3 "$S/scripts/okf_index.py" ./my-bundle/tables --write
```

`okf_index.py --write` preserves frontmatter already present, so regenerating the bundle-root
`index.md` never destroys its `okf_version` declaration (§11).

## License

[MIT](LICENSE) © Captain ASIC
