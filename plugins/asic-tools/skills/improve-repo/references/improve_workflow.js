export const meta = {
  name: 'improve-repo',
  description: 'Audit a repo for ASIC-standard drift across enabled checks; return findings grouped by category',
  phases: [
    { title: 'Audit' },
  ],
}

// args.repoPath — path to the repo under audit.
// args.profile — { python, frontend, repoType: 'single'|'multi',
//   kind: 'api'|'agent'|'cli'|'library'|'unknown', ruff, mypy,
//   versionLocationsPath, scaffoldSpecPaths: [...] } from the skill's Phase 1. The reference-spec
//   paths are ABSOLUTE paths to this plugin's own bundled files (release/scaffold references),
//   resolved in Phase 1 — never relative '../release/...' / '../scaffold/...', which would resolve
//   against the arbitrary audited repo (where they do not exist), not against the plugin.
//   The harness may hand `args` to a scriptPath workflow as a JSON string rather than a parsed
//   object, so coerce before reading (same as review_workflow.js).
const ARGS = typeof args === 'string' ? JSON.parse(args) : args
const REPO = ARGS && ARGS.repoPath
if (!REPO) throw new Error('improve_workflow: args.repoPath is required')
const PROFILE = (ARGS && ARGS.profile) || {}
const VERSION_LOCATIONS_PATH = PROFILE.versionLocationsPath || ''
const SCAFFOLD_SPEC_PATHS = (PROFILE.scaffoldSpecPaths || []).join(', ')
const KIND = PROFILE.kind || 'unknown'

// One entry per check. `tier` gates enablement against the profile (this is how JS/TS gets the
// hygiene tier only — frontend-eligible checks carry a frontend tier, the deep Python checks do
// not). `safety` decides whether a finding may be auto-applied (mechanical) or must go to the
// PR-body checklist (generative/destructive). `focus` is the adversarial prompt.
const CHECKS = [
  { key: 'version-consolidation', tier: 'universal', safety: 'auto',
    focus: 'Find version-string sprawl. Walk the version-location table at ' +
           VERSION_LOCATIONS_PATH + ' (an absolute path to this plugin\'s bundled release ' +
           'reference — read it there, not in the audited repo) against ' +
           'the repo. When profile.repoType === "single", the repo must have ONE canonical root ' +
           'version (pyproject [project] version, or package.json version) and every other ' +
           'location must MATCH it — flag any location whose value DISAGREES with root and fix it ' +
           'to match: a src/<pkg>/__init__.py __version__ literal out of lockstep with pyproject ' +
           '(keep it a literal synced to root — do NOT rewrite it into ' +
           'importlib.metadata.version(...)), duplicated version strings, and plugin.json/Xcode ' +
           'MARKETING_VERSION values that disagree with root. When profile.repoType === "multi", ' +
           'do NOT force a single version across packages — only flag a package whose own ' +
           'locations disagree with each other, and sync them to THAT package\'s OWN canonical ' +
           'value: its own pyproject [project] version (Python) or package.json version (JS/TS). ' +
           'Each package\'s other locations sync to that package\'s manifest, never to a sibling ' +
           'package and never to a repo-wide root.' },
  { key: 'import-hygiene', tier: 'python+frontend', safety: 'auto',
    focus: 'Find MECHANICAL import drift inside a single file, BEYOND what ruff/eslint already ' +
           'flag: the same module re-imported inline inside many functions where one module-level ' +
           'import would do (collapse the inline re-imports), and duplicate imports of one symbol ' +
           'under different aliases (de-duplicate them). All fixes stay within one file — do NOT ' +
           'propose creating or editing a shared module here. Do NOT re-report plain unused ' +
           'imports (ruff F401) or redefinitions (ruff F811) — those are the linter\'s lane.' },
  { key: 'shared-import-extraction', tier: 'python+frontend', safety: 'propose',
    focus: 'Find identical imports repeated across sibling files that would belong in a shared ' +
           'module. Extracting to a new/edited shared module is generative — it creates or edits ' +
           'a module other files then import from — so this check is propose-only: report the ' +
           'duplication and the proposed shared module, never auto-apply it.' },
  { key: 'scaffold-conformance', tier: 'python', safety: 'propose',
    focus: 'Compare the repo against the ASIC scaffold spec at these absolute paths (this ' +
           'plugin\'s bundled scaffold references — read them there, not in the audited repo): ' +
           SCAFFOLD_SPEC_PATHS + '. The project kind is "' + KIND + '". The expected layout is ' +
           'KIND-SPECIFIC (kind_variants.md): api/cli expect a main.py entrypoint, agent expects ' +
           'the agent.py/tools.py/prompts.py split, library expects neither. Judge structure ' +
           'against the named kind ONLY — for example do NOT flag a missing agent.py/tools.py/' +
           'prompts.py split unless kind is "agent", and do NOT flag a missing main.py for a ' +
           'library. Always audit the kind-agnostic canonical files that every kind shares: ' +
           'a recognizable test layout — co-located tests beside code OR a central tests/ ' +
           'mirroring src/ (Airi-style); scaffold ships BOTH as valid (it recommends co-located ' +
           'but allows central), so flag ONLY a repo with NEITHER layout, never a repo that uses ' +
           'the central tests/ layout. Plus config.py (Pydantic v2 Settings + ' +
           'lru_cache get_settings), exceptions.py, logging_utils.py, and the __init__.py version ' +
           'singleton. If kind is "unknown", flag ONLY those kind-agnostic files and the layout — ' +
           'never the kind-specific entrypoint/split, to avoid over-flagging a CLI/library repo. ' +
           'Flag missing or misplaced structure. Creating files is generative, so this check is ' +
           'propose-only.' },
  { key: 'standards-surface', tier: 'python', safety: 'auto',
    focus: 'Run the repo\'s configured ruff and mypy (gated by profile.ruff / profile.mypy) and ' +
           'surface their output as findings — structure caps (files >500, functions >50, ' +
           'classes >100, lines >100), missing type hints, missing docstrings, lint violations. ' +
           'Run BOTH `ruff check` AND `ruff format --check` — they are SEPARATE commands: ' +
           '`ruff check` covers lint, `ruff format --check` covers formatting, and a repo can be ' +
           'lint-clean while still having format drift. Emit a fixable:true finding for EACH file ' +
           '`ruff format --check` reports as "would reformat" (Phase 4 applies it via ' +
           '`ruff format <path>`); never fold a would-reformat file into the skipped reason. ' +
           'Do NOT re-implement these checks; invoke the tools and group what they report. Mark ' +
           'each finding fixable:true when ruff can autofix it (formatting, import ordering, other ' +
           'ruff --fix rules) so Phase 4 can apply it via `ruff check --fix` (or `ruff format` for ' +
           'format findings); mark fixable:false for mypy findings and any ruff rule with no ' +
           'autofix (those route to the PR-body checklist). If a tool (ruff AND mypy both) is not ' +
           'configured in this repo, set "skipped" to that reason and return no findings.' },
  { key: 'naming-conventions', tier: 'python', safety: 'propose',
    focus: 'Flag database/API naming drift against the standing rules: bare `id` primary keys ' +
           '(should be {entity}_id), FK naming ({referenced_entity}_id), timestamps {action}_at, ' +
           'booleans is_{state}, RESTful routes /api/v1/{entities}/{entity_id}. Renaming a ' +
           'primary key changes a database contract, so this check is propose-only — never auto.' },
]

// A check runs when its tier is universal, or when any of its '+'-joined language tiers is present
// in the profile. New standards extend CHECKS without touching this filter (OCP).
function enabledChecks(profile) {
  return CHECKS.filter((c) => {
    if (c.tier === 'universal') return true
    return c.tier.split('+').some((t) =>
      (t === 'python' && profile.python) || (t === 'frontend' && profile.frontend))
  })
}

const FINDINGS_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    // Non-empty when the check could not run (e.g. no ruff configured); findings then empty.
    skipped: { type: 'string' },
    findings: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        properties: {
          severity: { type: 'string', enum: ['blocker', 'major', 'minor', 'nit'] },
          file: { type: 'string' },
          line: { type: 'integer' },
          problem: { type: 'string' },
          fix: { type: 'string' },
          est_lines: { type: 'integer' },
          // standards-surface sets this: true when ruff can autofix the finding (Phase 4 applies it
          // via `ruff check --fix`), false for mypy / non-autofixable rules (PR-body checklist).
          // ROUTING DEFAULT (Phase 4 step 4): an ABSENT fixable is treated as false — a
          // standards-surface finding that omits it routes to the PR-body checklist, never
          // auto-applied. This keeps the apply gate total even though fixable is optional here.
          fixable: { type: 'boolean' },
        },
        required: ['severity', 'file', 'problem', 'fix'],
      },
    },
  },
  required: ['findings'],
}

function checkPrompt(check) {
  // graphify-first is mandatory for subagents that explore code (docs/agent-tooling.md:36-40);
  // the guard hooks are advisory-only, so the instruction must live here. Mirrors
  // review_workflow.js:147-154. The prompt also pins the working directory to REPO: a Workflow
  // subagent inherits the orchestrator's cwd (NOT the audited repo), so every CLI call and read
  // must be scoped to REPO or the audit silently runs against the wrong tree.
  const orient = 'When graphify-out/graph.json exists in the repo, FIRST orient with the graphify ' +
    'CLI (`cd ' + REPO + ' && graphify query "<area>"` / `explain` / `path`) to find the relevant ' +
    'files, THEN read them — do not blind-grep before graphify has oriented you (see ' +
    'docs/agent-tooling.md). When no graph exists, say so and read directly. '
  return `You are auditing the repo at ${REPO} with the "${check.key}" check. ${orient}\n\n` +
    `CRITICAL — working directory: ALL CLI invocations (graphify, ruff, mypy, git) and ALL file ` +
    `reads MUST target ${REPO}, NOT your inherited cwd. A Workflow subagent inherits the ` +
    `orchestrator's cwd, which is NOT the audited repo, so prefix every command with ` +
    `\`cd ${REPO} && …\` (e.g. \`cd ${REPO} && ruff check .\`) and read files under ${REPO}. ` +
    `Every file:line you cite is relative to ${REPO}.\n\n` +
    `What to find: ${check.focus}\n\n` +
    `Report ONLY drift you can ground in a file:line you actually read — no style preferences, no ` +
    `speculation, no praise. Every finding cites file (and line where applicable) and a concrete ` +
    `fix. Severity: blocker = breaks the build or release; major = clear standards violation; ` +
    `minor = should fix; nit = optional. Estimate est_lines (lines the fix would touch) per ` +
    `finding. If the check cannot run in this repo, set "skipped" to the reason and return an ` +
    `empty findings array. Return via the schema.`
}

phase('Audit')
const active = enabledChecks(PROFILE)
log(`Auditing ${active.length} check(s): ${active.map((c) => c.key).join(', ')}`)

const results = await parallel(active.map((check) => () =>
  agent(checkPrompt(check), { label: `audit:${check.key}`, phase: 'Audit', schema: FINDINGS_SCHEMA })
    .then((r) => ({ check, result: r }))
))

// Group by check. Findings ALWAYS surface as a category — even when the agent also set a
// `skipped` note. A check can run one of several tools and skip another (e.g. standards-surface
// runs ruff, finds format drift, but mypy is absent): the partial-skip note must never discard
// the real findings. So check findings FIRST. `skipped` records a check only when it produced no
// findings (nothing ran, or a tool was unavailable with nothing to report); a partial skip
// alongside real findings is recorded with `partial: true`, not in place of them. A check that
// ran clean with zero findings and no skip is omitted from both.
const categories = []
const skipped = []
for (const entry of results.filter(Boolean)) {
  const { check, result } = entry
  if (!result) { skipped.push({ key: check.key, reason: 'audit agent returned no result' }); continue }
  const findings = result.findings || []
  if (findings.length > 0) {
    categories.push({ category: check.key, safety: check.safety, tier: check.tier, findings })
    if (result.skipped) skipped.push({ key: check.key, reason: result.skipped, partial: true })
    continue
  }
  if (result.skipped) { skipped.push({ key: check.key, reason: result.skipped }); continue }
}

return { categories, skipped }
