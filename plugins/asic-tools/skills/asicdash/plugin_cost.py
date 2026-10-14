"""Harness-measured plugin context cost via `claude plugin details <name>` (PRP-027).

`claude plugin details` prints human-readable text only (2.1.296: no --json), and a cold call
costs ~3 s; seven in parallel measured 16.9 s. So successful results are cached per installed
version in the system temp dir, and a warm asicdash run makes no subprocess call. The parser
fails loud: an unrecognised format yields reason "unparsed", never a guessed number.

Imports nothing from this skill. Stdlib only.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

CACHE_PATH = Path(tempfile.gettempdir()) / "asicdash-plugin-cost-v1.json"
TIMEOUT_S = 30
MAX_WORKERS = 4
ALWAYS_ON = re.compile(r"^\s*Always-on:\s+~([\d,]+)\s+tok", re.MULTILINE)
ROW = re.compile(r"^\s{2}(\S+)\s+~([\d.,]+k?)\s+~([\d.,]+k?)\s*$", re.MULTILINE)

Cost = dict  # {"always_on": int, "components": [{"component", "always_on", "on_invoke"}]}
Result = tuple[Cost | None, str]


def _num(text: str) -> int:
    """'~2,427' -> 2427, '2.6k' -> 2600, '620' -> 620 (the leading ~ is already stripped)."""
    t = text.replace(",", "")
    return round(float(t[:-1]) * 1000) if t.endswith("k") else int(float(t))


def parse_details(text: str) -> Cost | None:
    """Parse `claude plugin details` output, or None when no Always-on line is present.

    Args:
        text: The command's stdout.

    Returns:
        Always-on total plus per-component rows from the "Per-component" table.
    """
    m = ALWAYS_ON.search(text)
    if not m:
        return None
    _, _, table = text.partition("Per-component")
    rows = [
        {"component": c, "always_on": _num(a), "on_invoke": _num(i)}
        for c, a, i in ROW.findall(table)
    ]
    return {"always_on": _num(m.group(1)), "components": rows}


def run_details(full_name: str) -> Result:
    """Run `claude plugin details <full_name>` once and parse it."""
    exe = shutil.which("claude")
    if not exe:
        return None, "claude CLI not on PATH"
    try:
        proc = subprocess.run(
            [exe, "plugin", "details", full_name],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_S,
            # Reason: a nonzero exit (unknown plugin) is a reported reason, not an exception.
            check=False,
        )
    except subprocess.TimeoutExpired:
        return None, f"timed out after {TIMEOUT_S}s"
    except OSError as exc:
        return None, f"could not run claude: {exc.strerror or exc}"
    parsed = parse_details(proc.stdout)
    if parsed:
        return parsed, ""
    if "not found" in proc.stdout + proc.stderr:
        return None, "not found by claude plugin details"
    return None, "unparsed (claude plugin details format changed?)"


def _load(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _save(path: Path, cache: dict) -> None:
    tmp = path.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(cache), encoding="utf-8")
        tmp.replace(path)
    except OSError:
        return  # Reason: the cache is an optimisation; the report is correct without it.


def plugin_costs(
    plugins: dict[str, str],
    runner: Callable[[str], Result] = run_details,
    cache_path: Path = CACHE_PATH,
) -> dict[str, Result]:
    """Cost per plugin, from the cache when its key matches, else measured (in parallel).

    Args:
        plugins: {full_name: cache_key}; the key changes whenever the installed copy changes.
        runner: Measures one plugin; injected by tests.
        cache_path: Cache file; injected by tests.

    Returns:
        {full_name: (cost or None, reason)}. Only successes are cached.
    """
    cache = _load(cache_path)
    results: dict[str, Result] = {}
    todo: list[str] = []
    for name, key in plugins.items():
        hit = cache.get(name)
        if isinstance(hit, dict) and hit.get("key") == key and isinstance(hit.get("cost"), dict):
            results[name] = (hit["cost"], "")
        else:
            todo.append(name)
    if todo:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            for name, (cost, reason) in zip(todo, pool.map(runner, todo), strict=True):
                results[name] = (cost, reason)
                if cost:
                    cache[name] = {"key": plugins[name], "cost": cost}
        _save(cache_path, cache)
    return results
