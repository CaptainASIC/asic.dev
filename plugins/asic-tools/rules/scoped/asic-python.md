---
paths:
  - "**/*.py"
  - "**/*.pyi"
  - "**/pyproject.toml"
---
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

## Performance

- **Profile before optimizing** (cProfile, py-spy) — never optimize on a guess; target the
  measured bottleneck.
- `functools.lru_cache` for expensive repeated computations · generators for large
  datasets (never load what you can stream) · `asyncio` for I/O-bound concurrency ·
  `multiprocessing` for CPU-bound parallelism · cache hot SQL queries in Redis.
