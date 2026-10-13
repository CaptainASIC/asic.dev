#!/bin/bash
# Stdin-JSON cases for git-guard.sh (PRP-009 base + PRP-019 additions). No network, no real commits, no pushes.
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
  [ "$rc" -eq 0 ] || { echo "FAIL $1 — guard exited $rc (decisions must exit 0)"; fail=$((fail+1)); return; }
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

# ---- PRP-019: wrapped, absolute-path, subshell and quoted forms (bypasses before v2.0.0) ----
check bash_c_push             'bash -c "git push"'                   /nonexistent-dir deny
check abs_path_push           '/usr/bin/git push origin main'        /nonexistent-dir deny
check subshell_push           'echo $(git push)'                     /nonexistent-dir deny
check backtick_push           'echo `git push`'                      /nonexistent-dir deny
check quoted_git_push         '"git" push origin main'               /nonexistent-dir deny
check quoted_subcmd_push      "git 'push' origin main"               /nonexistent-dir deny
check git_c_dot_push          'git -C . push'                        /nonexistent-dir deny
check backslash_git_push      '\git push origin main'                /nonexistent-dir deny
check push_backslash_subcmd   'git \
  push origin main'                                                  /nonexistent-dir deny
check variable_push_asks      'G=git; $G push'                       /nonexistent-dir ask
check git_ifs_push_asks       'git${IFS}push origin main'            /nonexistent-dir ask
check git_dir_spaced_push     'git --git-dir /x/.git push origin main' /nonexistent-dir deny
check work_tree_spaced_push   'git --work-tree /x push'              /nonexistent-dir deny
check commit_then_var_push    'git commit -m x && G=git; $G push'    /nonexistent-dir ask
check commit_then_quoted_push 'git commit -m x && git -c user.name="A B" push' /nonexistent-dir ask
check bash_c_attributed       "bash -c 'git commit -m \"x Co-Authored-By: Claude\"'" /nonexistent-dir deny
check session_trailer_denied  'git commit -m "fix: x

Claude-Session: https://claude.ai/code/session_01abc"'              /nonexistent-dir deny
check session_url_denied      'git commit -m "see https://claude.ai/code/session_01abc"' /nonexistent-dir deny
check gh_pr_attribution       'gh pr create --title x --body "Generated with Claude Code"' /nonexistent-dir deny
# ---- PRP-019: hook bypass is denied ----
check no_verify_commit        'git commit --no-verify -m "feat: x"'  /nonexistent-dir deny "Skipping git hooks"
check commit_short_n          'git commit -n -m "feat: x"'           /nonexistent-dir deny "Skipping git hooks"
check commit_glued_an         'git commit -an -m "feat: x"'          /nonexistent-dir deny "Skipping git hooks"
check merge_no_verify         'git merge --no-verify feature/x'      /nonexistent-dir deny "Skipping git hooks"
check hookspath_override      'git -c core.hooksPath=/dev/null commit -m "feat: x"' /nonexistent-dir deny "Skipping git hooks"
check skip_env_override       'SKIP=ruff git commit -m "feat: x"'    /nonexistent-dir deny "Skipping git hooks"
check husky_env_override      'HUSKY=0 git commit -m "feat: x"'      /nonexistent-dir deny "Skipping git hooks"
check heredoc_then_no_verify  "git commit -m \"\$(cat <<'EOF'
feat: x
EOF
)\" --no-verify"                                                     /nonexistent-dir deny "Skipping git hooks"
check backslash_no_verify     'git commit -m x \
  --no-verify'                                                       /nonexistent-dir deny "Skipping git hooks"
check amp_msg_no_verify       'git commit -m "a & b" --no-verify'    /nonexistent-dir deny "Skipping git hooks"
check amp_msg_short_n         'git commit -m "a & b" -n'             /nonexistent-dir deny "Skipping git hooks"
check semi_msg_glued_an       'git commit -m "a; b" -an'             /nonexistent-dir deny "Skipping git hooks"
check am_amp_path_short_n     'git am "fix & lint.patch" -n'         /nonexistent-dir deny "Skipping git hooks"
check commit_backslash_main   'git \
  commit -m "feat: x"'                                               "$TMP"           ask "never commit to main"
# ---- PRP-019: destructive local operations ask ----
check reset_hard_asks         'git reset --hard HEAD~1'              /nonexistent-dir ask "cannot be recovered"
check clean_fd_asks           'git clean -fd'                        /nonexistent-dir ask "cannot be recovered"
check branch_D_asks           'git branch -D old-feature'            /nonexistent-dir ask "cannot be recovered"
check branch_delete_force     'git branch --delete --force old'      /nonexistent-dir ask "cannot be recovered"
# ---- PRP-019: look-alikes stay silent ----
check log_grep_push_silent    'git log --grep push'                  /nonexistent-dir none
check reset_soft_silent       'git reset --soft HEAD~1'              /nonexistent-dir none
check clean_dry_run_silent    'git clean -n'                         /nonexistent-dir none
check branch_d_silent         'git branch -d merged-feature'         /nonexistent-dir none
check guard_path_grep_silent  "grep -n 'co-authored-by:' hooks/git-guard.sh" /nonexistent-dir none
check dot_git_path_silent     'ls .git/hooks'                        /nonexistent-dir none
check no_edit_amend_silent    'git commit --amend --no-edit'         /nonexistent-dir none
check heredoc_commit_silent   "git commit -m \"\$(cat <<'EOF'
feat: add push notifications
EOF
)\""                                                                 /nonexistent-dir none

# ---- PRP-019: an unparseable payload fails CLOSED (exit 2 + reason on stderr), never exit 0/1 ----
err=$(printf '%s' '{"tool_name":"Bash","tool_input":{"command":"git status"' | bash "$GUARD" 2>&1 >/dev/null); rc=$?
if [ "$rc" -eq 2 ] && [ "${err#*could not parse}" != "$err" ]; then
  echo "ok   unparseable_input_blocks -> exit 2"; pass=$((pass+1))
else
  echo "FAIL unparseable_input_blocks -> expected exit 2 with reason, got rc=$rc err='$err'"; fail=$((fail+1))
fi

echo "--- $pass passed, $fail failed"
[ "$fail" -eq 0 ]
