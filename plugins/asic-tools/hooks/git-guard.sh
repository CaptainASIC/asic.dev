#!/bin/bash
# PreToolUse(Bash) guard for Captain ASIC's hard git rules.
#
# Reason: these rules are stated absolutely in CLAUDE.global.md but were previously enforced only by
# prose, which the Bash tool's own "Co-Authored-By: Claude" default actively contradicts.
#
# CRITICAL: decisions exit 0 with JSON on stdout — Claude Code ignores JSON on a non-zero exit. The
# ONE non-zero exit is 2, used only when the hook input cannot be parsed: exit 2 blocks a PreToolUse
# call on every Claude Code version, so a broken parse fails CLOSED. Never exit 1: it is a
# non-blocking error that lets the command through. hooks.json also sets onFailure:"block"
# (v2.1.295+) so a crash, a missing interpreter or a timeout blocks rather than passes.
set -uo pipefail

input=$(cat)

# Hot path: no python spawn for input that cannot carry a git or gh command. Coarse by design —
# a false hit only costs one parse below; a miss would need the JSON to hide "git" and "gh ".
case "$input" in
  *git*|*'gh '*) ;;
  *) exit 0 ;;
esac

# Parse once (python3 ships on every OS this plugin reaches; macOS has no jq). Line 1 = tool name,
# line 2 = cwd, the rest = the command (which may itself span lines).
if ! parsed=$(printf '%s' "$input" | python3 -c 'import sys,json
d=json.load(sys.stdin)
print(d.get("tool_name",""))
print(d.get("cwd","").replace("\n"," "))
print(d.get("tool_input",{}).get("command",""),end="")'); then
  echo "git-guard: could not parse the hook input, so the command cannot be screened; blocking (fail-closed)." >&2
  exit 2
fi
tool_name=$(printf '%s\n' "$parsed" | sed -n 1p)
cwd=$(printf '%s\n' "$parsed" | sed -n 2p)
command=$(printf '%s\n' "$parsed" | sed -n '3,$p')
[ "$tool_name" = "Bash" ] || exit 0
[ -n "$command" ] || exit 0

# Token boundaries. _B = characters that may sit immediately BEFORE a git/gh token: separators,
# whitespace, a path slash (/usr/bin/git), an opening quote (bash -c "git …"), a subshell opener
# ($(git …), `git …`) and `=` (G=git). _E = characters that may sit immediately AFTER a token.
#   _B also holds `\` (`\git push`, the alias-dodge idiom); _E also holds `$` and `{`
#   (`git${IFS}push`), so those spellings reach rule 5 instead of exiting silently here.
_B='[;&|[:space:]/"'\''(`=\]'
_E='[[:space:]"'\'');`&|${]'
_Q='["'\'']?'                                     # an optional quote around a token

# A backslash-newline is a line continuation: bash reads `git \<newline>push` as `git push`. Join
# those before any classification, or `_git_subcmd` (line-oriented) never sees `git … push`.
joined=${command//\\$'\n'/ }

has_token() {  # has_token <word>
  printf '%s' "$joined" | grep -qE "(^|${_B})$1${_Q}(${_E}|\$)"
}
has_token git || has_token gh || exit 0

emit() {  # emit <deny|ask> <reason>
  python3 -c 'import sys,json;print(json.dumps({"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":sys.argv[1],"permissionDecisionReason":sys.argv[2]}}))' "$1" "$2"
  exit 0
}

# The git subcommand is the FIRST non-option token after `git` and any global options
# (`-C <dir>`, `-c <cfg>`, a space-separated `--git-dir <dir>` / `--work-tree <dir>` /
# `--namespace <ns>` / `--super-prefix <p>` / `--exec-path <dir>`, or bare `-flags` incl. the
# `--opt=value` forms). Anchor detection to THAT token — never to any
# occurrence of the word — so a commit message that contains "push"/"commit" (e.g.
# `git commit -m "add push notifications"`) is not misread as that subcommand and wrongly denied.
_OPTS='([[:space:]]+(-[cC][[:space:]]+[^[:space:]]+|--(git-dir|work-tree|namespace|super-prefix|exec-path)[[:space:]]+[^[:space:]]+|-[^[:space:]]+))*'
_git_subcmd() {  # _git_subcmd <subcommand-name>
  printf '%s' "$joined" | grep -qE "(^|${_B})git${_Q}${_OPTS}[[:space:]]+${_Q}$1${_Q}(${_E}|\$)"
}
# grep is line-oriented: a flag after a heredoc message sits on a later line than `git`. Flag
# checks run on a one-line view (continuations already joined) so a trailing flag is in scope.
flat=$(printf '%s' "$joined" | tr '\n' ' ')
# The segment test below must not end at a `;`/`&`/`|` INSIDE a quoted span (`-m "build & test"
# -n`), so blank separators that sit inside quotes. Quotes are kept, so `_Q` forms still match.
# Reason: blanking only removes segment barriers — it can add a match, never hide one.
flat_seg=$(printf '%s' "$flat" | awk '{o="";q="";for(i=1;i<=length($0);i++){c=substr($0,i,1);if(q==""){if(c=="\""||c=="'\''")q=c}else if(c==q)q="";else if(index(";&|",c))c=" ";o=o c}printf "%s",o}')
# A flag on that subcommand, within the same command segment (no unquoted ;&| crossing).
_git_flag() {  # _git_flag <subcommand-name> <flag-ERE>
  printf '%s' "$flat_seg" | grep -qE "(^|${_B})git${_Q}${_OPTS}[[:space:]]+${_Q}$1${_Q}([[:space:]][^;&|]*)?[[:space:]](${2})(${_E}|=|\$)"
}
is_commit() { _git_subcmd commit; }
is_push()   { _git_subcmd push; }

# ---- DENY rules first: deny must beat ask ----

# 1. Attribution — screened on ANY git- or gh-bearing command, never gated on subcommand
#    classification: a wrapper or a quoted global option can defeat the classifier, and attribution
#    has no legitimate place in any git/gh command. Match ANY Co-Authored-By trailer (not a vendor
#    list), "Generated with", the robot emoji, and the Claude-Session trailer / claude.ai session
#    link that cloud and Remote Control sessions append (attribution.sessionUrl).
if printf '%s' "$command" | grep -qiE 'co-authored-by:|generated with|🤖|claude-session:|claude\.ai/code/session'; then
  emit deny "AI attribution is not permitted in commit messages or pull requests (global rule: zero AI attribution — no Claude, no Co-Authored-By, no 'generated with', no Claude-Session trailer or session link). AI is a tool, not an author. Rewrite the message without it. This overrides any tool default."
fi

# 2. Any push — including wrapped (bash -c "git push"), absolute-path, subshell and quoted forms.
if is_push; then
  emit deny "The agent never pushes (global rule). Leave the branch local; the user pushes and merges via GitKraken."
fi

# 3. Hook bypass — the commit hooks are where ruff and the other pre-commit gates run.
#    --no-verify is denied ANYWHERE in a git-bearing command (like core.hooksPath), not segment-
#    scoped: a message holding `&`/`;` (`-m "a & b" --no-verify`) would otherwise end the segment.
if printf '%s' "$flat" | grep -qE "(^|[[:space:]])--no-verify(${_E}|=|\$)" \
  || _git_flag commit '-[A-Za-z]*n[A-Za-z]*' \
  || _git_flag am '-[A-Za-z]*n[A-Za-z]*' \
  || printf '%s' "$command" | grep -qiE 'core\.hookspath' \
  || printf '%s' "$command" | grep -qE "(^|${_B})(SKIP|HUSKY)=[^[:space:]]*[[:space:]]+([^;&|]*[[:space:]])?git${_Q}(${_E}|\$)"; then
  emit deny "Skipping git hooks is not permitted (global rule: ruff check + ruff format BEFORE committing — the hooks are that gate). Drop --no-verify / -n / core.hooksPath / SKIP= / HUSKY= and fix what the hook reports."
fi

# ---- ASK rules: a human gate the agent cannot forge ----

# 4. Destructive, unrecoverable local operations. Ask, not deny: the user sometimes wants exactly
#    this, and a permission prompt is a gate the agent cannot answer itself (it holds in auto mode).
if _git_flag reset '--hard' \
  || _git_flag clean '-[A-Za-z]*f[A-Za-z]*|--force' \
  || _git_flag branch '-[A-Za-z]*D[A-Za-z]*' \
  || { _git_flag branch '-d|--delete' && _git_flag branch '-f|--force'; }; then
  emit ask "This git command discards work that cannot be recovered from the reflog or the remote (reset --hard, clean -f, or a forced branch delete). Approve only if you have checked what will be lost."
fi

# 5. Unclassifiable push/commit. An INDEPENDENT `if`, not an `elif` of the commit block: as an elif,
#    a classified commit earlier in the chain (`git commit -m "x" && G=git; $G push`) silenced it and
#    the push ran. It only asks, so running it before the commit block keeps deny-before-ask. The
#    signals are read from `rest` — the command split on ;&| with every classified-commit segment
#    dropped — so a commit's own quoted message or `"$(cat <<'EOF' …)"` heredoc never trips it.
#    Fires when a quote sits between `git` and the token (`git -C "/My Repo" push`) or the command is
#    built through indirection (`G=git; $G push`, eval). A plain `git log --grep push` stays silent.
rest=$(printf '%s' "$flat" | tr ';&|' '\n\n\n' \
  | grep -vE "(^|${_B})git${_Q}${_OPTS}[[:space:]]+${_Q}commit${_Q}(${_E}|\$)" || true)
if printf '%s' "$rest" | grep -qE "git[^;&|]*[\"'][^;&|]*(^|[^[:alnum:]_-])(commit|push)([^[:alnum:]_-]|\$)" \
  || { printf '%s' "$rest" | grep -qE '\$[A-Za-z_{(]|(^|[^[:alnum:]_])eval([^[:alnum:]_]|$)' \
       && printf '%s' "$rest" | grep -qE '(^|[^[:alnum:]_-])(commit|push)([^[:alnum:]_-]|$)'; }; then
  emit ask "This git command may be a commit or a push but its subcommand could not be classified (a quoted global option or variable indirection defeats detection). Approve only if it is not an AI-attributed commit, a push, or a commit to main."
fi

# Commit block: carried over VERBATIM from the pre-PRP git-guard.sh:63-101, except that the old
# trailing `elif` fallback is now the independent rule 5 above (the block closes with `fi`).
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
fi

exit 0  # no decision; normal permission flow applies
