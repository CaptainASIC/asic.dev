#!/bin/bash
# Nineteen stdin-JSON cases for git-guard.sh. No network, no real commits, no pushes.
# The `deny` cases never reach a `git` invocation (deny rules run first), so only the on-main and
# target-dir cases need a repo — a bare `git init -b main`, no commit required.
set -uo pipefail
GUARD="$(cd "$(dirname "$0")/.." && pwd)/git-guard.sh"
pass=0; fail=0
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
git -C "$TMP" init -q -b main   # unborn branch; symbolic-ref still reports "main"

mk() { python3 -c 'import sys,json;print(json.dumps({"hook_event_name":"PreToolUse","tool_name":"Bash","cwd":sys.argv[2],"tool_input":{"command":sys.argv[1]}}))' "$1" "${2-/nonexistent-dir}"; }

check() { # check <label> <command> <cwd> <expected: deny|ask|none> [reason-substring]
  local out got reason rc
  out=$(mk "$2" "$3" | bash "$GUARD"); rc=$?
  [ "$rc" -eq 0 ] || { echo "FAIL $1 — guard exited $rc (must always be 0)"; fail=$((fail+1)); return; }
  # No output = no decision = "none". Normalise BEFORE parsing: a JSON extractor over empty input
  # yields empty (not "none"), which would make the legitimate no-output cases wrongly FAIL.
  if [ -z "$out" ]; then
    got=none
  else
    got=$(printf '%s' "$out" | python3 -c 'import sys,json;print(json.load(sys.stdin)["hookSpecificOutput"]["permissionDecision"])' 2>/dev/null || echo none)
  fi
  if [ "$got" != "$4" ]; then echo "FAIL $1 -> expected $4, got $got"; fail=$((fail+1)); return; fi
  if [ -n "${5-}" ]; then  # optionally assert the reason, not just the decision
    reason=$(printf '%s' "$out" | python3 -c 'import sys,json;print(json.load(sys.stdin)["hookSpecificOutput"].get("permissionDecisionReason",""))' 2>/dev/null || echo "")
    case "$reason" in
      *"$5"*) ;;
      *) echo "FAIL $1 -> decision $got OK but reason missing '$5'"; fail=$((fail+1)); return ;;
    esac
  fi
  echo "ok   $1 -> $got"; pass=$((pass+1))
}

check attribution_denied      'git commit -m "feat: x

Co-Authored-By: Claude <noreply@anthropic.com>"'                    /nonexistent-dir deny
check generated_with_denied   'git commit -m "chore: y — Generated with Claude Code"' /nonexistent-dir deny
check attribution_generic     'git commit -m "x Co-Authored-By: Gemini <x@y>"'        /nonexistent-dir deny
check push_denied             'git push origin main'                 /nonexistent-dir deny
check push_dry_run_denied     'git push --dry-run'                   /nonexistent-dir deny
check push_word_not_denied    'git commit -m "add push notifications"' /nonexistent-dir none
check attribution_on_main     'git commit -m "x Co-Authored-By: Claude"' "$TMP"       deny
check commit_on_main_asks     'git commit -m "feat: x"'              "$TMP"           ask
check commit_from_file_asks   'git commit -F msg.txt'                "$TMP"           ask
check commit_from_file_glued  'git commit -Fmsg.txt'                 "$TMP"           ask
check reuse_message_glued     'git commit -CHEAD'                    "$TMP"           ask
check git_c_targets_main      "git -C $TMP commit -m 'feat: x'"      /nonexistent-dir ask "never commit to main"
check cd_then_commit_on_main  "cd $TMP && git commit -m 'feat: x'"   /nonexistent-dir ask
check fetch_then_cd_on_main   "git fetch && cd $TMP && git commit -m 'feat: x'" /nonexistent-dir ask
# A `cd` AFTER the commit must NOT mask an on-main commit: cwd is main ($TMP), the trailing cd is
# ignored, so the commit is seen to target main -> ask.
check commit_then_cd_on_main  "git commit -m 'feat: x' && cd /tmp/feature-repo" "$TMP"          ask
# Space-bearing quoted global option before the subcommand: classification is defeated, but
# attribution-deny is ungated (deny) and an unclassifiable commit falls back to ask.
check git_c_spaced_attributed 'git -C "/My Repo" commit -m "x Co-Authored-By: Claude"' /nonexistent-dir deny
check git_c_spaced_commit     'git -C "/My Repo" commit -m "feat: x"'  /nonexistent-dir ask
check clean_commit_off_main   'git commit -m "feat: x"'              /nonexistent-dir none
check non_git_command         'npm test'                             /nonexistent-dir none

echo "--- $pass passed, $fail failed"
[ "$fail" -eq 0 ]
