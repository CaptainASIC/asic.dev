#!/bin/bash
# PreToolUse(Bash) guard for Captain ASIC's hard git rules.
#
# Reason: these rules are stated absolutely in CLAUDE.global.md but were previously enforced only by
# prose, which the Bash tool's own "Co-Authored-By: Claude" default actively contradicts.
#
# CRITICAL: always exit 0. JSON on stdout is the ONLY decision channel; Claude Code ignores JSON on
# any non-zero exit, and exit 1 is a NON-blocking error that lets the command through.
set -uo pipefail

# Parse and build JSON with python3 — it ships with every OS this plugin reaches (macOS and Linux
# both include it; macOS ships NO jq), so the enforcement runtime carries no dependency a user might
# lack. This mirrors the in-house precedent graphify-grep-guard.sh (Reuse-first): no jq prerequisite,
# no degraded fallback branch.
input=$(cat)

tool_name=$(printf '%s' "$input" | python3 -c 'import sys,json;print(json.load(sys.stdin).get("tool_name",""),end="")' 2>/dev/null)
[ "$tool_name" = "Bash" ] || exit 0

command=$(printf '%s' "$input" | python3 -c 'import sys,json;print(json.load(sys.stdin).get("tool_input",{}).get("command",""),end="")' 2>/dev/null)
cwd=$(printf '%s' "$input" | python3 -c 'import sys,json;print(json.load(sys.stdin).get("cwd",""),end="")' 2>/dev/null)
[ -n "$command" ] || exit 0

# Fast bail: nothing here concerns non-git commands.
printf '%s' "$command" | grep -qE '(^|[;&|[:space:]])git([[:space:]]|$)' || exit 0

emit() {  # emit <deny|ask> <reason>
  python3 -c 'import sys,json;print(json.dumps({"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":sys.argv[1],"permissionDecisionReason":sys.argv[2]}}))' "$1" "$2"
  exit 0
}

# The git subcommand is the FIRST non-option token after `git` and any global options
# (`-C <dir>`, `-c <cfg>`, or bare `-flags`). Anchor detection to THAT token — never to any
# occurrence of the word — so a commit message that contains "push"/"commit" (e.g.
# `git commit -m "add push notifications"`) is not misread as that subcommand and wrongly denied.
_git_subcmd() {  # _git_subcmd <subcommand-name>
  printf '%s' "$command" | grep -qE "(^|[;&|[:space:]])git([[:space:]]+(-[cC][[:space:]]+[^[:space:]]+|-[^[:space:]]+))*[[:space:]]+$1([[:space:]]|$)"
}
is_commit() { _git_subcmd commit; }
is_push()   { _git_subcmd push; }

# ---- DENY rules first: deny must beat ask (§4.4 CRITICAL) ----

# 1. Attribution — deny WITHOUT gating on subcommand classification. A space-bearing quoted global
#    option before the subcommand (`git -C "/My Repo" commit …`, `git -c user.name="A B" commit …`)
#    defeats the token classifier below, so gating attribution-deny on is_commit would let an
#    attributed commit slip through unscreened — a silent hole in a categorical rule. Attribution
#    text has no legitimate place in ANY git command, so denying any git-bearing command carrying it
#    is fail-closed and correct. The rule is categorical ("no Co-Authored-By"), so match ANY
#    `Co-Authored-By:` trailer — not an enumerated vendor list, which silently ages out as new models
#    (Gemini, Llama, Grok, a generic "AI Assistant") appear — plus "Generated with" and the emoji.
if printf '%s' "$command" | grep -qiE 'co-authored-by:|generated with|🤖'; then
  emit deny "AI attribution is not permitted in commit messages (global rule: zero AI attribution — no Claude, no Co-Authored-By, no 'generated with'). AI is a tool, not an author. Rewrite the message without it. This overrides any tool default."
fi

# 2. Any push.
if is_push; then
  emit deny "The agent never pushes (global rule). Leave the branch local; the user pushes and merges via GitKraken."
fi

# ---- ASK rules: a human gate the agent cannot forge (§3.4) ----

if is_commit; then
  # A message we cannot read is not a message we can clear. `-F`/`--file` and `-C`/`--reuse-message`
  # are COMMIT options (they appear AFTER the `commit` subcommand), so scope the check to the
  # post-`commit` tail. This keeps a top-level `git -C <dir> commit` — where `-C` redirects the repo,
  # not the message — from being misread as an unreadable message (which would fire this ask via the
  # wrong branch and hide the target-resolution path below). Match glued forms too — git accepts
  # `-Fmsg.txt` and `-CHEAD` (no delimiter), so the value char after -F/-C may be non-space.
  commit_tail=${command#*commit}
  if printf '%s' "$commit_tail" | grep -qE '(^|[[:space:]])(-F|-C|--file|--reuse-message)([^[:space:]]|[[:space:]]|=|$)'; then
    emit ask "This commit's message is supplied from a file or another commit, so it cannot be screened for AI attribution. Approve only if you have read the message."
  fi

  # Resolve the repo the commit actually TARGETS, not the session cwd. ONLY a `git -C <dir>` or a
  # `cd <dir>` that PRECEDES the commit in the chain redirects where the commit runs; a `cd` AFTER
  # the commit (`git commit -m "x" && cd <feature-repo>`) changes the shell's later cwd but the
  # commit already ran in the current repo — reading the trailing cd's branch would let an on-main
  # commit slip through unasked (a silent bypass, §3.4). So scope resolution to the pre-commit
  # prefix. Within that prefix the cd match still anchors to start-of-string OR any `;`/`&`/`|`
  # separator, so a non-leading `cd` (`git fetch && cd <main-repo> && git commit`) still redirects.
  pre_commit=${command%%commit*}
  target="$cwd"
  cd_dir=$(printf '%s' "$pre_commit" | sed -nE 's/^([[:space:]]*|.*[;&|][[:space:]]*)cd[[:space:]]+([^[:space:]&;|]+).*/\2/p')
  gitc_dir=$(printf '%s' "$pre_commit" | sed -nE 's/.*git[[:space:]]+-C[[:space:]]+([^[:space:]]+).*/\1/p')
  [ -n "$cd_dir" ] && target="$cd_dir"
  [ -n "$gitc_dir" ] && target="$gitc_dir"

  # Reason: symbolic-ref works on an unborn branch (fresh `git init`, no commits) where
  # `rev-parse --abbrev-ref HEAD` errors, and it yields nothing on a detached HEAD.
  branch=""
  if [ -n "$target" ] && [ -d "$target" ]; then
    branch=$(git -C "$target" symbolic-ref --short HEAD 2>/dev/null || true)
  elif [ "$target" != "$cwd" ]; then
    # A different target dir was named but cannot be resolved here to read its branch — do not
    # assume it is safe. Ask rather than silently allowing a possible commit to main.
    emit ask "This commit targets a directory ('$target') whose branch cannot be verified from here. Approve only if it is not committing to main."
  fi
  if [ "$branch" = "main" ] || [ "$branch" = "master" ]; then
    emit ask "Committing directly to '$branch'. The global rule is: never commit to main — work on feature/*, fix/*, docs/*. Approve only if you are deliberately overriding that rule."
  fi
elif printf '%s' "$command" | grep -qwE 'commit|push'; then
  # git-bearing, but the classifier matched NEITHER commit nor push while a `commit`/`push` token IS
  # present — a quoted, space-bearing global option (`git -C "/My Repo" commit/push …`) can defeat
  # token detection. Do NOT fall through to a silent exit 0 on a possible commit/push: ask, so a
  # human screens it (§4.4). Deliberately conservative — a benign `git log --grep="commit"` also asks
  # — but ask is one click; a missed on-main commit or push is not.
  emit ask "This git command may be a commit or a push but its subcommand could not be classified (a quoted, space-bearing global option can defeat detection). Approve only if it is not an AI-attributed commit, a push, or a commit to main."
fi

exit 0  # no decision; normal permission flow applies
