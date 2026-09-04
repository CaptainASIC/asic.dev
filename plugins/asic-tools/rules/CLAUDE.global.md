# Global Engineering Rules — Captain ASIC

These rules apply to every project unless a project-level CLAUDE.md/PLANNING.md overrides
them. They are directives, not suggestions. Code examples below are canonical patterns —
match them.

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

## Python environment — uv for everything

Python 3.12+. All commands run inside the project venv via uv. Never invoke bare
`python`/`pip`; never hand-edit dependency lists in pyproject.toml.

```bash
uv venv                      # create virtual environment
uv sync                      # install/update from pyproject + lock
uv add requests              # add runtime dependency (updates pyproject correctly)
uv add --dev pytest ruff mypy
uv remove requests
uv run python script.py      # run anything in the environment
uv run pytest
uv python install 3.12       # pin interpreter if needed
```

Standard development commands:

```bash
uv run pytest                          # all tests
uv run pytest src/pkg/tests/test_x.py -v
uv run pytest --cov=src --cov-report=html
uv run ruff format .                   # format
uv run ruff check --fix .              # lint + autofix
uv run mypy src/                       # type check
uv run pre-commit run --all-files
```

## Structure & modularity

- Hard caps: **files ≤500 lines, functions ≤50, classes ≤100, line length ≤100** (ruff,
  configured in pyproject.toml). Approaching a cap → refactor into focused modules.
- Vertical slice architecture — features organized end-to-end, tests living beside the
  code they validate:

```
src/project/
    __init__.py
    main.py
    conftest.py
    tests/
        test_main.py
    database/
        connection.py
        models.py
        tests/
            test_connection.py
            test_models.py
    features/
        user_management/
            handlers.py
            validators.py
            tests/
                test_handlers.py
                test_validators.py
```

- Agent systems split by responsibility: `agent.py` (main agent definition and execution),
  `tools.py` (tool functions), `prompts.py` (prompt text only).
- Prefer relative imports within packages.
- Environment variables via python-dotenv + pydantic-settings; secrets only in `.env`
  (never committed; keep `.env.example` current).

## Style & conventions

- PEP 8 with: line length 100, double quotes, trailing commas in multi-line structures.
  Format with `ruff format`; lint with `ruff check` — both clean before any commit.
- **Type hints on every function signature and class attribute.**
- Naming:
  - `snake_case` — variables, functions
  - `PascalCase` — classes, type aliases
  - `UPPER_SNAKE_CASE` — constants, enum values
  - `_leading_underscore` — private attributes/methods
- Comment non-obvious code so a mid-level developer can follow it. Complex logic gets an
  inline `# Reason:` comment explaining why, not what.
- **Google-style docstring on every public function, class, and module:**

```python
def calculate_discount(
    price: Decimal,
    discount_percent: float,
    min_amount: Decimal = Decimal("0.01"),
) -> Decimal:
    """Calculate the discounted price for a product.

    Args:
        price: Original price of the product.
        discount_percent: Discount percentage (0-100).
        min_amount: Minimum allowed final price.

    Returns:
        Final price after applying the discount.

    Raises:
        ValueError: If discount_percent is not between 0 and 100.
        ValueError: If the final price would fall below min_amount.

    Example:
        >>> calculate_discount(Decimal("100"), 20)
        Decimal('80.00')
    """
```

## Data models — Pydantic v2 only

Use Pydantic v2 idioms exclusively: `@field_validator`, `model_config = ConfigDict(...)`.
Never v1 `@validator` / `class Config`. Validate at the boundary; strict where it matters.

```python
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProductBase(BaseModel):
    """Base product model with common fields."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    price: Decimal = Field(..., gt=0, decimal_places=2)
    category: str
    tags: list[str] = []

    @field_validator("price")
    @classmethod
    def validate_price(cls, v: Decimal) -> Decimal:
        if v > Decimal("1000000"):
            raise ValueError("Price cannot exceed 1,000,000")
        return v


class ProductCreate(ProductBase):
    """Model for creating new products."""


class ProductUpdate(BaseModel):
    """Model for updates — all fields optional."""

    name: str | None = Field(None, min_length=1, max_length=255)
    price: Decimal | None = Field(None, gt=0, decimal_places=2)


class Product(ProductBase):
    """Complete product model with database fields."""

    product_id: int
    created_at: datetime
    updated_at: datetime
    is_active: bool = True

    model_config = ConfigDict(from_attributes=True)
```

## Configuration

Settings via pydantic-settings, accessed through a cached singleton — never instantiate
`Settings` directly in application code:

```python
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with validation."""

    app_name: str = "MyApp"
    debug: bool = False
    database_url: str
    redis_url: str = "redis://localhost:6379"
    max_connections: int = 100

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    """Return the cached settings instance."""
    return Settings()
```

## Testing

- **TDD preferred**: write the failing test → watch it fail → minimal code to pass →
  refactor with tests green → repeat.
- **Every new feature gets pytest tests** (functions, classes, routes). After changing any
  logic, update affected tests in the same change.
- Minimum three cases per feature — **expected use, edge case, failure case**:

```python
def test_user_can_update_email_when_valid(sample_user):
    """Expected: valid input succeeds."""
    sample_user.update_email("new@example.com")
    assert sample_user.email == "new@example.com"


def test_user_update_email_strips_whitespace(sample_user):
    """Edge: boundary/unusual input handled."""
    sample_user.update_email("  new@example.com  ")
    assert sample_user.email == "new@example.com"


def test_user_update_email_fails_with_invalid_format(sample_user):
    """Failure: invalid input rejected with a clear error."""
    with pytest.raises(ValidationError) as exc_info:
        sample_user.update_email("not-an-email")
    assert "Invalid email format" in str(exc_info.value)
```

- Shared fixtures in `conftest.py`; descriptive test names that state behavior and
  condition. Unit tests mock external dependencies; integration tests verify component
  interaction; e2e tests cover full workflows.
- Never mock-to-pass; never ignore a failing test — read the error, fix the root cause.
- Mock data only in tests — never in dev or prod environments. Dev and prod use real data
  sources and integrations; no fake payloads or hardcoded samples standing in for live behavior.
- Coverage target 80%+, prioritizing critical paths and complex logic over trivia.

## Error handling & logging

- Create custom exception families for domain errors; catch specific types:

```python
class PaymentError(Exception):
    """Base exception for payment-related errors."""


class InsufficientFundsError(PaymentError):
    """Raised when an account has insufficient funds."""

    def __init__(self, required: Decimal, available: Decimal) -> None:
        self.required = required
        self.available = available
        super().__init__(f"Insufficient funds: required {required}, available {available}")
```

- Context managers for resource management (connections, transactions, files) —
  commit/rollback/close handled in one place.
- Structured stdlib logging via module loggers:

```python
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)
```

  Log at the right level (DEBUG trace, INFO lifecycle, WARNING degraded, ERROR/exception
  failures). Informative but not verbose; no print-debugging left behind.

## Database & API conventions

- **Entity-specific primary keys**, never bare `id`:

```sql
sessions.session_id   UUID PRIMARY KEY
leads.lead_id         UUID PRIMARY KEY
messages.message_id   UUID PRIMARY KEY
```

- Field naming: FKs `{referenced_entity}_id` · timestamps `{action}_at` (`created_at`,
  `expires_at`) · booleans `is_{state}` (`is_active`) · counts `{entity}_count` ·
  durations `{property}_{unit}` (`timeout_minutes`).
- Pydantic models mirror database fields exactly — no field-mapping layers; repositories
  derive table/PK names from the entity by convention.
- Stack: FastAPI for APIs · SQLAlchemy or SQLModel for ORM · **PostgreSQL preferred** over
  other SQL engines · **Redis caching whenever SQL is in play**.
- RESTful routes with consistent parameter naming:

```python
router = APIRouter(prefix="/api/v1/leads", tags=["leads"])

@router.get("/{lead_id}")              # GET    /api/v1/leads/{lead_id}
@router.put("/{lead_id}")              # PUT    /api/v1/leads/{lead_id}
@router.delete("/{lead_id}")           # DELETE /api/v1/leads/{lead_id}
@router.get("/{lead_id}/messages")     # sub-resource
```

- API endpoints carry `summary`/`description` and parameter docs — FastAPI's OpenAPI
  output is part of the documentation surface.

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

## Performance

- **Profile before optimizing** (cProfile, py-spy) — never optimize on a guess; target the
  measured bottleneck.
- `functools.lru_cache` for expensive repeated computations · generators for large
  datasets (never load what you can stream) · `asyncio` for I/O-bound concurrency ·
  `multiprocessing` for CPU-bound parallelism · cache hot SQL queries in Redis.

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
