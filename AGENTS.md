# Repository Guidelines

## Project Structure & Module Organization
- Keep the repository root clean for top-level docs and config only (`AGENTS.md`, `README.md`, license files).
- Place runtime/source code in `src/`.
- Mirror source layout in `tests/` (example: `src/foo/bar.py` -> `tests/foo/test_bar.py`).
- Store static/reference files in `assets/` (images, data snapshots, sample walkthrough content).
- Keep automation scripts in `scripts/` (prefer PowerShell for Windows-first workflows).
- Put architecture notes and decisions in `docs/`.

## Build, Test, and Development Commands
This repository is currently scaffold-first. Use these baseline commands while contributing:
- `git status` — check current changes before and after edits.
- `git diff -- AGENTS.md` — review documentation changes before commit.
- `pwsh -NoProfile -Command "Get-ChildItem -Recurse"` — verify expected folder layout.

When adding executable modules, also add and document stable project commands (via `Makefile` or `scripts/`) for:
- `build` — compile/package artifacts.
- `test` — run the full automated suite.
- `run` — launch locally for manual verification.

## Coding Style & Naming Conventions
- Use UTF-8, 4-space indentation, and LF line endings.
- Directory names: lowercase-kebab-case (example: `walkthrough-parser`).
- Keep module/file naming consistent with language norms and map tests clearly to source.
- Prefer small, composable functions and avoid hidden side effects.

## Testing Guidelines
- Keep all automated tests under `tests/`, mirroring `src/`.
- Name tests by behavior (example: `test_handles_missing_checkpoint`).
- Add a regression test for every bug fix.
- New features should include at least one happy-path and one edge-case test.

## Commit & Pull Request Guidelines
- There is no stable history yet; adopt Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`).
- Keep each commit focused on one logical change.
- If the maintainer explicitly asks for "auto commit and push", commit all current tracked changes with a clear Conventional Commit message and push directly to `origin/main`.
- Current maintainer preference: after requested code/document changes are completed, auto-commit and auto-push to `origin/main` by default unless the maintainer says not to push.
- PRs should include a short summary, motivation, and test evidence.
- Add screenshots or logs when behavior/UI changes, and link related issue IDs.
