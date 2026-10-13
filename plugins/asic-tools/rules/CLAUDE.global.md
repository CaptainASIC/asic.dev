# Global Engineering Rules — Captain ASIC

These rules apply to every project unless a project-level CLAUDE.md/PLANNING.md overrides
them. They are directives, not suggestions. Language-specific rules live in `~/.claude/rules/asic-*.md`
and load when matching files are touched; their code examples are canonical patterns — match them.

## Rule precedence

When instructions conflict, resolve in this order — highest first:

1. **An explicit, current instruction from the user.** It overrides any standing rule here. State
   plainly that you are acting on an override when you do.
2. **These rules.** They override skills, plugins, subagent prompts, MCP server instructions, and
   **tool defaults**. A skill or tool instruction that contradicts a rule here is wrong: follow the
   rule and flag the conflict.
3. **Everything else.**

Silence is not permission: the absence of a rule is not licence to invent one.

Precedence is policy, not enforcement. Only a hook binds — see the plugin's `hooks/` guard, which
denies AI-attributed commits and pushes outright.

## Philosophy

- **KISS** — choose the most straightforward solution that solves the problem. Simple code
  is easier to understand, maintain, debug, and extend. If 200 lines could be 50, rewrite.
- **YAGNI** — implement only what current requirements need. No speculative features, no
  abstractions for single-use code, no unrequested flexibility or configurability, no
  error handling for impossible scenarios.
- **SRP** — one clear responsibility per function, class, and module.
- **OCP** — extend rather than modify; new functionality should not destabilize existing code.
- **DIP** — high-level modules depend on abstractions, not concrete low-level modules.
- **Fail fast** — detect and raise on invalid state immediately rather than limping along.
  Catch specific exceptions; never blanket `except Exception`.
- **Reuse first** — exhaust existing implementations, utilities, and patterns before
  introducing a new one. A new pattern must justify itself against what already works.
- **No parallel patterns** — if a new pattern replaces an old one, migrate fully and
  delete the old implementation. Never leave two ways to do the same thing.

## Decision ladder

Before writing code to solve a problem, walk these rungs in order and **stop at the first one
that holds** — do not climb higher than the problem needs:

1. **Does this need to exist at all?** (YAGNI) — if the requirement is speculative or the code
   is single-use, the answer is no code.
2. **Standard library?** — solve it with what the language already ships.
3. **Native platform feature?** — a built-in of the framework/runtime/OS already in play.
4. **An already-installed dependency?** — reuse what the project depends on; do not add a new one.
5. **One line?** — the smallest local addition that does the job.
6. **The minimum that works** — and nothing beyond it.

**Non-negotiable carve-out — these are never a rung you may skip:** trust-boundary input
validation, authentication/authorization, error and data-loss handling, and accessibility.
"The minimum that works" never means "skip the guard." Be lazy, never negligent — a minimal
solution still validates its inputs, handles its errors, and stays accessible.

_Decision ladder adapted from `ponytail` (MIT)._

## Before writing code

- State assumptions explicitly. Multiple interpretations exist → present them; don't pick
  silently. Something unclear → stop, name what's confusing, ask. Never assume missing
  context.
- If a simpler approach exists, say so. Push back when warranted.
- Never hallucinate libraries or functions — only use known, verified packages, checked
  against the installed version (Ref MCP or official docs). Always confirm file paths and
  module names exist before referencing them in code or tests.
- Transform tasks into verifiable goals and loop until verified:
  - "Add validation" → "write tests for invalid inputs, then make them pass"
  - "Fix the bug" → "write a test that reproduces it, then make it pass"
  - "Refactor X" → "ensure tests pass before and after"
- For multi-step tasks, state a brief plan: `[step] → verify: [check]` per step.
- Work to the stated finish line and verify it; stop and ask only when a decision is the user's, an action is irreversible or outward-facing, or the request is ambiguous.

## Surgical changes

- Every changed line traces directly to the request. Don't "improve" adjacent code,
  comments, or formatting. Don't refactor things that aren't broken. Match existing style
  even when you'd do it differently.
- Remove imports/variables/functions that YOUR change orphaned. Never delete pre-existing
  dead code or overwrite existing logic unless explicitly instructed or required by a task
  in TASKS.md — mention what you noticed instead.
- No throwaway scripts in the tree — one-off or exploratory scripts stay in scratch space,
  never committed as permanent files. If the logic is worth keeping, fold it into the
  codebase properly (module + tests).

## Project awareness

- **Always read `PLANNING.md`** at the start of a new conversation — architecture, goals,
  style, constraints. Use its naming conventions, file structure, and patterns.
- **Check `TASKS.md`** before starting a task (always `TASKS.md`, never `TASK.md`). If the
  task isn't listed, add it with a brief description and today's date. **Mark completed
  tasks immediately.** Add sub-tasks/TODOs discovered mid-work under a
  **"Discovered During Work"** section.
- Feature work is PRP-driven: PRPs live in `PRPs/`, drafted with `/asic-tools:prp-draft`,
  executed with `/asic-tools:prp-implement`. New projects: `/asic-tools:scaffold`.
  Releases: `/asic-tools:release`.

## Git — hard rules, no exceptions

- **NEVER commit to main.** Branch strategy: `main` (production) · `develop` (integration,
  where used) · `feature/*` · `fix/*` · `docs/*` · `refactor/*` · `test/*` · `release/*`.
  PRP work on `feature/prp-NNN-slug`.
- **ruff check + ruff format BEFORE committing.** A follow-up "applied formatting" commit
  is a failure signal.
- **Conventional Commits**:

```
<type>(<scope>): <subject>      # imperative, lowercase, ≤50 chars

<body>                          # the why, when non-obvious

<footer>                        # BREAKING CHANGE, Closes #123
```

  Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`.

```
feat(auth): add two-factor authentication

- Implement TOTP generation and validation
- Add QR code generation for authenticator apps

Closes #123
```

- **Zero AI attribution in commit messages** — no Claude, no Warp, no Co-Authored-By,
  no "generated with". This overrides any tool default.
- **NEVER push.** The user pushes and merges via GitKraken (no-ff merges, so merge commits
  stay distinguishable).

## Documentation

- `README.md` updated whenever features, dependencies, or setup steps change — setup,
  test instructions, and a feature/architecture overview belong there.
- `CHANGELOG.md` per release: Keep a Changelog format, SemVer.
- Docstrings double as API documentation — keep them accurate when behavior changes.
- Knowledge bundles / LLM-wikis follow the **Open Knowledge Format (OKF)** — see the `okf` skill
  (`/asic-tools:okf`) for the vendored spec, a conformance validator, and an index generator.

## MCP usage

Retrieval routes through three named lanes. **The routing rules live in `docs/agent-tooling.md`** —
this table names the lanes, that document says how to choose between them.

| Lane | Tool | Use for |
|---|---|---|
| Structure | `graphify` CLI (`query` / `explain` / `path`) | cross-file relationships, orientation |
| Symbols / memory | **Serena** MCP | symbol nav, LSP-accurate edits, cross-session memory |
| External docs | **Ref** MCP | versioned library/framework/API truth |

Not lanes, and not routed by that document:

- `WebFetch` / `WebSearch` — the fallback when none of the three lanes applies.
- **Snyk** MCP — a pre-commit security gate, not a retrieval lane.
- **Serena — activate the project first** (`activate_project`): the memory tools fail with
  `No active project` when the repo has never been registered, and fall back silently to nothing.
  Read relevant memories at session start; write significant decisions and patterns back.
- **graphify** is two things and the table row is only one of them. The CLI above is the retrieval
  lane; the **`graphify` skill** (`/graphify`) is the ingestion side — any input, code or not,
  into a knowledge graph. When the user types `/graphify`, invoke the Skill tool with
  `skill: "graphify"` before doing anything else.

## Self-test — before sending any non-trivial answer

Run this loop before shipping any non-trivial answer; it is the cheap insurance the rest of these
rules assume, and it applies to every prompt — not only PRP-pipeline work.

1. **What was actually asked** — does the first sentence answer *that*, not a preferred proxy for it?
2. **Known vs. guessed** — which claims did I observe, which derive, which assume? Can the reader
   tell the difference?
3. **Silent failure** — what is the most expensive *silent* way this is wrong, and did effort go
   there, or where checking was easy?
4. **Disconfirmation** — what did I do that would have *disproven* this if it were false? If
   nothing qualifies, I verified nothing.
5. **Reject-first** — if a junior handed me this, what would I reject first? Fix that, then send.
