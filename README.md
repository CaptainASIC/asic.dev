# asic.dev

Agent-harness tooling for Claude Code and Warp, shipped as a Claude Code plugin marketplace
with Warp counterparts where they make sense.

| Tool | What it does |
|---|---|
| [agentdash](#agentdash) | Audit visible and invisible agent config across global + project scope |
| [draft-prp](#draft-prp) | Research-first generator for Product Requirements Prompts |
| [scaffold](#scaffold) | Standards-enforced Python project bootstrap — verified runnable, not a paper template |
| [release](#release) | Multi-location version bump + changelog, derived from Conventional Commits |

## Install

### As a plugin (recommended)

In Claude Code:

```
/plugin marketplace add CaptainASIC/asic.dev
/plugin install asic-tools@asic-dev
```

Skills are namespaced: `/asic-tools:agentdash`, `/asic-tools:draft-prp`,
`/asic-tools:scaffold`, `/asic-tools:release`. Plugin skills show up in the desktop app's
customize page; filesystem personal skills currently do not
([claude-code#66998](https://github.com/anthropics/claude-code/issues/66998)).

### Dev mode (this repo checked out)

```bash
./install.sh
```

Symlinks each skill under `plugins/asic-tools/skills/` into `~/.claude/skills/` — bare
`/agentdash` and `/draft-prp` names, and edits in the repo are live without reinstalling.
Don't combine both installs: you'd get duplicate skill registrations.

### Warp

`install.sh` copies `warp/agentdash.yaml` to `~/.warp/workflows/` (Warp watches real files,
so a copy — rerun after editing). `warp/draft-prp.md` is pasted into a Warp Drive prompt
manually (Drive is cloud-stored).

---

## agentdash

Audit visible and invisible agent-harness config for Claude Code and Warp, across global and
project scope. One deterministic CLI; Claude skill and Warp workflow are thin wrappers around it.

### Why

A plain inventory of skills and agents is `ls` with extra steps. The value is in what you cannot
see by listing directories:

- **Hook registrations** — commands firing invisibly on session events (flattened from
  `settings.json`, deduplicated, executable-existence checked)
- **Plugin-injected surface** — skills, agents, commands, and hooks shipped by installed plugins
- **Always-loaded context cost** — token estimates for `CLAUDE.md`, rules, memory, `WARP.md`,
  `AGENTS.md` loaded into every session
- **Rot and shadowing** — hook scripts on disk that nothing references, project entries shadowing
  global ones, broken frontmatter, missing executables

### Usage

```bash
# plugin install path (marketplace clone); dev-mode symlink path is ~/.claude/skills/agentdash/
DASH=~/.claude/plugins/marketplaces/asic-dev/plugins/asic-tools/skills/agentdash/agentdash.py
python3 "$DASH"                              # table, current project
python3 "$DASH" --json                       # machine-readable
python3 "$DASH" --project ~/Repositories/Airi
```

In Claude Code: ask "show my config dashboard" (triggers the `agentdash` skill).
In Warp: run the `agentdash` workflow.

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
| `~/.warp/workflows/`, `.warp/workflows/`, `WARP.md`, `AGENTS.md` | global + project | YAML top-level parse |

### Known gaps, on purpose

- **Warp Drive** (rules, workflows, profiles stored in Drive): cloud-synced SQLite with an
  undocumented schema. Not parsed; reported as `n/a` instead of pretending coverage.
- **Claude routines / scheduled cloud agents**: stored server-side, no local file. Reported as
  `n/a`; list with `/schedule` in Claude Code.
- Token counts are `bytes / 4` estimates, not tokenizer output.

### Maintenance

Claude Code's config layout shifts between versions. All scanned locations live in one table:
`known_paths()` in [agentdash.py](plugins/asic-tools/skills/agentdash/agentdash.py). Fix
breakage there.

---

## draft-prp

Turns a feature discussion (mid-chat "let's make this a PRP", or a pasted design summary) into
a **Product Requirements Prompt** — a self-contained, implementation-ready instruction document
that a coding agent (Claude Code or Warp) executes with no other context.

### Why

A PRP is only as good as its specifics. The failure mode of template-driven generation is
confident garbage: invented line numbers, guessed API signatures, gotchas recalled from
training data instead of read from source. An implementing agent trusts those and burns hours.
So this skill is ~20% template, ~80% enforced process:

1. **Context sweep** — README, PLANNING, TASKS, Serena memories, prior PRPs, tooling/lockfiles
2. **Codebase research** — reads every file the feature touches; library claims verified
   against installed versions; evidence required for every CRITICAL/GOTCHA
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

In Claude Code: `/draft-prp`, or just say "turn this into a PRP" mid-conversation.
In Warp: invoke the `draft-prp` Drive prompt (see [warp/draft-prp.md](warp/draft-prp.md)).

Layout: [SKILL.md](plugins/asic-tools/skills/draft-prp/SKILL.md) is the workflow driver;
[prp_template.md](plugins/asic-tools/skills/draft-prp/references/prp_template.md) and
[style_guide.md](plugins/asic-tools/skills/draft-prp/references/style_guide.md) hold the
section skeleton and the standing engineering rules (structure caps, stack defaults, DB
naming, test minimums, git constraints) loaded only when drafting.

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

In Claude Code: `/asic-tools:scaffold`. In Warp: the `scaffold` Drive prompt
([warp/scaffold.md](warp/scaffold.md)). Templates:
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

In Claude Code: `/asic-tools:release`. In Warp: the `release` Drive prompt
([warp/release.md](warp/release.md)).
