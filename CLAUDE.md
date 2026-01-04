# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

DevTrace is a local-first provenance tracking tool for AI-augmented development. It records sessions (traces) and events (spans) like `run_command`, `edit_files`, `git_snapshot`, `mcp_call`, and `note` to answer "what did the agent change, in what order, and why?" - information not captured by git history alone.

Data is stored locally in `.devtrace/` (SQLite/JSONL), with optional global stats in `~/.devtrace/`.

## Build and Development Commands

```bash
# Setup
python -m venv .venv && source .venv/bin/activate
pip install -e .[dev]

# Testing
pytest                          # run all tests
pytest tests/test_file.py       # run single test file
pytest -k "test_name"           # run tests matching pattern
pytest -m slow                  # run slow/integration tests

# Linting and Formatting
ruff check .
ruff format .

# Verify CLI
python -m devtrace.cli --help
```

## Architecture

- **Language**: Python 3.11+, Typer CLI
- **Storage**: SQLite under `.devtrace/`
- **Code location**: `devtrace/` (CLI entrypoints, storage, shell/MCP adapters)
- **Tests**: `tests/` mirroring package layout, fixtures in `tests/fixtures/`
- **Docs/specs**: `docs/`, architecture in `docs/architecture/`

## CLI Commands (Planned)

```bash
devtrace init                           # initialize tracking
devtrace shell --agent <name>           # start tracked shell session
devtrace snapshot --label "<msg>"       # create git snapshot
devtrace log --follow                   # tail events
devtrace show --session <id>            # show session timeline
devtrace sessions                       # list sessions
```

## Coding Conventions

- Type hints everywhere; `mypy`-clean for public functions
- 4-space indents, snake_case modules, PascalCase classes, kebab-case CLI commands
- Pure helpers go in `devtrace/utils.py`
- Test naming: `test_<unit_under_test>_<expectation>`

## Important Notes

- Never commit `.devtrace/` contents or `*.db` files
- Redact secrets in recorded command outputs
- Mark slow/integration tests with `@pytest.mark.slow`
