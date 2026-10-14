"""plugin_cost tests (PRP-027): the details parser on canned output, and the version-keyed cache.

The runner is always injected: no test runs `claude`. SAMPLE keeps the 2.1.296 layout (inventory,
Always-on line, Per-component table) trimmed to four component rows.
"""

from __future__ import annotations

from pathlib import Path

import plugin_cost
import pytest
from plugin_cost import _num, parse_details, plugin_costs, run_details

SAMPLE = """\
Captain ASIC's Dev Toolbox (asic-tools) 1.0.0
  Source: asic-tools@asic-dev

Component inventory
  Skills (10)  asicdash, idea-refine, improve-repo, okf, prp-draft, prp-implement
  Hooks (2)  PreToolUse, UserPromptSubmit  (harness-only — no model context cost)

Projected token cost
  Always-on:   ~2,427 tok   added to every session

Per-component (rounded)
  component           always-on  on-invoke
  idea-refine              ~210      ~2.6k
  improve-repo             ~270      ~5.6k
  asicdash                 ~240       ~600
  prp-implement            ~180      ~9.3k

  On-invoke cost is paid each time a skill or agent fires.
"""

COST = {"always_on": 100, "components": []}


def test_parse_details_sample() -> None:
    cost = parse_details(SAMPLE)
    assert cost is not None and cost["always_on"] == 2427
    rows = {r["component"]: r for r in cost["components"]}
    assert rows["prp-implement"]["on_invoke"] == 9300
    assert rows["improve-repo"]["on_invoke"] == 5600
    assert rows["asicdash"]["on_invoke"] == 600 and len(rows) == 4


def test_parse_number_forms() -> None:
    assert _num("1,270") == 1270
    assert _num("2.6k") == 2600
    assert _num("620") == 620


def test_parse_returns_none_on_other_text() -> None:
    assert parse_details('Plugin "x" not found. Run `claude plugin list`.') is None
    assert parse_details("") is None


def _counting(result: tuple) -> tuple[list[str], object]:
    calls: list[str] = []

    def runner(name: str) -> tuple:
        calls.append(name)
        return result

    return calls, runner


def test_cache_hit_skips_runner(tmp_path: Path) -> None:
    cache = tmp_path / "c.json"
    calls, runner = _counting((COST, ""))
    first = plugin_costs({"p@m": "k1"}, runner=runner, cache_path=cache)
    second = plugin_costs({"p@m": "k1"}, runner=runner, cache_path=cache)
    assert calls == ["p@m"]
    assert first["p@m"] == second["p@m"] == (COST, "")


def test_key_change_remeasures(tmp_path: Path) -> None:
    cache = tmp_path / "c.json"
    calls, runner = _counting((COST, ""))
    plugin_costs({"p@m": "k1"}, runner=runner, cache_path=cache)
    plugin_costs({"p@m": "k2"}, runner=runner, cache_path=cache)
    assert calls == ["p@m", "p@m"]


def test_failures_not_cached(tmp_path: Path) -> None:
    cache = tmp_path / "c.json"
    calls, runner = _counting((None, "timed out after 30s"))
    plugin_costs({"p@m": "k"}, runner=runner, cache_path=cache)
    out = plugin_costs({"p@m": "k"}, runner=runner, cache_path=cache)
    assert calls == ["p@m", "p@m"] and out["p@m"] == (None, "timed out after 30s")
    assert "p@m" not in (cache.read_text() if cache.exists() else "")


def test_corrupt_cache_ignored(tmp_path: Path) -> None:
    cache = tmp_path / "c.json"
    cache.write_text("not json")
    calls, runner = _counting((COST, ""))
    assert plugin_costs({"p@m": "k"}, runner=runner, cache_path=cache)["p@m"] == (COST, "")
    assert calls == ["p@m"]


def test_run_details_without_claude(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(plugin_cost.shutil, "which", lambda name: None)
    assert run_details("p@m") == (None, "claude CLI not on PATH")
