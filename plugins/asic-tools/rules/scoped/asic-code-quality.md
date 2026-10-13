---
paths:
  - "**/*.{py,pyi,ts,tsx,js,jsx,mjs,cjs,swift,rs,go,java,kt,rb,c,h,cc,cpp,hpp,cs}"
---
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
