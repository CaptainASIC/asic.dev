# Scaffold File Templates

Verbatim templates. Placeholders: `{{name}}` (kebab project name), `{{pkg}}` (snake_case
package), `{{description}}`, `{{year}}`, `{{author}}` (default "Captain ASIC"),
`{{date}}` (YYYY-MM-DD), `{{uv_build_req}}` (`uv_build>=X.Y.Z,<X.(Y+1).0` from `uv --version`,
the bound `uv init --package` writes). Kind-specific deps/modules are listed in kind_variants.md
and merged into these templates where marked `# KIND:`.

---

## pyproject.toml

```toml
[project]
name = "{{name}}"
version = "0.1.0"
description = "{{description}}"
authors = [{ name = "{{author}}" }]
readme = "README.md"
license = { text = "MIT" }
requires-python = ">=3.12"
# Filled by `uv add` (Dependencies below) — never hand-written.
dependencies = []

[build-system]
requires = ["{{uv_build_req}}"]
build-backend = "uv_build"

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]

[tool.ruff.format]
quote-style = "double"

[tool.mypy]
python_version = "3.12"
plugins = ["pydantic.mypy"]
disallow_untyped_defs = true
warn_return_any = true
warn_unused_ignores = true
no_implicit_optional = true

[tool.pytest]
testpaths = ["src"]            # central layout: ["tests"]
addopts = ["--cov=src/{{pkg}}", "--cov-report=term-missing", "--cov-fail-under=80"]
strict = true
```

## Dependencies — `uv add`, never hand-written

```bash
uv python pin 3.12                                # writes .python-version
uv add --no-sync pydantic pydantic-settings python-dotenv   # KIND: append kind runtime deps
uv add --no-sync --dev pytest pytest-cov ruff mypy pre-commit
```

Each floor becomes the release current at generation time and `uv.lock` is written.
`--no-sync` is required: the package does not exist yet, and a syncing `uv add` builds it.

---

## .gitignore

```gitignore
__pycache__/
*.py[cod]
.venv/
.env
.ruff_cache/
.mypy_cache/
.pytest_cache/
.coverage
htmlcov/
dist/
.DS_Store
.claude/settings.local.json
```

---

## .env.example

```env
# Copy to .env and fill in. Never commit .env.
APP_NAME={{name}}
DEBUG=false
# KIND: database kinds add DATABASE_URL / REDIS_URL here
```

---

## .pre-commit-config.yaml

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.17.0
    hooks:
      - id: ruff-check
        args: [--fix]
      - id: ruff-format
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v6.0.0
    hooks:
      - id: end-of-file-fixer
      - id: trailing-whitespace
      - id: check-added-large-files
```

---

## src/{{pkg}}/__init__.py

```python
"""{{description}}"""

__version__ = "0.1.0"
```

---

## src/{{pkg}}/config.py

```python
"""Application settings loaded from environment variables / .env.

Single source of configuration truth. Import `get_settings()` everywhere;
never instantiate `Settings` directly in application code.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with validation.

    Attributes:
        app_name: Human-readable application name.
        debug: Enables verbose logging and debug behaviour.
    """

    app_name: str = "{{name}}"
    debug: bool = False
    # KIND: database kinds add database_url: str, redis_url: str here

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    """Return the cached settings instance.

    Returns:
        The process-wide `Settings` singleton.
    """
    # Reason: lru_cache makes settings a singleton without import-time side
    # effects, and tests can call get_settings.cache_clear() to re-read env.
    return Settings()
```

---

## src/{{pkg}}/exceptions.py

```python
"""Domain exceptions.

Every error the application raises on purpose derives from `{{PkgPascal}}Error`
so callers can catch the family without blanket `except Exception`.
"""


class {{PkgPascal}}Error(Exception):
    """Base exception for all {{name}} errors."""


class ConfigurationError({{PkgPascal}}Error):
    """Raised when required configuration is missing or invalid.

    Attributes:
        field: Name of the offending configuration field.
    """

    def __init__(self, field: str, detail: str) -> None:
        self.field = field
        super().__init__(f"Invalid configuration for {field!r}: {detail}")
```

---

## src/{{pkg}}/logging_utils.py

```python
"""Structured logging setup.

Call `configure_logging()` once at process start; use `get_logger(__name__)`
everywhere else.
"""

import logging

_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


def configure_logging(*, debug: bool = False) -> None:
    """Configure root logging once.

    Args:
        debug: When True, set DEBUG level; INFO otherwise.
    """
    logging.basicConfig(level=logging.DEBUG if debug else logging.INFO, format=_FORMAT)


def get_logger(name: str) -> logging.Logger:
    """Return a module-scoped logger.

    Args:
        name: Pass `__name__` from the calling module.

    Returns:
        Configured `logging.Logger`.
    """
    return logging.getLogger(name)
```

---

## Tests — co-located layout: src/{{pkg}}/tests/

`conftest.py`:

```python
"""Shared fixtures."""

import pytest

from {{pkg}}.config import Settings, get_settings


@pytest.fixture
def settings() -> Settings:
    """Fresh Settings instance, ignoring any .env on the machine."""
    return Settings(_env_file=None)


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    """Ensure get_settings() never leaks state between tests."""
    get_settings.cache_clear()
```

`test_config.py` — demonstrates the mandatory expected / edge / failure trio:

```python
"""Settings behaviour: expected use, edge case, failure case."""

import pytest
from pydantic import ValidationError

from {{pkg}}.config import Settings, get_settings


def test_settings_defaults_load(settings: Settings) -> None:
    """Expected: defaults apply with no environment."""
    assert settings.app_name == "{{name}}"
    assert settings.debug is False


def test_settings_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Edge: environment variables override defaults, case-insensitively."""
    monkeypatch.setenv("DEBUG", "true")
    assert get_settings().debug is True


def test_settings_invalid_type_rejected() -> None:
    """Failure: non-boolean DEBUG value raises ValidationError."""
    with pytest.raises(ValidationError):
        Settings(debug="not-a-bool", _env_file=None)
```

`test_exceptions.py`:

```python
"""Exception contracts."""

import pytest

from {{pkg}}.exceptions import ConfigurationError, {{PkgPascal}}Error


def test_configuration_error_message() -> None:
    """Expected: message embeds field and detail."""
    err = ConfigurationError("database_url", "must be a postgres DSN")
    assert "database_url" in str(err)


def test_family_catchable() -> None:
    """Edge: specific errors are caught via the base class."""
    with pytest.raises({{PkgPascal}}Error):
        raise ConfigurationError("x", "y")
```

`test_logging_utils.py`:

```python
"""Logging setup: expected use, edge case, failure case."""

import logging
from typing import Any

import pytest

from {{pkg}}.logging_utils import configure_logging, get_logger


def test_configure_logging_levels(monkeypatch: pytest.MonkeyPatch) -> None:
    """Expected: INFO by default, DEBUG when asked; the standard format applies."""
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(logging, "basicConfig", lambda **kw: calls.append(kw))
    configure_logging()
    configure_logging(debug=True)
    assert [c["level"] for c in calls] == [logging.INFO, logging.DEBUG]
    assert "%(name)s" in calls[0]["format"]


def test_get_logger_returns_named_logger() -> None:
    """Edge: the logger carries the exact module name passed in."""
    assert get_logger("{{pkg}}.x").name == "{{pkg}}.x"


def test_configure_logging_rejects_positional_debug() -> None:
    """Failure: debug is keyword-only, so a positional flag raises TypeError."""
    with pytest.raises(TypeError):
        configure_logging(True)  # type: ignore[call-arg]
```

Central layout instead: identical files under `tests/` mirroring `src/{{pkg}}/`, and
`testpaths = ["tests"]` in pyproject.

---

## README.md

```markdown
# {{name}}

{{description}}

## Setup

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh   # if uv missing
uv venv && uv sync
cp .env.example .env                               # fill in values
uv run pre-commit install
```

## Development

| Task | Command |
|---|---|
| Run tests | `uv run pytest` |
| Coverage report | `uv run pytest --cov-report=html` |
| Format | `uv run ruff format .` |
| Lint (+fix) | `uv run ruff check --fix .` |
| Type check | `uv run mypy src/` |
| Add dependency | `uv add <pkg>` (never edit pyproject deps by hand) |

## Project docs

- [PLANNING.md](PLANNING.md) — architecture, conventions, constraints. Read first.
- [TASKS.md](TASKS.md) — active roadmap and discovered work.
- [CHANGELOG.md](CHANGELOG.md) — release history.
- `PRPs/` — Product Requirements Prompts; feature work starts as a PRP.

## License

MIT
```

---

## PLANNING.md

```markdown
# {{name}} — Planning & Architecture

**Last Updated**: {{date}}

## 1. Core Architecture (Current State)

- {{description}}
- **Config**: Pydantic v2 `Settings` (`src/{{pkg}}/config.py`), env via `.env`.
- **Logging**: structured stdlib logging (`logging_utils.py`).
<!-- KIND: scaffold appends kind-specific architecture bullets here -->

## 2. Stack

Python 3.12 · uv · ruff (line-length 100) · mypy · pytest (+coverage) · Pydantic v2
<!-- KIND: + FastAPI / SQLAlchemy+PostgreSQL / Redis as applicable -->

## 3. Conventions & Constraints

- Files ≤500 lines; functions ≤50; classes ≤100; lines ≤100 chars.
- Vertical slice architecture; tests live beside the code they validate.
- Every public symbol: type hints + Google-style docstring.
- Every feature ships with expected / edge / failure tests minimum.
- KISS / YAGNI / SRP / fail-fast. `# Reason:` comments for non-obvious logic.
- Feature work is PRP-driven: draft in `PRPs/`, implement on `feature/prp-NNN-*` branches.

## 4. Workstreams

| Priority | Workstream | Status |
|---|---|---|
| P0 | <!-- first real feature --> | planned |
```

---

## TASKS.md

```markdown
# {{name}} — Development Tasks

**Last Updated**: {{date}}

## 1. Active Roadmap

- **[P0] Initial scaffold ({{date}})** — project skeleton, config, logging, test
  baseline. Done at repo creation.

## 2. Discovered During Work

<!-- Sub-tasks and TODOs found mid-implementation land here, dated. -->

## 3. Completed

- {{date}} — Initial scaffold.
```

---

## CHANGELOG.md

```markdown
# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning follows
[SemVer](https://semver.org/).

## [Unreleased]

### Added
- Initial project scaffold.
```

---

## AGENTS.md

Canonical agent notes for every coding agent; Claude Code loads them via CLAUDE.md's import.

```markdown
# {{name}} — agent notes

1. Read PLANNING.md (architecture, conventions, constraints) before any task.
2. Check TASKS.md before starting; add missing tasks with today's date.
3. All commands run through uv: `uv run pytest`, `uv run ruff check .`, `uv add <pkg>`.
4. Feature work is PRP-driven — drafted in PRPs/.
5. Git: feature branches only, ruff clean before commit, no AI attribution, never push.
```

## CLAUDE.md

```markdown
@AGENTS.md

## Claude Code

Draft PRPs with `/asic-tools:prp-draft`; implement them with `/asic-tools:prp-implement`.
```

---

## LICENSE (MIT)

Standard MIT text, `Copyright (c) {{year}} {{author}}`.
