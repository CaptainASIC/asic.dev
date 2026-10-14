# Hardening after the fix

Read this once the root-cause fix holds. Both techniques make the same bug harder to bring back.

## Validate at each layer

A single check at the point of the fix can be bypassed by another code path, a refactor or a mock.
Trace the path the bad value took and decide, layer by layer, whether a guard belongs there:

1. **Entry point** — reject obviously invalid input at the boundary (empty, missing, wrong type).
   The global rules require this at every trust boundary.
2. **Business logic** — check that the value makes sense for this operation.
3. **Environment guard** — refuse dangerous operations in the wrong context, e.g. writing outside
   a temp directory while tests run.
4. **Diagnostics** — a `DEBUG`-level line from the module logger before the risky operation. This
   is permanent logging and follows the project's logging conventions (in Python, the scoped
   Python rules' module-logger pattern). It is not a tagged
   Phase 5 probe; those are all removed in Phase 7.

Add a guard only where a real path can reach it. Fail fast and raise a specific exception; never
catch broadly to make the symptom go away.

## Wait for conditions, not durations

Fixed sleeps in tests guess at timing. They pass on a fast machine and fail under load or in CI.
Poll for the condition you actually need, with a timeout:

```python
import time
from collections.abc import Callable


def wait_for[T](
    condition: Callable[[], T | None],
    description: str,
    timeout_s: float = 5.0,
    interval_s: float = 0.01,
) -> T:
    """Poll ``condition`` until it returns a truthy value.

    Args:
        condition: Zero-argument callable, re-evaluated on every poll.
        description: What is awaited; used in the timeout message.
        timeout_s: Seconds to wait before giving up.
        interval_s: Seconds between polls.

    Returns:
        The first truthy value ``condition`` returned.

    Raises:
        TimeoutError: If no truthy value arrives within ``timeout_s``.
    """
    deadline = time.monotonic() + timeout_s
    while True:
        result = condition()
        if result:
            return result
        if time.monotonic() >= deadline:
            raise TimeoutError(f"timed out after {timeout_s}s waiting for {description}")
        time.sleep(interval_s)
```

Common mistakes: no timeout (the loop hangs forever), polling every millisecond (wastes CPU), and
reading state once before the loop instead of inside `condition` (the value goes stale). For
`asyncio` code the same shape applies, with `await asyncio.sleep(interval_s)`.

A fixed delay is correct only when the timing itself is under test (debounce, throttle). Wait for
the triggering condition first, then for the known interval, with a comment saying why.
