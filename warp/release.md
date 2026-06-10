# release — Warp prompt

Save as a Warp Drive prompt named `release`. Version-location table lives in the plugin
marketplace clone at
`~/.claude/plugins/marketplaces/asic-dev/plugins/asic-tools/skills/release/references/version_locations.md`
(or your repo checkout under `plugins/asic-tools/skills/release/references/`).

---

Prepare a release for this repo. You never push and never tag — I merge, tag, and push via
GitKraken. Your job is consistency: every version string moves together and the changelog
reflects what actually shipped.

1. SURVEY (read-only): find every version location per the reference table (pyproject,
   src/<pkg>/__init__.py __version__, .claude-plugin/plugin.json, package.json, Xcode
   MARKETING_VERSION in all build configs, Cargo.toml, README install snippets, …). If
   existing locations already disagree, STOP and report the drift — don't fix it as a side
   effect. Baseline = latest SemVer git tag (else latest CHANGELOG heading). Collect
   `git log <baseline>..HEAD` subjects, classify by Conventional Commit type; keep
   non-conventional subjects in an "Other" bucket, never silently dropped. Read
   CHANGELOG.md and note its exact format — the new entry must match it indistinguishably.

2. DECIDE: recommend the bump (BREAKING→major, feat→minor, else patch) with commit counts
   as evidence; confirm with me before applying.

3. APPLY: branch `release/vX.Y.Z` (never main). Update every location; re-grep the OLD
   version string repo-wide to catch missed spots (exclude .git, lockfiles, CHANGELOG
   history; regenerate lockfiles via the tool, never by hand). Write the CHANGELOG entry
   grouped per the file's convention, reworded for readers — not raw commit subjects. Run
   the repo's lint/tests if configured. Commit `chore(release): vX.Y.Z` — no AI
   attribution, not pushed.

4. REPORT: locations updated (file:key old→new), changelog entry verbatim, validation
   results, then my checklist: push + merge (no-ff) → annotated tag vX.Y.Z on main → push
   tag → optional GitHub release (provide ready-to-paste body). Note: for Claude Code
   plugin repos, the plugin.json bump is what makes `claude plugin update` ship — a
   release without it ships nothing.
