---
name: scaffold
description: Bootstrap a new Python project to Captain ASIC's standard — uv + ruff(100) + mypy + pytest, Pydantic v2 settings, vertical-slice layout, PLANNING.md/TASKS.md/CHANGELOG.md skeletons, working sample tests, git initialized on a feature branch. Use when the user says "scaffold a project", "new project", "bootstrap a repo", "set up a new python project", or invokes /scaffold. Produces a runnable project (tests pass, lint clean), not a paper template.
---

# scaffold

Generates a complete, *verified-working* project skeleton. The bar: `uv sync`, `uv run
pytest`, `uv run ruff check .`, and `uv run mypy src/` are all green before you report done.
A scaffold that doesn't run is a paper template — never ship one.

Reference files (read at generation time):
- `references/file_templates.md` — every common file, verbatim, with `{{placeholders}}`
- `references/kind_variants.md` — additions per project kind (api / agent / cli / library)

## Phase 1 — Interview

Collect before generating (batch as one question round; skip anything already stated):

1. **Project name** — kebab-case dir name; derive `snake_case` package name from it.
2. **One-line description** — lands in pyproject, README, and PLANNING.md.
3. **Kind** — `api` (FastAPI service) / `agent` (LLM agent system) / `cli` (command-line
   tool) / `library`. Drives optional deps and sample modules.
4. **Database?** — only when kind needs persistence: PostgreSQL via SQLAlchemy/SQLModel
   (+ Redis cache per standing rules). Default: none — YAGNI.
5. **Test layout** — co-located (`src/pkg/module/tests/` beside code, vertical-slice
   default) or central (`tests/` mirroring `src/`, Airi-style). Recommend co-located.
6. **License** — default MIT.
7. **Target directory** — default `~/Repositories/<name>`. Refuse to scaffold into a
   non-empty directory; report what's in the way instead.

## Phase 2 — Generate

Order matters — structure, then config, then code, then docs:

1. `mkdir` tree per kind (see kind_variants). Create `PRPs/` (empty, with `.gitkeep`) —
   feature work in this stack is PRP-driven from day one.
2. Write `pyproject.toml` from template: project metadata, `requires-python = ">=3.12"`,
   `[build-system]` on `uv_build` (`{{uv_build_req}}` from `uv --version`), `[tool.ruff]`
   line-length 100 / py312 / double quotes, `[tool.mypy]` strict-leaning with the pydantic
   plugin, `[tool.pytest]` strict with an 80% coverage floor. Then run the template's
   Dependencies block — `uv python pin 3.12`, `uv add --no-sync` runtime deps per kind and the
   dev toolchain. Never hand-write a dependency list. The build system is load-bearing: without
   it uv never installs the package, so `[project.scripts]` is skipped and tests cannot
   import `{{pkg}}`.
3. Write `.gitignore`, `.env.example`, `.pre-commit-config.yaml`, `LICENSE`.
4. Write core source from templates — every file fully typed, Google docstrings on every
   public symbol, `# Reason:` comments where logic is non-obvious:
   - `src/{{pkg}}/__init__.py` (version singleton)
   - `src/{{pkg}}/config.py` — Pydantic v2 `Settings` + `lru_cache` `get_settings()`
   - `src/{{pkg}}/exceptions.py` — app base exception + one structured example
   - `src/{{pkg}}/logging_utils.py` — structured logging factory
   - kind-specific modules (see kind_variants; agent kind gets the canonical
     `agent.py` / `tools.py` / `prompts.py` split)
5. Write tests demonstrating the standing three-case pattern (expected / edge / failure)
   against real generated code — `conftest.py` fixtures, descriptive names. These must
   pass; they are the proof the scaffold works, not decoration.
6. Write docs from templates: `README.md`, `PLANNING.md`, `TASKS.md`, `CHANGELOG.md`
   (`[Unreleased]` only), `AGENTS.md` (5-line agent notes for every coding agent), and
   `CLAUDE.md` (`@AGENTS.md` import plus the Claude Code commands).

Substitute every `{{placeholder}}` — grep for `{{` afterward; any survivor is a defect.

## Phase 3 — Verify (hard gate)

```bash
cd <target> && uv sync
uv run ruff check . && uv run ruff format --check .
uv run mypy src/
uv run pytest -v
uv run <name> --version          # cli kind only — proves the console script installed
```

All green or you fix and re-run — never report a failing scaffold as done. No `uv venv`: the
`uv add` calls already created `.venv`, and `uv venv` exits 2 on an existing one. Then:

```bash
git init -b main
git switch -c feature/initial-scaffold
git add -A && git commit -m "feat: initial project scaffold"
```

Commit lands on the feature branch — never main. No AI attribution in the commit message.
Do not push; do not create a GitHub repo unless asked.

## Phase 4 — Report

Path, tree summary (one line per top-level entry), the four green check outputs (one line
each), and next steps: create GitHub repo → `git remote add origin` → push branch + merge
via GitKraken; refresh hook revs with `uv run pre-commit autoupdate` (needs the git repo and
GitHub access); start feature work with `/asic-tools:prp-draft`.
