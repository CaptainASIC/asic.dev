# Scaffold Kind Variants

Additions merged into the base templates per project kind. Everything here obeys the same
bar: typed, docstringed, tested (expected/edge/failure), green under ruff + mypy + pytest.

---

## api — FastAPI service

**Runtime deps (`uv add`):** `fastapi`, `uvicorn[standard]`; **dev deps (`uv add --dev`):** `httpx` (TestClient needs it)
**With database (`uv add`):** `sqlalchemy` (or `sqlmodel`), `asyncpg`, `redis`; add
`DATABASE_URL=postgresql+asyncpg://...` and `REDIS_URL=redis://localhost:6379` to
`.env.example` and `Settings`.

**Extra modules:**

`src/{{pkg}}/main.py` — app factory:

```python
"""FastAPI application entry point."""

from fastapi import FastAPI

from {{pkg}} import __version__
from {{pkg}}.api.v1.routes import router as v1_router
from {{pkg}}.config import get_settings
from {{pkg}}.logging_utils import configure_logging


def create_app() -> FastAPI:
    """Build the FastAPI application.

    Returns:
        Configured FastAPI instance with v1 routes mounted.
    """
    settings = get_settings()
    configure_logging(debug=settings.debug)
    app = FastAPI(title=settings.app_name, version=__version__)
    app.include_router(v1_router, prefix="/api/v1")

    @app.get("/health", tags=["meta"])
    async def health() -> dict[str, str]:
        """Liveness probe; must stay dependency-free."""
        return {"status": "healthy", "version": __version__}

    return app


app = create_app()
```

`src/{{pkg}}/api/v1/routes.py` — RESTful skeleton following the naming standards
(`/api/v1/{entities}/{entity_id}`, entity-specific IDs):

```python
"""v1 API routes. One router per resource as the API grows."""

from fastapi import APIRouter

router = APIRouter()

# Resources follow REST + entity-id naming:
#   GET    /api/v1/items                 list
#   POST   /api/v1/items                 create
#   GET    /api/v1/items/{item_id}       fetch
#   PUT    /api/v1/items/{item_id}       update
#   DELETE /api/v1/items/{item_id}       delete
```

**Tests:** `test_main.py` using `fastapi.testclient.TestClient` — expected
(`/health` 200 + payload shape), edge (unknown route 404), failure (wrong method 405).

**README/PLANNING additions:** run command `uv run uvicorn {{pkg}}.main:app --reload`,
architecture bullet "FastAPI + auto-generated OpenAPI docs at /docs".

**Database naming reminders (when DB selected)** — emit into PLANNING.md §3:
entity-specific PKs `{entity}_id`; FKs `{referenced_entity}_id`; timestamps `{action}_at`;
booleans `is_{state}`; counts `{entity}_count`; models mirror DB fields exactly.

---

## agent — LLM agent system

**Runtime deps:** none imposed — framework choice (PydanticAI, Anthropic SDK, …) is a
per-project decision; scaffold stays framework-agnostic with clearly marked seams.

**Extra modules — the canonical agent split (one concern per file):**

`src/{{pkg}}/agent.py`:

```python
"""Main agent definition and execution logic."""

from dataclasses import dataclass

from {{pkg}}.config import get_settings
from {{pkg}}.logging_utils import get_logger
from {{pkg}}.prompts import SYSTEM_PROMPT
from {{pkg}}.tools import TOOLS

logger = get_logger(__name__)


@dataclass
class AgentResponse:
    """Result of one agent turn.

    Attributes:
        text: Final assistant text.
        tool_calls: Names of tools invoked this turn.
    """

    text: str
    tool_calls: list[str]


class Agent:
    """{{description}}

    Wire your LLM client of choice into `run()`; prompts live in prompts.py,
    tool functions in tools.py — keep this file orchestration-only.
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self.system_prompt = SYSTEM_PROMPT
        self.tools = TOOLS

    def run(self, user_input: str) -> AgentResponse:
        """Execute one turn.

        Args:
            user_input: Raw user message.

        Returns:
            AgentResponse with text and any tool calls made.

        Raises:
            NotImplementedError: until an LLM backend is wired in.
        """
        raise NotImplementedError("Wire an LLM backend here (see PLANNING.md P0).")
```

`src/{{pkg}}/tools.py`:

```python
"""Tool functions exposed to the agent. Pure, typed, individually testable."""

from collections.abc import Callable

TOOLS: dict[str, Callable[..., object]] = {}


def tool(fn: Callable[..., object]) -> Callable[..., object]:
    """Register a function as an agent tool.

    Args:
        fn: The tool implementation; name becomes the tool name.

    Returns:
        The function, unchanged.
    """
    TOOLS[fn.__name__] = fn
    return fn
```

`src/{{pkg}}/prompts.py`:

```python
"""System prompts. Prompt text only — no logic."""

SYSTEM_PROMPT = """You are {{name}}. {{description}}"""
```

**Tests:** registry behaviour (expected: `@tool` registers; edge: two tools coexist;
failure: `Agent.run` raises `NotImplementedError` until wired).

---

## cli — command-line tool

**Runtime deps:** none (argparse, stdlib).

`src/{{pkg}}/main.py`:

```python
"""CLI entry point."""

import argparse

from {{pkg}} import __version__
from {{pkg}}.logging_utils import configure_logging, get_logger

logger = get_logger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """Construct the argument parser.

    Returns:
        Configured ArgumentParser.
    """
    parser = argparse.ArgumentParser(prog="{{name}}", description="{{description}}")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--debug", action="store_true", help="verbose logging")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the CLI.

    Args:
        argv: Argument vector; None uses sys.argv.

    Returns:
        Process exit code.
    """
    args = build_parser().parse_args(argv)
    configure_logging(debug=args.debug)
    logger.info("{{name}} starting")
    return 0
```

**pyproject addition** — installed as a console command only because the base template declares
`[build-system]`; Phase 3 runs `uv run {{name}} --version` to prove it:

```toml
[project.scripts]
{{name}} = "{{pkg}}.main:main"
```

**Tests:** expected (`main([])` returns 0), edge (`--debug` accepted), failure
(unknown flag → `SystemExit` with code 2).

---

## library

No extra modules — base skeleton is the library. Drop `main.py`; public API lives in
`__init__.py` re-exports. Add `py.typed` marker file so consumers get type information.
