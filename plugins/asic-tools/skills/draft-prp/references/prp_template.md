# PRP Canonical Template

Skeleton for `PRP-NNN_TITLE_IN_SNAKE_CAPS.md`. Bracketed text is guidance — replace it, never
ship it. All 12 sections appear in every PRP; depth scales with scope (a small fix may merge
§5 into §6 and keep §3 to two subsections, but the headings stay).

---

```markdown
# PRP-NNN: Title — Subtitle

**Objective:** This Product Requirements Prompt (PRP) provides a complete, implementation-ready
instruction set for an AI agent to [1–3 sentences: what gets built, on top of what, what is
explicitly untouched].

**Status:** Ready for execution
**Author:** [author]
**Date:** YYYY-MM-DD
**Branch:** `feature/prp-NNN-short-slug`

**Depends on:**
- **PRP-XXX** (Name — hard dependency; [which artifact/contract this PRP consumes]).
- **PRP-YYY** (Name — soft dependency; [why it helps but does not block]).

**Blocked by:** [What must land first, with file/task references — or "Nothing."]

---

## 1. Objective & Scope

**Goal:** [One paragraph: the end state, concrete and observable.]

**The Win:** [One paragraph: why this matters to the user/system. Benefit language, no fluff.]

**Summary of changes:**

| Area | Files | Action |
|------|-------|--------|
| [subsystem] | `path/to/file.py` | MODIFY |
| [subsystem] | `path/to/new_file.py` | CREATE |

**Total:** N new files, M modified files.

**Strict non-goals:**
- [What this PRP intentionally does NOT do. Be specific — these prevent scope creep.]

## 2. Problem Statement

### 2.1 Current Behaviour
[What exists now and how it falls short. Concrete: quote actual behavior, actual file
state, actual measurements. Reference prior PRPs as "(post-PRP-XXX)" where relevant.]

### 2.2 Root Cause
[Only when fixing something: the verified mechanism of the failure, with file:line.]

### 2.3 Desired Behaviour
[Numbered walk-through of the future state, step by step, from the trigger to the result.]

## 3. Architecture & Background

[Numbered subsections (3.1, 3.2, …), one per design decision. Each answers a WHY: why this
approach, why not the alternative, what constraint forced the choice. Decisions made in the
drafting interview land here. Use ASCII data-flow diagrams in ```text blocks where flow
matters. This section is what separates a PRP from a ticket — do not skip the reasoning.]

### 3.1 [Decision name]
[Prose + minimal code/schema illustrating the shape. Prescriptive tone: "must", "never".]

## 4. All Needed Context

### 4.1 Documentation & References

```yaml
# MUST READ — include these in the implementation context window
- file: path/to/source.py
  why: |
    [What in this file the implementer needs and why. Multi-sentence, specific.]

- url: https://official.docs/page
  why: [Section needed. Verified against installed version X.Y.Z.]

- file: PRPs/PRP-XXX_NAME.md
  why: [Contract this PRP builds on.]
```

### 4.2 Current Codebase Tree (relevant)

```text
src/
├── module/
│   ├── existing.py        # [role; why it matters here]
│   └── other.py           # (PRP-XXX) [origin note when relevant]
```

### 4.3 Desired Codebase Tree (additions/changes only)

```text
src/
├── module/
│   └── new_feature.py     # NEW — [single-line responsibility]
```

### 4.4 Known Gotchas & Library Quirks

```python
# CRITICAL: [Safety boundary or correctness trap. What breaks if violated.
# Every CRITICAL traces to evidence: source you read, docs you fetched, or a
# measurement. Include the evidence inline — signatures, versions, numbers.]

# GOTCHA: [Non-obvious behavior + the workaround. file:line where observed.]

# PATTERN: [Existing codebase precedent the implementation must mirror, with
# the exemplar path.]
```

## 5. Implementation Blueprint

### 5.1 Data Models & Structures
[Complete model definitions when the PRP introduces data shapes — Pydantic v2 idioms
(`@field_validator`, `model_config = ConfigDict(...)`), entity-specific PK naming
(`{entity}_id`), `{action}_at` timestamps, `is_{state}` booleans.]

### 5.2 Task List (execution order)

```yaml
Task 1: MODIFY path/to/file.py
  - [sub-action, imperative]
  - VERIFY: [the check that proves this task done — test name, command, observable]

Task 2: CREATE path/to/new_file.py
  - MIRROR pattern from: path/to/exemplar.py
  - VERIFY: [check]
```

[Action verbs: VERIFY, CREATE, MODIFY, APPEND, EXTEND, CHANGE, ADD, REMOVE, REPLACE, MERGE.
Order = dependency order. Every task names exact files. Every task pairs with a verify.]

## 6. Implementation Instructions

[One subsection per file, in task order: `### 6.N Modify: path/to/file.py` or
`### 6.N Create: path/to/file.py`. Copy-paste-grade code for new files and non-obvious
changes; for trivial edits, exact before/after suffices. Inline # CRITICAL / # GOTCHA
comments where the implementer needs them at the point of use. Constrain scope explicitly:
touch only the files listed; no adjacent "improvements"; existing callers stay compatible
unless a task says otherwise.]

## 7. Test Instructions

[One subsection per test file. Test intentions, not full code:]

### 7.1 tests/path/test_feature.py
- `test_happy_path_condition` → [input ⇒ expected]
- `test_edge_case_condition` → [boundary ⇒ expected]
- `test_failure_case_condition` → [invalid input ⇒ expected error]

[Minimum per feature: one expected-use, one edge, one failure case. Update existing tests
whose behavior contracts changed — list them.]

### 7.N Run

```bash
cd [backend] && uv run ruff check . --fix && uv run ruff format .
cd [backend] && uv run pytest tests/path/ -v
```

## 8. Manual Integration Smoke

```bash
# [Start dependencies, start service, hit the feature, observe. Real commands,
# copy-pasteable, using detected tooling. End with what success looks like.]
```

## 9. Validation & Acceptance Criteria

### 9.1 Level 1 — Syntax & Style
```bash
[ruff/linter commands]
```

### 9.2 Level 2 — Unit Tests
```bash
[pytest commands]
```

### 9.3 Level 3 — Integration
[Services up, health checks, end-to-end command.]

### 9.4 Acceptance Checklist
- [ ] [One checkbox per implementation artifact and per behavioral guarantee.]
- [ ] All new code ruff-clean BEFORE commit (no fix-up formatting commits).
- [ ] Commits on `feature/prp-NNN-slug` — never main. Conventional Commits format.
      No AI attribution of any kind in commit messages. Do not push — the user pushes.

## 10. Documentation Updates

[Paste-ready snippets the implementing agent applies after acceptance passes:]

### 10.1 PLANNING.md
[Exact markdown block to append/merge under the relevant workstream.]

### 10.2 TASKS.md
[Exact entry marking this PRP done, dated. Add sub-tasks discovered during implementation
under a "Discovered During Work" section.]

### 10.3 .serena/memories/prp/NNN_short_name.md
[Status memo: what shipped, what is pending, pointers for the next session.]

### 10.4 README.md / CHANGELOG.md
[Only if user-facing setup or behavior changed; state "No change" otherwise.]

## 11. Anti-Patterns to Avoid

- ❌ Don't [specific wrong path an implementer might plausibly take]. [Why it fails here.]
- ❌ Don't touch files outside the §1 summary table.
- ❌ Don't skip a failing validation level and proceed.

## 12. Future Work (out of scope)

- **[Deferred capability] (future PRP):** [One-liner what + one-liner why deferred.]
```
