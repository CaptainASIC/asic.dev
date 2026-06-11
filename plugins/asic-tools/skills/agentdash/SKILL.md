---
name: agentdash
description: Config dashboard for Claude Code + Warp. Audits skills, agents, commands, rules, hooks, plugins, memory files, MCP servers, and Warp workflows across global and project scope — including invisible config (hook registrations, plugin-injected skills, always-loaded context cost). Use when the user asks "what skills/agents/hooks do I have", "show my config", "config dashboard", "what's loaded into my context", "audit my claude or warp setup", or invokes /agentdash.
---

# agentdash

Deterministic scanner. Do not assemble the inventory yourself — run the script and relay.

## Run

```bash
python3 "${CLAUDE_PLUGIN_ROOT:-$HOME/.claude}/skills/agentdash/agentdash.py" --no-color
```

(`CLAUDE_PLUGIN_ROOT` is set when installed as a plugin; the fallback covers the symlinked
personal-skill dev install — both roots contain `skills/agentdash/`.)

Flags:
- `--project PATH` — inspect a different repo (default: cwd)
- `--json` — machine-readable; use when you need to post-process, not for display
- `--html [PATH]` — self-contained themed HTML report (collapsible sections, ASIC light/dark),
  written to the system temp dir unless PATH given, opened in the browser unless `--no-open`

When the user asks for the visual/HTML/browser dashboard, run with `--html` instead of the table.

## Present

1. Table mode: script output verbatim in a fenced code block. Do not reformat, reorder, or summarize the table. HTML mode: state the written path and that it opened in the browser.
2. Below it, at most 3 bullets flagging anomalies only: broken/shadowed/unregistered items, surprising hook registrations (commands firing on many events), or heavy always-loaded context. If the SUMMARY section shows no problems, say so in one line.

No editorializing beyond anomalies. If the script errors, show the error verbatim.
