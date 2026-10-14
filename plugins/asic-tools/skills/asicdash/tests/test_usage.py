"""usage collector + usage_html fragment tests (PRP-027). Transcripts are written into tmp_path.

Timestamps are 12:00Z so a call's local date is the same in every UTC-11..UTC+11 zone; no test
builds a day key from a near-midnight time.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from usage import collect_usage, hit_pct, preview

NOW = datetime(2026, 10, 13, 12, tzinfo=UTC).astimezone()
PROJ = "-Users-x-Repositories-demo"


def ts(minute: int, day: int = 13) -> str:
    return f"2026-10-{day:02d}T12:{minute:02d}:00Z"


def write(root: Path, rel: str, lines: list[dict]) -> Path:
    path = root / PROJ / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    # Reason: Claude Code writes compact JSON; the nested-file pre-filter depends on it.
    path.write_text(
        "\n".join(json.dumps(x, separators=(",", ":")) for x in lines) + "\n", encoding="utf-8"
    )
    return path


def asst(minute: int, rid: str, out: int, inp: int = 0, cr: int = 0, cc: int = 0, **kw) -> dict:
    usage = {
        "output_tokens": out,
        "input_tokens": inp,
        "cache_read_input_tokens": cr,
        "cache_creation_input_tokens": cc,
    }
    return {
        "type": "assistant",
        "timestamp": ts(minute, kw.pop("day", 13)),
        "requestId": rid,
        "message": {"id": f"m-{rid}", "usage": usage},
        **kw,
    }


def user(minute: int, text: object, uid: str, **kw) -> dict:
    return {
        "type": "user",
        "timestamp": ts(minute),
        "uuid": uid,
        "message": {"content": text},
        **kw,
    }


def test_duplicate_request_lines_count_once(tmp_path: Path) -> None:
    write(tmp_path, "s1.jsonl", [asst(1, "r1", 50), asst(1, "r1", 50), asst(1, "r1", 50)])
    assert collect_usage(tmp_path, NOW)["totals"]["out"] == 50


def test_highest_output_line_wins(tmp_path: Path) -> None:
    write(tmp_path, "s1.jsonl", [asst(1, "r1", 10), asst(2, "r1", 70)])
    assert collect_usage(tmp_path, NOW)["totals"]["out"] == 70


def test_subagent_and_workflow_transcripts_roll_up(tmp_path: Path) -> None:
    write(tmp_path, "s1.jsonl", [{**asst(1, "r1", 5), "entrypoint": "claude-desktop"}])
    write(tmp_path, "s1/subagents/agent-a.jsonl", [asst(2, "r2", 7)])
    write(tmp_path, "s1/subagents/workflows/wf_x/agent-b.jsonl", [asst(3, "r3", 11)])
    u = collect_usage(tmp_path, NOW)
    assert u["totals"]["sessions"] == 1 and u["totals"]["out"] == 23
    day = u["days"][NOW.date().isoformat()]
    assert set(day) == {"desktop"} and day["desktop"]["out"] == 23


def test_global_dedupe_across_files(tmp_path: Path) -> None:
    write(tmp_path, "s1.jsonl", [asst(1, "shared", 40)])
    write(tmp_path, "s1/subagents/agent-a.jsonl", [asst(2, "shared", 40)])
    assert collect_usage(tmp_path, NOW)["totals"]["out"] == 40


def test_prompt_attribution_includes_subagent_calls(tmp_path: Path) -> None:
    write(tmp_path, "s1.jsonl", [user(0, "build the thing", "u1"), asst(1, "r1", 30)])
    write(tmp_path, "s1/subagents/agent-a.jsonl", [asst(2, "r2", 20)])
    top = collect_usage(tmp_path, NOW)["totals"]["top_prompts"]
    assert len(top) == 1 and top[0]["text"] == "build the thing" and top[0]["total"] == 50


def test_nested_calls_anchor_at_file_start(tmp_path: Path) -> None:
    write(tmp_path, "s1.jsonl", [user(0, "P1", "u1"), user(5, "P2", "u2")])
    write(tmp_path, "s1/subagents/agent-a.jsonl", [asst(1, "r1", 5), asst(10, "r2", 70)])
    top = {p["text"]: p for p in collect_usage(tmp_path, NOW)["totals"]["top_prompts"]}
    assert top["P1"]["total"] == 75 and "P2" not in top


def test_non_prompts_ignored(tmp_path: Path) -> None:
    write(
        tmp_path,
        "s1.jsonl",
        [
            user(0, [{"type": "tool_result", "content": "x"}], "u1"),
            user(1, "meta text", "u2", isMeta=True),
            user(2, "<task-notification>done</task-notification>", "u3"),
            user(3, "side", "u4", isSidechain=True),
            asst(4, "r1", 9),
        ],
    )
    assert collect_usage(tmp_path, NOW)["totals"]["top_prompts"] == []


def test_window_cutoff(tmp_path: Path) -> None:
    old = {**asst(1, "old", 99), "timestamp": "2025-09-08T12:00:00Z"}  # 400 days before NOW
    write(tmp_path, "s1.jsonl", [old, asst(2, "new", 3)])
    assert collect_usage(tmp_path, NOW)["totals"]["out"] == 3


def test_cache_fields_and_hit(tmp_path: Path) -> None:
    write(tmp_path, "s1.jsonl", [asst(1, "r1", 1, inp=10, cc=30, cr=60)])
    totals = collect_usage(tmp_path, NOW)["totals"]
    assert totals["periods"]["all"]["c_read"] == 60 and totals["c_create"] == 30
    assert hit_pct(totals["periods"]["all"]) == 60


def test_preview_masks_tokens_tags_and_slash() -> None:
    secret = (
        "sk_" + "live_" + "Ab3dE5gH7jK9mN1pQ3sT5vX7z"
    )  # Reason: built at runtime, never a literal
    out = preview(f"<x>use key {secret} now</x>")
    assert "[…]" in out and "sk_live" not in out and "<x>" not in out
    assert preview("<command-name>/prp-draft</command-name>") == "/prp-draft"
    long = " ".join(["word"] * 75)  # 374 chars, no token run
    cut = preview(long)
    assert len(cut) == 100 and cut.endswith("…")
