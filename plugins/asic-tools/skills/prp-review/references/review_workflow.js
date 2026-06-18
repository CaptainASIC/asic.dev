export const meta = {
  name: 'prp-review',
  description: 'Adversarial PRP review gate: 6-lens fan-out, adjudicate, apply fixes, re-review (capped 3 rounds)',
  phases: [
    { title: 'Review' },
    { title: 'Adjudicate' },
    { title: 'Apply' },
  ],
}

// args.prpPath — absolute or repo-relative path to the PRP file under review.
// The harness may hand `args` to a scriptPath workflow as a JSON string rather than a parsed
// object, so coerce before reading.
const ARGS = typeof args === 'string' ? JSON.parse(args) : args
const PRP = ARGS && ARGS.prpPath
if (!PRP) throw new Error('review_workflow: args.prpPath is required')
const MAX_ROUNDS = 3

// Six distinct lenses: 3 logic, 3 style. Style lenses compare the PRP against real repo code.
const LENSES = [
  { key: 'requirements', kind: 'logic',
    focus: 'Does the PRP fully cover its stated goal (§1) and desired behaviour (§2.3)? Find ' +
           'missing requirements, unstated assumptions, and goal/scope mismatches.' },
  { key: 'architecture', kind: 'logic',
    focus: 'Is the §3 architecture sound and the simplest that works (KISS/YAGNI)? Find ' +
           'over-engineering, fragile designs, and decisions that fight the codebase.' },
  { key: 'verifiability', kind: 'logic',
    focus: 'Is every §5 task paired with a real VERIFY, and is every §9 acceptance criterion ' +
           'observable? Find edge cases with no test and unverifiable claims.' },
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

function reviewerPrompt(lens, round) {
  const readRepo = lens.kind === 'style'
    ? 'Read the repo files this PRP cites (§4.1 MUST READ and §4.2 tree) so you compare its ' +
      'proposals against code that actually exists. '
    : ''
  return `You are an adversarial PRP reviewer with the "${lens.key}" lens (round ${round}). ` +
    `Read the PRP at ${PRP}. ${readRepo}\n\n` +
    `Your lens: ${lens.focus}\n\n` +
    `Be skeptical and specific. Report only real problems you can ground in evidence (a quote ` +
    `from the PRP or a file:line you read) — no style preferences, no praise, no speculation. ` +
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
    `issue). Keep severity honest. Read the PRP and cited files as needed to judge. Return ` +
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

// Keep one finding per dedup_group; prefer the highest severity in the group.
const RANK = { blocker: 0, major: 1, minor: 2, nit: 3 }
function dedupe(valid) {
  const byGroup = new Map()
  for (const f of valid) {
    const k = f.dedup_group || f.claim
    const cur = byGroup.get(k)
    if (!cur || RANK[f.severity] < RANK[cur.severity]) byGroup.set(k, f)
  }
  return [...byGroup.values()]
}

const reviewLog = []
let residual = []

for (let round = 1; round <= MAX_ROUNDS; round++) {
  phase('Review')
  log(`Round ${round}/${MAX_ROUNDS}: 6 reviewers`)
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

  // Applied fixes are re-reviewed by the next round, which clears residual on a clean pass.
  // The final round has no verification round after it, so its applied blockers stay
  // unverified and are surfaced to the human rather than reported as confirmed-resolved.
  residual = round === MAX_ROUNDS ? blockers : []
}

return { reviewLog, residual }
