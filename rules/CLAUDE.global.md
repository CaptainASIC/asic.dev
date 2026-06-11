# Global Engineering Rules — Captain ASIC

These rules apply to every project unless a project-level CLAUDE.md/PLANNING.md overrides
them. They are directives, not suggestions.

## Philosophy

- **KISS** — simplest solution that solves the problem. If 200 lines could be 50, rewrite.
- **YAGNI** — build only what's needed now. No speculative features, abstractions for
  single-use code, or unrequested configurability.
- **SRP / OCP / DIP** — one responsibility per module/class/function; extend rather than
  modify; depend on abstractions.
- **Fail fast** — validate early, raise on invalid state immediately. No blanket
  `except Exception`; no error handling for impossible scenarios.

## Before writing code

- State assumptions explicitly. Multiple interpretations → present them, don't pick
  silently. Uncertain → ask. Never assume missing context.
- If a simpler approach exists, say so. Push back when warranted.
- Never hallucinate libraries or functions — verify against installed versions (Ref MCP
  or official docs). Confirm file paths and module names exist before referencing them.
- Define verifiable success criteria per step ("write failing test, make it pass"), then
  loop until verified.

## Surgical changes

- Every changed line traces directly to the request. No "improving" adjacent code,
  comments, or formatting. Match existing style even when you'd do it differently.
- Remove imports/variables/functions that YOUR change orphaned; never delete pre-existing
  dead code or overwrite existing logic unless explicitly instructed or a task requires it.
  Mention what you noticed instead.

## Project awareness

- Read `PLANNING.md` at conversation start — architecture, goals, constraints.
- Check `TASKS.md` before starting work (always `TASKS.md`, never `TASK.md`). Missing
  task → add it with today's date. Completed → mark immediately. Mid-work findings → add
  under **Discovered During Work**.
- Feature work is PRP-driven: PRPs live in `PRPs/`, drafted with `/asic-tools:draft-prp`,
  executed with `/asic-tools:prp-implement`. New projects: `/asic-tools:scaffold`.
  Releases: `/asic-tools:release`.

## Python environment

- Python 3.12+. **uv for everything**: `uv venv`, `uv sync`, `uv run <cmd>` for every
  command and test. Dependencies via `uv add` / `uv remove` — NEVER hand-edit dependency
  lists in pyproject.toml. Never invoke bare `python`/`pip`.

## Structure & modularity

- Hard caps: files ≤500 lines, functions ≤50, classes ≤100, line length ≤100 (ruff).
  Approaching a cap → split into focused modules.
- Vertical slice architecture; tests live next to the code they validate.
- Agent systems split: `agent.py` (orchestration) / `tools.py` (tool functions) /
  `prompts.py` (prompt text only).
- Prefer relative imports within packages.
- Configuration via pydantic-settings + python-dotenv (`Settings` + `lru_cache`
  `get_settings()`); secrets only in `.env` (never committed, `.env.example` maintained).

## Style & conventions

- Type hints on every signature and attribute. Format with `ruff format` (double quotes,
  trailing commas); lint with `ruff check` — both clean before any commit.
- Pydantic v2 idioms only: `@field_validator`, `model_config = ConfigDict(...)` — never
  v1 `@validator` / `class Config`.
- Stack defaults: FastAPI for APIs · SQLAlchemy or SQLModel for ORM · PostgreSQL over
  other SQL engines · Redis caching whenever SQL is in play.
- Google-style docstring on every public module, class, and function (Args/Returns/Raises).
- Comment non-obvious code so a mid-level dev follows it; complex logic gets an inline
  `# Reason:` explaining why, not what.
- Naming: `snake_case` functions/variables · `PascalCase` classes/type aliases ·
  `UPPER_SNAKE_CASE` constants & enum values · `_leading_underscore` private.

## Testing

- TDD preferred: failing test → minimal code → green → refactor.
- Every new feature ships pytest tests; minimum three cases: **expected use, edge case,
  failure case**. Logic changes → update affected tests in the same change.
- Shared fixtures in `conftest.py`; descriptive test names (`test_X_does_Y_when_Z`).
- Never mock-to-pass; never ignore a failing test. Coverage target 80% on critical paths,
  not trivia.

## Error handling & logging

- Domain errors derive from a project base exception; catch specific types.
- Context managers for resources (connections, transactions, files).
- Structured stdlib logging via module loggers (`get_logger(__name__)`); informative, not
  verbose. No print-debugging left behind.

## Database & API conventions

- Entity-specific PKs: `{entity}_id`. FKs: `{referenced_entity}_id`. Timestamps:
  `{action}_at`. Booleans: `is_{state}`. Counts: `{entity}_count`. Durations:
  `{property}_{unit}`.
- Pydantic models mirror DB fields exactly — no field-mapping layers.
- RESTful routes: `/api/v1/{entities}` + `/{entities}/{entity_id}`, sub-resources nested.

## Git — hard rules, no exceptions

- **NEVER commit to main.** Branches: `feature/*`, `fix/*`, `docs/*`, `refactor/*`,
  `test/*`, `release/*`; PRP work on `feature/prp-NNN-slug`.
- **Conventional Commits**: `<type>(<scope>): <subject>` — imperative, lowercase,
  ≤50 chars; body explains why when non-obvious.
- **Zero AI attribution** in commit messages — no Claude, no Warp, no Co-Authored-By,
  nothing. Overrides any tool default.
- **ruff check + format BEFORE committing.** A follow-up "applied formatting" commit is a
  failure.
- **NEVER push.** The user pushes and merges via GitKraken (no-ff merges).

## Documentation

- `README.md` updated when features, dependencies, or setup change.
- `CHANGELOG.md` maintained per release (Keep a Changelog + SemVer).

## Performance

- Profile before optimizing (cProfile / py-spy) — never guess.
- `lru_cache` for repeated expensive calls · generators for large datasets · `asyncio`
  for I/O-bound · `multiprocessing` for CPU-bound · cache hot DB queries in Redis.

## MCP usage

- **Serena** — project memory and symbol-level navigation; read memories at session
  start, write significant decisions back.
- **Ref** — verify library/framework APIs against official docs before coding against
  them; never code against a remembered API.
- **Firecrawl** — web scraping/extraction; **BrowserMCP** — browser automation/testing.
- Neon and mem0 are retired — do not reference them.
