# Repository Guidelines

## Project Structure & Module Organization
- Keep runnable code under `devtrace/` (CLI entrypoints, storage, shell/MCP adapters) with supporting scripts in `scripts/`.
- Place tests in `tests/` mirroring the package layout; fixtures live in `tests/fixtures/`.
- Docs, specs, and design notes belong in `docs/`; keep architecture sketches in `docs/architecture/`.
- Generated or local state stays out of git; use `.devtrace/` and `*.db` in `.gitignore`.

## Build, Test, and Development Commands
- Create a virtualenv: `python -m venv .venv && source .venv/bin/activate`.
- Install deps editable: `pip install -e .[dev]` (include typer, sqlite helpers, pytest, ruff).
- Run tests: `pytest`.
- Lint/format: `ruff check .` and `ruff format .` (or `black` if you prefer that formatter).
- Local smoke: `python -m devtrace.cli --help` to confirm the CLI wiring.

## Coding Style & Naming Conventions
- Python 3.11+, 4-space indents, type hints everywhere; `mypy`-clean for public functions.
- Modules use snake_case; classes are PascalCase; CLI commands and options stay kebab-case.
- Keep functions short and single-purpose; prefer pure helpers in `devtrace/utils.py`.
- Docstrings: concise summary line + argument notes where behavior is non-obvious.

## Testing Guidelines
- Use `pytest` with descriptive test names: `test_<unit_under_test>_<expectation>`.
- Co-locate fixtures in `tests/fixtures/` and prefer factory helpers over inline blobs.
- Cover edge cases for shell wrapping, SQLite persistence, and git snapshot parsing.
- Aim for fast tests; mark slow/integration with `@pytest.mark.slow`.

## Commit & Pull Request Guidelines
- Commits: imperative, present tense, ≤72-char subject (e.g., `add shell wrapper telemetry`, `fix sqlite schema migration`). Squash noisy WIP commits before raising a PR.
- PRs: include a short summary, rationale, and before/after notes; link related issues/tasks; attach CLI output or logs when fixing bugs.
- Keep diffs small and atomic: separate schema changes, ingestion adapters, and UI work into distinct PRs.

## Security & Configuration Tips
- Default to local-only storage; never commit `.devtrace/` contents or local SQLite logs.
- Redact secrets in recorded command outputs; provide sanitized samples in tests.
- Validate untrusted paths and commands before logging; treat MCP proxy traffic as sensitive metadata.
