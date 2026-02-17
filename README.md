# DevTrace

DevTrace captures command-level telemetry for CLI agents and exports training datasets.

## Phase implementation status

- Feature 1 (simple data collection): implemented
- Feature 2 (XGBoost training/scoring): planned next
- Feature 3 (sync/scaling): planned after Feature 2

## Captured metrics (Feature 1)

- `command_hash`
- `duration_ms`
- `exit_code`
- `timed_out`
- `files_touched_count`
- `lines_added`
- `lines_deleted`

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]

# initialize local db
python -m devtrace.cli init

# run and capture
python -m devtrace.cli run --agent codex -- sh -lc "echo hello"

# export training dataset
python -m devtrace.cli export --format csv --out ./dataset.csv
```

## Install (package users)

- `pipx install devtrace` (recommended for CLI users)
- `pip install devtrace` (inside an active virtualenv)
- Homebrew support is provided via a tap formula template at `packaging/homebrew/devtrace.rb`

For release/publish/Brew details, see `docs/release.md`.

## VS Code Debugging

This repo includes debug launch profiles in `.vscode/launch.json`.

1. Open **Run and Debug** in VS Code.
2. Select one of:
   - `DevTrace: init (.devtrace-test)`
   - `DevTrace: run capture (echo hello)`
   - `DevTrace: events (limit 5)`
   - `DevTrace: export csv`
3. Set breakpoints in:
   - `devtrace/cli.py`
   - `devtrace/runner.py`
   - `devtrace/git_metrics.py`
   - `devtrace/storage.py`
4. Press **F5** to run under debugger.

## Feature 1 CLI

- `init`
- `run`
- `events`
- `export`

Feature 2/3 code scaffolding may exist in the repository but is intentionally not part of the active CLI surface yet.
