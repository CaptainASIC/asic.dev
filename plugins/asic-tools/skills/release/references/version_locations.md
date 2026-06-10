# Version String Locations by Ecosystem

Survey table for Phase 1. Check every row whose marker file exists; a repo can hit several
rows (e.g. asic.dev: plugin.json + marketplace entries; Airi: pyproject + Xcode + docs).

| Marker | Version location(s) | Key / pattern |
|---|---|---|
| `pyproject.toml` | `pyproject.toml` | `[project] version = "X.Y.Z"` |
| `src/<pkg>/__init__.py` | same | `__version__ = "X.Y.Z"` — keep in lockstep with pyproject |
| `.claude-plugin/plugin.json` | each plugin dir | `"version": "X.Y.Z"` — gates `claude plugin update` |
| `.claude-plugin/marketplace.json` | repo root | per-plugin `"version"` if declared in entries |
| `package.json` | `package.json` (+ `package-lock.json` via `npm version`) | `"version": "X.Y.Z"` |
| `*.xcodeproj/project.pbxproj` | Xcode project | `MARKETING_VERSION = X.Y` (note: Xcode may drop trailing `.0`) and `CURRENT_PROJECT_VERSION` (build number — bump separately) |
| `Info.plist` (legacy Xcode) | app target | `CFBundleShortVersionString`, `CFBundleVersion` |
| `Cargo.toml` | crate root | `[package] version = "X.Y.Z"` |
| `docker-compose.yml` / Dockerfiles | image tags | `image: name:X.Y.Z` — only when repo self-references its own version |
| `CITATION.cff` | repo root | `version: X.Y.Z` |
| Docs | `README.md`, install snippets | literal version strings in install/usage examples |

After applying updates, **re-grep the OLD version string repo-wide** (exclude `.git/`,
lockfiles, `CHANGELOG.md` history) — anything still matching is either a missed location
(update it and report the table gap) or a historical reference (leave it, say so).

Known traps:

- `uv.lock` / `package-lock.json` contain the project's own version — regenerate via the
  tool (`uv lock`, `npm install`), never hand-edit.
- Xcode `MARKETING_VERSION` appears once per build configuration (Debug + Release) —
  update all occurrences.
- CHANGELOG `[Unreleased]` link refs at file bottom (Keep a Changelog style) need the new
  compare-URL line when present.
