---
name: asicdash
description: Config + usage dashboard for Claude Code + Warp (formerly agentdash). Audits skills, agents, commands, rules, hooks, plugins, memory files, MCP servers, and Warp workflows across global and project scope — including invisible config (hook registrations, plugin-injected skills, always-loaded context cost) — and charts Claude Code usage from local session transcripts (GitHub-style heatmap, per-day modals, Terminal/Desktop launch split). Use when the user asks "what skills/agents/hooks do I have", "show my config", "config dashboard", "what's loaded into my context", "audit my claude or warp setup", "show my claude usage", or invokes /asicdash or /agentdash.
---

# asicdash

Deterministic scanner. Do not assemble the inventory yourself — run the script and relay.

## Run

```bash
python3 "${CLAUDE_PLUGIN_ROOT:-$HOME/.claude}/skills/asicdash/asicdash.py"
```

(`CLAUDE_PLUGIN_ROOT` is set when installed as a plugin; the fallback covers the symlinked
personal-skill dev install — both roots contain `skills/asicdash/`.)

Default mode writes a self-contained themed HTML report (collapsible sections, Claude usage
heatmap with per-day modals, ASIC light/dark) to the system temp dir and opens it in the
browser. Flags:
- `--cli --no-color` — aligned table on stdout; use when the user wants the answer in chat
  instead of the browser
- `--project PATH` — inspect a different repo (default: cwd)
- `--json` — machine-readable; use when you need to post-process, not for display
- `--html PATH` — override the report path; `--no-open` to skip the browser

Only use `--cli` when the user explicitly asks for the table/chat-only output.

## Present

1. HTML mode (default): state the written path and that it opened in the browser.
   CLI mode: script output verbatim in a fenced code block. Do not reformat, reorder,
   or summarize the table.
2. Below it, at most 3 bullets flagging anomalies only: broken/shadowed/unregistered items,
   surprising hook registrations (commands firing on many events), or heavy always-loaded
   context. If the SUMMARY section shows no problems, say so in one line.

No editorializing beyond anomalies. If the script errors, show the error verbatim.
