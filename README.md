# asic.dev

Agent-harness tooling for Claude Code, shipped as a Claude Code plugin marketplace.

| Tool | What it does |
|---|---|
| [asicdash](#asicdash) | Config + usage dashboard: audit visible and invisible agent config, chart Claude usage |
| [idea-refine](#idea-refine) | Refine a raw idea into a build-ready one-pager — upstream of prp-draft |
| [prp-draft](#prp-draft) | Research-first generator for Product Requirements Prompts |
| [prp-review](#prp-review) | Adversarial review gate: tier-sized Workflow hardens a PRP before implementation |
| `citation-scout` (agent) | Read-only evidence extractor the PRP fan-outs delegate to — returns `path:line` records, never conclusions |
| `architecture-judge` (agent) | Chooses a PRP's §3 architecture from a stated angle, returning each decision with the alternative it rejected |
| [prp-implement](#prp-implement) | Two-phase PRP executor: drift-checked plan → pause → verified execution + close-out |
| `prp_status.py` (script) | Lints every PRP's `**Status:**` against the five-value standard and generates `PRPs/STATUS.md` |
| [scaffold](#scaffold) | Standards-enforced Python project bootstrap — verified runnable, not a paper template |
| [release](#release) | Multi-location version bump + changelog, derived from Conventional Commits |
| [improve-repo](#improve-repo) | Repo-wide standards-conformance auditor: finds version/scaffold/import/naming drift, ships category-scoped fix PRs |
| [sync-rules](#global-rules) | Deploy the bundled global engineering rules to `~/.claude/CLAUDE.md` on any machine |
| [okf](#okf) | Open Knowledge Format: vendored spec, offline conformance validator, index generator |

## Install

### As a plugin (recommended)

New machine, start to finish:

```
/plugin marketplace add CaptainASIC/asic.dev      # 1. add the marketplace
/plugin install asic-tools@asic-dev               # 2. install the plugin
                                                  # 3. restart Claude Code (skills register at startup)
                                                  # 4. wire the MCP servers the skills need
                                                  #    (see below)
/asic-tools:sync-rules                            # 5. optional: deploy the global engineering
                                                  #    rules to ~/.claude/CLAUDE.md (diff-aware)
```

**Prerequisites — three MCP servers.** These are install-time requirements, not routing rules;
`docs/agent-tooling.md` says which lane owns what.

| Server | Used by | Needs |
|---|---|---|
| **Serena** | `prp-draft` Phase 1 reads `.serena/memories/prp/`; `prp-implement` close-out writes one | project activation (`activate_project`) |
| **Ref** | `prp-draft` Phase 2 verifies external APIs against versioned docs | an account/API key |
| **Snyk** | `prp-implement`'s fail-closed security gate | `SNYK_TOKEN` |

Without them: `prp-draft` cannot verify a library claim, and `prp-implement` stops at its security
gate — which is fail-closed by design, so an absent Snyk blocks rather than silently passing.

Skills are namespaced: `/asic-tools:asicdash`, `/asic-tools:idea-refine`,
`/asic-tools:prp-draft`, `/asic-tools:prp-review`, `/asic-tools:prp-implement`,
`/asic-tools:scaffold`, `/asic-tools:release`, `/asic-tools:sync-rules`,
`/asic-tools:improve-repo`, `/asic-tools:okf`. Two workflow commands
sit in the same namespace — `/asic-tools:prp-review-fanout` and `/asic-tools:improve-repo-audit`,
the raw fan-outs behind `prp-review` and `improve-repo` (see below). Plugin skills show up in the desktop app's customize page;
filesystem personal skills currently do not
([claude-code#66998](https://github.com/anthropics/claude-code/issues/66998)).

### Companion skill: archify

Diagrams are [archify](https://github.com/tt-a1i/archify)'s job (MIT, third-party). It turns a
description, a repo, or pasted Mermaid into a validated, interactive standalone HTML/SVG diagram.
`asic-tools` no longer ships a diagram skill: 2.0.0 removed the earlier `diagram` skill.

```
npx skills add tt-a1i/archify -g      # needs Node.js 18+
```

`/asic-tools:sync-rules` checks the installed version and offers this install or upgrade; it never
runs it without asking. archify checks for new stable releases during delivery; set
`ARCHIFY_UPDATE_CHECK_DISABLED=1` to turn that off.

**Upgrading from 1.x:** legacy diagram sources made with the earlier skill still open in their
original desktop editor; nothing converts them. On a dev-mode (symlink) install, remove the stale
link once: `cd ~/.claude/skills && rm diagram`.

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
`/asicdash` and `/prp-draft` names, and edits in the repo are live without reinstalling. It also
symlinks each agent under `plugins/asic-tools/agents/` into `~/.claude/agents/`: auto-discovery
covers the plugin install only, so without this the fan-outs fall back to generic subagents.
Don't combine both installs: you'd get duplicate skill registrations. It is worse than duplication
— the plugin cache is pinned to an installed version, so a skill invoked through the plugin can run
a script many versions behind this repo, and a change you just made appears to have no effect.
Check which is live:

```bash
grep -A2 asic-tools ~/.claude/plugins/installed_plugins.json   # installed version
grep '"version"' plugins/asic-tools/.claude-plugin/plugin.json  # repo version
```

**Workflow commands.** The plugin also ships `/asic-tools:prp-review-fanout` and
`/asic-tools:improve-repo-audit` — the raw multi-agent fan-outs. The skills
(`/asic-tools:prp-review`, `/asic-tools:improve-repo`) are the supported entry points. Calling a
fan-out directly skips the skill's setup: for review, PRP resolution and sizing (Phase 0) and the
review-log append (Phase 2); for the audit, the repo profile (Phase 1) that resolves the absolute
reference-spec paths the audit agents read.

**Routing.** Delegated work is tiered rather than inheriting whatever model the session is on:
the volume stages (review lenses, repo-audit checks, citation scouting) run on cheaper tiers,
while adjudication and architecture selection take the strongest tier available. Main-thread
work — drafting, planning, the implementation loop — follows the session model: a skill can set
`model`/`effort` for the current turn only, and these phases span several turns.

**Top-tier model (opt-in).** `/config` → `top_tier_model` picks the model for the prp-review
adjudicator: `fable` (default) or `mythos`, which runs `claude-mythos-5-1` and needs Cyber
Verification Program access. An account without it that selects `mythos` runs the adjudicator on
the session model with a Claude Code warning, not on Mythos. The prp-draft architecture panel stays
on Fable: the Agent tool's per-call `model` accepts only `sonnet`, `opus`, `haiku` and `fable`. The plugin
requires Claude Code 2.1.271 or later (the setting's picker). If `/model` shows "Requires usage
credits" on the Fable or Mythos row, those seats bill usage credits; Claude Code documents its
consent prompt for the main session, not for subagents.

### Global rules

The engineering rule set the skills assume ships inside the plugin in two parts:

- [`rules/CLAUDE.global.md`](plugins/asic-tools/rules/CLAUDE.global.md) — the core (precedence,
  philosophy, decision ladder, surgical changes, git, MCP lanes, self-test). Installed as
  `~/.claude/CLAUDE.md` and loaded every session.
- [`rules/scoped/`](plugins/asic-tools/rules/scoped/) — Python, Pydantic, configuration, testing,
  structure and DB/API rules with canonical code examples. Installed as
  `~/.claude/rules/asic-*.md`; each loads only when Claude touches a matching file.

On any machine with the plugin installed:

```
/asic-tools:sync-rules
```

installs or updates all of them — diff-aware, never silently clobbering local edits, and never
touching a `~/.claude/rules/` file that is not named `asic-*.md`. Dev mode: `install.sh` does the
same copies and reports retired files as STALE. Always copies, not symlinks — the desktop app
skips symlinks in some loaders.

The same command then offers to merge
[plugins/asic-tools/rules/settings.fragment.json](plugins/asic-tools/rules/settings.fragment.json)
into `~/.claude/settings.json`: `attribution` with empty `commit`/`pr` and `sessionUrl: false`, a
`permissions.deny` rule for `git push`, and `autoMode.hard_deny` rules (keeping `"$defaults"`) for
push, attribution, and hook bypass. It shows a diff first, only adds, reports conflicts instead of
overwriting them, and keeps `settings.json.sync-rules.bak`. Auto mode reads `autoMode` only from
user settings, never from a repo's `.claude/` files.

### Enforcement hooks

`asic-tools` ships `hooks/hooks.json`, registered automatically when the plugin is enabled. It binds
the standing git rules that prose alone could not:

| Rule | Behaviour |
|---|---|
| AI attribution in a commit message or PR (incl. `Claude-Session:` trailer) | **denied** — no escape. AI is a tool, not an author. |
| `git push`, in any form (`bash -c`, `/usr/bin/git`, `$(…)`, quoted) | **denied** — the user pushes and merges via GitKraken. |
| Hook bypass (`--no-verify`, `commit -n`, `core.hooksPath`, `SKIP=`, `HUSKY=`) | **denied** — the hooks run ruff before every commit. |
| `git reset --hard`, `git clean -f`, `git branch -D` | **asks** — work that cannot be recovered. |
| `git commit` on `main` / `master` | **asks** — you approve or reject in a permission dialog. |
| A push or commit the guard cannot classify (`G=git; $G push`, quoted options) | **asks**. |

`ask` is the escape hatch by design: an env var or flag file would be forgeable by the agent, a
permission dialog is not. Hooks load at session start — **restart Claude Code after updating the
plugin**, then confirm with `/hooks` (source: `Plugin`).

These hooks bind the agent, not you: a commit you make yourself in a terminal is untouched.

The guard fails closed: an unreadable payload, a crash, or a timeout blocks the command. Text
inspection cannot see through git aliases or script files, which is why `/asic-tools:sync-rules`
also installs a `permissions.deny` rule and auto-mode `hard_deny` rules — three layers, each
covering the others' blind spots. Narrow allow rules such as `Bash(git reset *)` in a repo's
`.claude/settings.local.json` run before the auto-mode classifier; remove them if you do not want
those commands unreviewed.

---

## asicdash

Config + usage dashboard for Claude Code (formerly **agentdash**). Audits visible and
invisible agent-harness config across global and project scope, and charts Claude usage from
local session transcripts. One deterministic CLI; the Claude skill is a thin
wrapper around it.

That includes the config that costs money: each agent's `model` and `effort`, a flag on any agent
that declares **neither** — an absent `model:` is not a default, it is whatever the session happens
to be — and the model/effort each routing role in a plugin workflow sets.

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
| plugin `workflows/*.js` | plugin | routing block: model + effort per role |
| `~/.claude/projects/**/*.jsonl` session transcripts | usage (HTML report) | per-day token/session aggregation |

### Known gaps, on purpose

- **`output-styles/`, `monitors/`, `.lsp.json`, `bin/`** — zero occurrences across every
  installed plugin, so a scanner for them would be code that never fires and a maintenance
  cost across Claude Code layout changes. Revisit when one actually appears.

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
   MVP scope, and an explicit **Not Doing** list. A **builder check** runs first: a fresh
   subagent reads the draft as its builder; only questions that change what gets built reach
   you, in one round, and every call the skill made on its own is listed as its call

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
4. **Interview** — open design decisions become batched questions, recommendation first,
   including which build choices you want to own and the test seams the tests will target
5. **Draft** — canonical 12-section format (objective → problem → architecture decisions →
   verified context → blueprint → per-file instructions → tests → smoke → acceptance →
   doc updates → anti-patterns → future work)
6. **Builder check + self-audit** — a fresh subagent reads the draft as its implementer and
   lists what it would still have to guess (one follow-up question round at most); then paths
   re-verified, commands copy-pasteable, git constraints embedded

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
Workflow that fans out a tier-sized set of distinct-lens reviewers — six on logic (requirements coverage,
architecture soundness, over-build, edge-cases & verifiability, silent-failure including swallowed errors,
type-design) and three on style/convention drift against
the real target repo (naming, structure, error/test/docstring conventions; these three run only
when the PRP cites repo files) — adjudicates their
findings to drop false positives, applies the blocker/major fixes to the PRP in place, and
re-reviews up to the tier's round cap. It appends a `## Review Log` to the PRP and surfaces any residual
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
[workflows/review_workflow.js](plugins/asic-tools/workflows/review_workflow.js)
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

Before flipping the status, close-out runs a **converge pass**: a fresh-context reviewer reads
the PRP's goal, desired behaviour and acceptance checklist against the branch diff and reports
requirements the code misses, since passing gates only prove what the PRP chose to test.
Confirmed gaps are fixed and re-checked once; a gap that survives stops the run. Every run keeps
a small state file (`PRPs/.work/prp-implement-active.md`) with its base commit and current task,
and a plugin hook prints it back after context compaction, so a long run keeps
its place. Passed checks are reported with their actual output, the run notifies you at the plan
pause and at the end, and the final report offers an optional `/code-review ultra` before merge.

Close-out also regenerates the PRP registry. `prp_status.py` holds the status standard in its
module docstring — five values, who writes each, and the exit codes that lint them — and renders
`PRPs/STATUS.md` from the corpus, deriving the in-flight badge from live git refs so no PRP stores
a state git already answers. **`STATUS.md` is generated: regenerate it, never hand-edit it.** The
script refuses to overwrite a `STATUS.md` that lacks its generated banner, so a hand-written file
is never clobbered.

```bash
# <asic.dev> = your clone of this repo
python3 <asic.dev>/plugins/asic-tools/skills/prp-implement/scripts/prp_status.py PRPs --write
```

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

---

## okf

Adopts Google's [Open Knowledge Format](https://github.com/GoogleCloudPlatform/open-knowledge-format)
v0.2 as the standard shape for knowledge bundles and LLM-wikis — a directory of markdown with YAML
frontmatter, one required field (`type`), two reserved filenames (`index.md`, `log.md`). The spec is
vendored offline and pinned (Apache-2.0, see `NOTICE.md`), so the skill needs no network and adds no
dependency: stdlib `python3` only. v0.1 bundles still validate, with migration warnings for the two
fields v0.2 superseded.

The value is the **validator**. OKF §11 conformance is mechanically checkable, and nothing else
checks it.

| Exit | Meaning |
|---|---|
| `0` | Conformant (recommendation warnings may print; `--quiet` silences them) |
| `1` | Non-conformant — each violation named by path |
| `2` | Usage/IO error |
| `3` | Indeterminate — a frontmatter line the parser cannot place (quoted or merge key, tab indentation); nested maps and lists are parsed. A validator limitation, not a verdict. |

It deliberately **never fails** a bundle for missing optional fields, unknown `type` values, unknown
extra keys, broken cross-links, or a missing `index.md` — §11 forbids consumers from rejecting on
those, so over-strictness would be a defect. It equally never *silently accepts*: a line it cannot
read surfaces as exit `3`, never a skip, and a missing or empty `type` behind such a line is still
exit `1`. `type: ""`, `type: null`, and `type: ~` are an empty `type`, not content.

### Usage

```bash
# <asic.dev> = your clone of this repo
S=<asic.dev>/plugins/asic-tools/skills/okf
python3 "$S/scripts/validate_okf.py" ./my-bundle
python3 "$S/scripts/okf_index.py" ./my-bundle/tables --write
```

`okf_index.py --write` preserves frontmatter already present, so regenerating the bundle-root
`index.md` never destroys its `okf_version` declaration (§12).

## License

[MIT](LICENSE) © Captain ASIC
