# scaffold — Warp prompt

Save as a Warp Drive prompt named `scaffold`. Full templates live in the plugin marketplace
clone at `~/.claude/plugins/marketplaces/asic-dev/plugins/asic-tools/skills/scaffold/references/`
(or your repo checkout under `plugins/asic-tools/skills/scaffold/references/`).

---

Scaffold a new Python project to my standard. The result must RUN — `uv sync`,
`uv run pytest`, `uv run ruff check .`, `uv run mypy src/` all green before you report
done. A scaffold that fails any of those is not done.

1. INTERVIEW (one batch): project name (kebab; derive snake_case package), one-line
   description, kind (api / agent / cli / library), database needed? (PostgreSQL +
   SQLAlchemy + Redis only if yes — default no), test layout (co-located vertical-slice
   default, or central tests/), license (MIT default), target dir
   (~/Repositories/<name> default). Refuse to scaffold into a non-empty directory.

2. GENERATE from the reference templates (file_templates.md + kind_variants.md):
   pyproject (py3.12, ruff line-length 100 double quotes, mypy disallow_untyped_defs,
   pytest+cov), .gitignore, .env.example, .pre-commit-config.yaml, LICENSE, PRPs/ dir;
   src/<pkg>/ with config.py (Pydantic v2 Settings + lru_cache get_settings), exceptions.py
   (app base error family), logging_utils.py, kind modules (agent kind = agent.py/tools.py/
   prompts.py split); tests proving the expected/edge/failure trio per module; README.md,
   PLANNING.md (architecture + the conventions block: ≤500-line files, ≤50-line functions,
   ≤100-line classes, vertical slice, PRP-driven flow), TASKS.md (Active Roadmap /
   Discovered During Work / Completed), CHANGELOG.md ([Unreleased]), CLAUDE.md pointer.
   Everything typed + Google docstrings. Grep for leftover {{placeholders}} — zero allowed.

3. VERIFY (hard gate): the four commands above, all green, fix until they are.

4. GIT: `git init -b main`, then `git switch -c feature/initial-scaffold`, commit
   `feat: initial project scaffold` — never on main, no AI attribution, do not push, do
   not create a GitHub repo unless asked.

5. REPORT: path, top-level tree, four green check lines, next steps (GH repo → remote →
   push branch → merge in GitKraken; start features with prp-draft).
