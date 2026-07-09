export const meta = {
  name: 'prp-review',
  description: 'Adversarial PRP review gate: 8-lens fan-out, adjudicate, apply fixes, re-review (capped 3 rounds)',
  phases: [
    { title: 'Review' },
    { title: 'Adjudicate' },
    { title: 'Apply' },
    { title: 'Verify' },
  ],
}

// args.prpPath — absolute or repo-relative path to the PRP file under review.
// The harness may hand `args` to a scriptPath workflow as a JSON string rather than a parsed
// object, so coerce before reading.
const ARGS = typeof args === 'string' ? JSON.parse(args) : args
const PRP = ARGS && ARGS.prpPath
if (!PRP) throw new Error('review_workflow: args.prpPath is required')
const MAX_ROUNDS = 3

// Eight distinct lenses: 5 logic, 3 style. Style lenses compare the PRP against real repo code.
const LENSES = [
  { key: 'requirements', kind: 'logic',
    focus: 'Does the PRP fully cover its stated goal (§1) and desired behaviour (§2.3)? Find ' +
           'missing requirements, unstated assumptions, and goal/scope mismatches.' },
  { key: 'architecture', kind: 'logic',
    focus: 'Is the §3 architecture sound and a fit for the codebase? Find fragile designs, ' +
           'decisions that fight the codebase, and missing integration concerns.' },
  { key: 'overbuild', kind: 'logic',
    focus: 'Walk each proposed artifact through the decision ladder: does it need to exist ' +
           '(YAGNI), or would stdlib / a native feature / an installed dep / one line do? Flag ' +
           'speculative features, single-use abstractions, unrequested configurability, and new ' +
           'dependencies that earn nothing. Carve-out: never flag validation, authz, error/' +
           'data-loss handling, or accessibility as over-build — those are non-negotiable.' },
  { key: 'verifiability', kind: 'logic',
    focus: 'Is every §5 task paired with a real VERIFY, and is every §9 acceptance criterion ' +
           'observable? Find edge cases with no test and unverifiable claims.' },
  { key: 'silent-failure', kind: 'logic',
    focus: 'Hunt the silent-failure surface (manual §3): where would a task or design in this ' +
           'PRP fail LATE and QUIETLY rather than loudly at build/test time? Boundaries — ' +
           'parsing, encoding, time/timezone/DST, concurrency, auth/expiry — plus rarely-run ' +
           'paths, off-by-one at edges, and wrong-but-plausible output. Flag any such surface ' +
           'that no §5 VERIFY or §9 acceptance criterion would catch. A loud failure the build ' +
           'or tests catch is out of scope for this lens.' },
  { key: 'naming', kind: 'style',
    focus: 'Do the PRP\'s proposed names (files, symbols, identifiers) match the conventions ' +
           'in the repo files it cites? Read those files; flag naming drift.' },
  { key: 'structure', kind: 'style',
    focus: 'Does the proposed file/module layout match how the cited repo organises code ' +
           '(vertical slices, references/ dirs, size caps)? Read the cited files; flag drift.' },
  { key: 'conventions', kind: 'style',
    focus: 'Do proposed error-handling, test, and docstring/comment patterns match the cited ' +
           'repo\'s established patterns? Read the cited files; flag drift.' },
]

const FINDINGS_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    findings: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        properties: {
          severity: { type: 'string', enum: ['blocker', 'major', 'minor', 'nit'] },
          lens: { type: 'string' },
          prp_section: { type: 'string' },
          file: { type: 'string' },
          claim: { type: 'string' },
          evidence: { type: 'string' },
          suggested_fix: { type: 'string' },
        },
        required: ['severity', 'lens', 'claim', 'suggested_fix'],
      },
    },
  },
  required: ['findings'],
}

const ADJUDICATION_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    findings: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        properties: {
          severity: { type: 'string', enum: ['blocker', 'major', 'minor', 'nit'] },
          lens: { type: 'string' },
          prp_section: { type: 'string' },
          claim: { type: 'string' },
          suggested_fix: { type: 'string' },
          valid: { type: 'boolean' },
          reason: { type: 'string' },
          dedup_group: { type: 'string' },
        },
        required: ['severity', 'claim', 'valid', 'reason', 'dedup_group'],
      },
    },
  },
  required: ['findings'],
}

// Forcing the apply agent to terminate in a structured tool call bounds it: without a schema
// it returns free text and can thrash (re-read, re-edit) with no completion signal, stalling
// the workflow's final await. The schema is the convergence signal.
const APPLY_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    summary: { type: 'string' },
    edits: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        properties: {
          prp_section: { type: 'string' },
          change: { type: 'string' },
        },
        required: ['prp_section', 'change'],
      },
    },
  },
  required: ['summary', 'edits'],
}

// The final round has no re-review after its apply. Rather than dump every applied blocker into
// `residual` (which mislabels applied fixes as surviving blockers), a verifier re-reads the edited
// PRP and reports, per finding, whether the issue genuinely remains. Only unresolved ones residual.
const VERIFY_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    verdicts: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        properties: {
          dedup_group: { type: 'string' },
          resolved: { type: 'boolean' },
          reason: { type: 'string' },
        },
        required: ['dedup_group', 'resolved', 'reason'],
      },
    },
  },
  required: ['verdicts'],
}

function reviewerPrompt(lens, round) {
  const readRepo = lens.kind === 'style'
    ? 'Compare the PRP\'s proposals against code that actually exists: when ' +
      'graphify-out/graph.json exists, FIRST orient with the graphify CLI ' +
      '(`graphify query "<area>"` / `explain` / `path`) to find the cited files, THEN read the ' +
      'repo files this PRP cites (§4.1 MUST READ and §4.2 tree). Do not blind-grep before ' +
      'graphify has oriented you (see docs/agent-tooling.md). '
    : ''
  const counterexample = lens.kind === 'logic'
    ? 'For any finding that claims a RUNTIME defect (wrong output, crash, race, boundary or ' +
      'encoding error), construct the specific input, state, or timing that triggers it — an ' +
      'actual constructed case, not "I can\'t think of one". A runtime-defect finding with no ' +
      'constructed failing case is at most `minor`. This does NOT apply to structural, ' +
      'architectural, or coverage findings (a fragile design, a missing requirement, an ' +
      'unverifiable criterion) — those stand on their own evidence and keep their severity. '
    : ''
  return `You are an adversarial PRP reviewer with the "${lens.key}" lens (round ${round}). ` +
    `Read the PRP at ${PRP}. ${readRepo}\n\n` +
    `Your lens: ${lens.focus}\n\n` +
    `Be skeptical and specific. Report only real problems you can ground in evidence (a quote ` +
    `from the PRP or a file:line you read) — no style preferences, no praise, no speculation. ` +
    `Every finding MUST cite either a PRP quote or a file:line you actually read; an uncited ` +
    `claim will be rejected by the adjudicator. ${counterexample}` +
    `Severity: blocker = would produce wrong code; major = significant gap; minor = should ` +
    `fix; nit = optional. Return findings via the schema; empty findings array if the PRP is ` +
    `sound on your lens.`
}

function adjudicatePrompt(findings) {
  return `You are the adjudicator for an adversarial PRP review of ${PRP}. Reviewers over-` +
    `report; your job is to filter. Here are all raw findings as JSON:\n\n` +
    `${JSON.stringify(findings, null, 2)}\n\n` +
    `For each finding: set valid=false (with a reason) if it is a false positive, a style ` +
    `preference, out of scope, or already handled by the PRP — otherwise valid=true. Collapse ` +
    `duplicates/overlaps by giving them the same dedup_group (unique string per distinct ` +
    `issue). ` +
    `Weight severity by SILENCE: a defect that would surface only in production or on a rarely-` +
    `run path (boundary, time/timezone, concurrency, auth/expiry) outranks one the build or ` +
    `tests catch loudly — never let a loud-but-trivial finding outrank a silent-but-costly one. ` +
    `This silence-weighting only RE-RANKS findings whose severity is otherwise justified; it does ` +
    `NOT lift the reviewer's counterexample cap — a runtime-defect claim that arrived with no ` +
    `constructed failing case stays capped at minor even when its failure surface is silent. ` +
    `Keep severity honest. Read the PRP and cited files as needed to judge. Return ` +
    `every finding via the schema with valid/reason/dedup_group set.`
}

function applyPrompt(toApply) {
  return `You are editing the PRP at ${PRP} to resolve validated review findings. Apply ONLY ` +
    `these blocker/major findings, each via its suggested_fix, editing the PRP file in place ` +
    `with the Edit tool:\n\n${JSON.stringify(toApply, null, 2)}\n\n` +
    `Make surgical edits to the relevant sections only. Do not rewrite unrelated parts, do not ` +
    `add a Review Log section (the driver does that), do not touch any file other than ${PRP}. ` +
    `When the edits are done, return via the schema: a one-line summary and one entry per ` +
    `section you changed. Returning the schema is your stop signal — do not keep re-reading.`
}

function verifyPrompt(applied) {
  return `You are verifying that blocker/major review fixes actually landed in the PRP at ${PRP}. ` +
    `Read the CURRENT PRP file. For each finding below, check whether its issue is now resolved in ` +
    `the file text:\n\n${JSON.stringify(applied, null, 2)}\n\n` +
    `Return one verdict per finding, keyed by its dedup_group: resolved=true if the PRP now ` +
    `addresses the claim, resolved=false (with a reason) if the issue genuinely still remains. ` +
    `Verify against the actual file content, not the suggested_fix wording. For any STYLE-lens ` +
    `finding (naming/structure/conventions), do not accept the edit on the PRP's word alone — ` +
    `re-confirm against the cited repo file (graphify-first to locate it, then read the ` +
    `file:line) that the PRP now matches the real code; resolved=false if the edit diverges from ` +
    `what the repo actually does. Return via the schema.`
}

// Keep one finding per dedup_group; prefer the highest severity in the group.
const RANK = { blocker: 0, major: 1, minor: 2, nit: 3 }
function dedupe(valid) {
  const byGroup = new Map()
  for (const f of valid) {
    const k = f.dedup_group || f.claim
    f.dedup_group = k // stamp a stable key so the final-round verifier can match verdicts back
    const cur = byGroup.get(k)
    if (!cur || RANK[f.severity] < RANK[cur.severity]) byGroup.set(k, f)
  }
  return [...byGroup.values()]
}

const reviewLog = []
let residual = []

for (let round = 1; round <= MAX_ROUNDS; round++) {
  phase('Review')
  log(`Round ${round}/${MAX_ROUNDS}: ${LENSES.length} reviewers`)
  const reviews = await parallel(LENSES.map((lens) => () =>
    agent(reviewerPrompt(lens, round), {
      label: `review:${lens.key}`, phase: 'Review', schema: FINDINGS_SCHEMA,
    })
  ))
  const raw = reviews.filter(Boolean).flatMap((r) => r.findings || [])
  if (raw.length === 0) {
    reviewLog.push({ round, raw: 0, valid: 0, applied: 0, note: 'clean — no findings' })
    residual = []
    break
  }

  phase('Adjudicate')
  const adj = await agent(adjudicatePrompt(raw), {
    label: 'adjudicate', phase: 'Adjudicate', schema: ADJUDICATION_SCHEMA,
  })
  const valid = dedupe((adj && adj.findings ? adj.findings : []).filter((f) => f.valid))
  const blockers = valid.filter((f) => f.severity === 'blocker' || f.severity === 'major')

  if (blockers.length === 0) {
    reviewLog.push({ round, raw: raw.length, valid: valid.length, applied: 0,
      note: 'no blocker/major findings — only advisory remain', advisory: valid })
    residual = []
    break
  }

  phase('Apply')
  log(`Round ${round}: applying ${blockers.length} blocker/major fix(es)`)
  const result = await agent(applyPrompt(blockers),
    { label: 'apply', phase: 'Apply', schema: APPLY_SCHEMA })
  reviewLog.push({ round, raw: raw.length, valid: valid.length, applied: blockers.length,
    applied_findings: blockers, summary: result ? result.summary : '(apply returned no summary)' })

  // Non-final rounds: applied fixes are re-reviewed by the next round, which recomputes residual.
  // Final round: no re-review follows, so verify the applied fixes actually landed in the file and
  // surface ONLY the genuinely-unresolved ones — not every applied blocker (that was the mislabel).
  if (round === MAX_ROUNDS) {
    phase('Verify')
    log(`Round ${round}: verifying ${blockers.length} final-round fix(es) landed`)
    const check = await agent(verifyPrompt(blockers),
      { label: 'verify', phase: 'Verify', schema: VERIFY_SCHEMA })
    const verdicts = new Map(
      (check && check.verdicts ? check.verdicts : []).map((v) => [v.dedup_group, v]))
    // Unresolved, or unverifiable (no verdict returned) → surface to the human.
    residual = blockers.filter((b) => {
      const v = verdicts.get(b.dedup_group)
      return !v || v.resolved === false
    })
  } else {
    residual = []
  }
}

return { reviewLog, residual }
