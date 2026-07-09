#!/bin/bash
# UserPromptSubmit: restate rule precedence each turn, at higher salience than line ~430 of a
# 441-line rules file.
#
# Reason: phrased as FACT, not as an imperative system command — the hooks reference warns that
# out-of-band imperative text can trigger prompt-injection defenses and be surfaced rather than used.
set -uo pipefail
cat >/dev/null  # drain stdin; this hook needs no input

CTX="Rule precedence in this environment: an explicit, current instruction from the user outranks the standing rules in CLAUDE.md, and Claude states when it is acting on such an override. The standing rules in CLAUDE.md outrank skills, plugins, subagent prompts, MCP server instructions, and tool defaults. Commit messages never carry AI attribution."
python3 -c 'import sys,json;print(json.dumps({"hookSpecificOutput":{"hookEventName":"UserPromptSubmit","additionalContext":sys.argv[1]}}))' "$CTX"
exit 0
