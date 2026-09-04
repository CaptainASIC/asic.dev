# Agent Tooling — Retrieval Lanes & Verified-Context Rules

Hard routing rules for the Dev Toolbox PRP loop. Not vibes. Every retrieval in a PRP skill
consults a named lane; every claim that enters a PRP carries a citation. This file is the
contract the skills implement.

## The three lanes (and why none is redundant)

| Lane | Tool | Owns | Source of truth |
|---|---|---|---|
| **Structure** | `graphify` **CLI** (`query` / `path` / `explain`) | cross-file relationships, god nodes, communities, "what touches what", broad orientation | local `graphify-out/graph.json` |
| **Semantic / memory / edit** | `serena` MCP | symbol-level nav (`find_symbol`, `find_referencing_symbols`), LSP-accurate edits, **cross-session memory** (`.serena/memories/`) | live LSP + on-disk memories |
| **External docs** | `Ref` MCP | third-party library / framework / API behavior, versioned | `api.ref.tools` |

### Empirically-determined overlap

- **graphify CLI vs serena** *do* overlap on "where is X / what relates to X". They are **not**
  interchangeable for this repo's usage:
  - graphify answers **whole-graph** questions (communities, god nodes, PR impact, A→B paths)
    in one scoped call. serena cannot — it walks symbols one hop at a time.
  - serena owns two things graphify cannot: **cross-session memory** (`.serena/memories/prp/`
    status memos are read by `prp-draft` Phase 1 and written by `prp-implement` close-out —
    actively used, 6 memos present) and **LSP-accurate symbol edits**.
  - **Verdict: keep both.** graphify = read/orient, serena = remember/edit. Neither is dropped.

- **graphify MCP (`graphify-airi`) IS redundant and harmful — dropped.** It was hardwired to
  `/Users/asic/Repositories/Airi/graphify-out/graph.json`, so every `mcp__graphify-airi__*`
  call from any other repo queried the **wrong repo's graph**. The CLI already reads the correct
  local graph. The MCP is removed from `~/.claude.json`; **all graphify retrieval goes through the
  CLI.** Never call `mcp__graphify-airi__*` tools.

- **Ref is NOT redundant.** It is the only lane for external/versioned API truth. Keep.

## Routing rules (hard)

1. **Code/structure question → graphify CLI first.** When `graphify-out/graph.json` exists,
   the first retrieval action is `graphify query`/`explain`/`path`. Raw `Read`/`grep` is
   allowed **only after** graphify has oriented you, or to read/modify specific lines a graph
   node already pointed you to. This applies to **subagents too** — every subagent prompt that
   explores code must carry the graphify-first instruction.
2. **"Where is this symbol / who calls it / rename it" → serena.** Use `find_symbol`,
   `find_referencing_symbols`, `replace_symbol_body`. Do not grep for symbol definitions when
   the LSP can answer exactly.
3. **Cross-session state → serena memory.** PRP status, prior decisions, architectural maps
   persist in `.serena/memories/`. Read at task start, write at close-out. Never re-derive
   from git what a memo already records.
4. **External library/API behavior → Ref.** Never code against a remembered API. Verify the
   installed version's docs via `ref_search_documentation` / `ref_read_url`. Record the
   verified version in the PRP.
5. **No graph present → graphify lane collapses to direct Read**, and that must be stated
   explicitly in the skill output ("no graph; oriented by direct read of …").

6. **`prp-implement` close-out refreshes the graph.** After the last task commit of a PRP,
   `prp-implement` close-out runs `graphify update .` — AST-only, no API cost, measured at ~0.5s
   on this repo. It re-extracts **code files only**; document nodes need the semantic
   `/graphify --update` and are not refreshed here, so the reported line names its scope rather
   than claiming the whole graph is current. The step is guarded by an existing `graphify-out/`:
   in a repo without one the command would *build* a graph rather than skip, and close-out never
   creates a graph a repo never had. This is a **cache warm, never a gate**: a missing binary, an
   absent `graphify-out/`, or a failed update degrades to one reported line in the final report and
   close-out continues. Rule 5 already makes "no graph" a legitimate state; refusing to close out a
   validated, committed implementation because a convenience cache would not rebuild inverts the
   cost of being wrong. `graphify-out/` is gitignored in the repos in play, so the refresh cannot
   dirty a tracked tree; where it is not, the changes are reported and left **unstaged**. Other
   code-writing skills do not refresh the graph today; generalising the rule is future work.

## Verified-context rule (enforced per PRP step)

**No claim, decision, or gotcha enters a PRP — or advances a PRP step — without a cited
source.** A citation is exactly one of:

- a **graph node** reference (`graphify` node `src=path loc=Lnn`), or
- a **`path:line`** read this session, or
- a **Ref doc URL** with the resolved version.

A conclusion that cannot be traced to one of those three is **not usable** and must be marked
`SPECULATIVE — verify before relying` and surfaced to the user. Prefer zero speculatives.

### Per-PRP-step retrieval source

| Step | Lane | Verified-context gate |
|---|---|---|
| `prp-draft` Ph1 context sweep | serena memory (read) + graphify wiki/orient | n/a (orientation) |
| `prp-draft` Ph2 codebase research | **graphify CLI first**, then Read for the `path:line` | every §4 reference = `path:line` read this session; every citation-scout subagent returns `{path,symbol,line,surprise}`, prose rejected |
| `prp-draft` Ph2 external libs | Ref | version recorded in PRP |
| `prp-review` reviewers (style lenses) | **graphify CLI first**, then Read cited files | findings cite a PRP quote **or** a `file:line` the reviewer read; speculation rejected by adjudicator |
| `prp-implement` A1 load | Read §4.1 MUST READ | — |
| `prp-implement` A3 drift check | **graphify CLI first**, then Read; citation-scout fan-out graphify-first | every verdict carries `evidence = path:line` |
| `prp-implement` A2.5 resume | git log (authority on done tasks) + serena memo | done-state from commits, never from prose |
| `prp-implement` close-out | serena memory (write) + **graphify refresh** (`graphify update .`, code nodes only) | refresh outcome reported as one line; never blocking |

## Blind-file-scan flags (fixed in this release)

These spots retrieved without a lane discipline and are corrected by the Phase 3 edits:

- `workflows/review_workflow.js` (then at `prp-review/references/`) — reviewer prompts told
  subagents to "Read the
  repo files" with **no graphify-first instruction**. Fixed: style-lens prompts now orient via
  graphify CLI before reading.
- `prp-implement` A3 Explore fan-out — prompt did not mandate graphify-first for subagents.
  Fixed: A3/A2.5 fan-out prompts now carry the graphify-first rule.
- The graphify guard hooks (`graphify-{read,grep}-guard.sh`) are **advisory only** — they
  inject `additionalContext`, they never `exit 2`/deny. The verified-context rule above is
  therefore enforced **in the skill prompts**, not by the hook. Do not rely on the hook to
  block a blind scan; it cannot.
