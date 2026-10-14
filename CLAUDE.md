## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).

## Repo conventions

Overrides to the global rules, for this repo only:

- **Task tracking:** `PRPs/` plus the generated `PRPs/STATUS.md` replace `PLANNING.md` and
  `TASKS.md`. Do not create those files. (`PRPs/` is gitignored — local working documents.)
- **Plugin runtime scripts use `python3`, not `uv run`.** Scripts under `plugins/asic-tools/` run on
  users' machines, stdlib-only, invoked as `python3 <script>` from skill text; uv is not assumed
  there. Dev tooling in this repo runs through `uv run` (`uv sync` once).
- **Checks before commit:** `uv run ruff check .`, `uv run ruff format --check .`,
  `uv run pytest -q`, `bash plugins/asic-tools/hooks/tests/test_git_guard.sh`,
  `uv run python evals/run_evals.py --skip-snyk`, `claude plugin validate --strict plugins/asic-tools`.
  Drop `--skip-snyk` only when you mean to upload the seeded fixture to Snyk.
- **Skill trigger evals (paid):** `claude plugin eval plugins/asic-tools --ablation none
  --no-publish --max-cost-usd 5` — never from the repo root.
