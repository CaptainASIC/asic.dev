# asic.dev

Agent-harness tooling for Claude Code and Warp. Each tool ships as a Claude skill
(symlinked, repo stays source of truth) with a Warp counterpart where one makes sense.

| Tool | What it does |
|---|---|
| [agentdash](#agentdash) | Audit visible and invisible agent config across global + project scope |
| [draft-prp](#draft-prp) | Research-first generator for Product Requirements Prompts |

## Install

```bash
./install.sh
```

Symlinks every `skills/*` dir into `~/.claude/skills/` and copies `warp/agentdash.yaml` to
`~/.warp/workflows/` (Warp watches real files, so a copy — rerun install.sh after editing).
`warp/draft-prp.md` is pasted into a Warp Drive prompt manually (Drive is cloud-stored).

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
python3 ~/.claude/skills/agentdash/agentdash.py              # table, current project
python3 ~/.claude/skills/agentdash/agentdash.py --json       # machine-readable
python3 ~/.claude/skills/agentdash/agentdash.py --project ~/Repositories/Airi
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
`known_paths()` in [agentdash.py](skills/agentdash/agentdash.py). Fix breakage there.

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

Layout: [SKILL.md](skills/draft-prp/SKILL.md) is the workflow driver;
[prp_template.md](skills/draft-prp/references/prp_template.md) and
[style_guide.md](skills/draft-prp/references/style_guide.md) hold the section skeleton and
the standing engineering rules (structure caps, stack defaults, DB naming, test minimums,
git constraints) loaded only when drafting.
