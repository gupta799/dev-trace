# DevTrace Release and Distribution

## 1. Publish to PyPI

Prereqs:
- GitHub repo configured with a PyPI Trusted Publisher
- `publish-pypi.yml` workflow present

Steps:
1. Bump `version` in `pyproject.toml`.
2. Create and push git tag (for example `v0.2.0`).
3. Tag push trigger runs `.github/workflows/publish-pypi.yml`.
4. Optionally create a GitHub release for release notes.
5. Verify package appears at `https://pypi.org/project/devtrace/`.

## 2. Recommended install commands

- `pipx install devtrace` (best for end-user CLI installs)
- `pip install devtrace` (inside venv)

## 3. Homebrew setup

Homebrew formulas are Ruby files (`.rb`).

This repository now contains a tap-ready formula at `Formula/devtrace.rb`.

To publish and install:
1. Keep `Formula/devtrace.rb` updated with the latest release tag URL and sha256.
2. Push formula changes to `main`.
3. Users install with:
   - `brew tap gupta799/dev-trace`
   - `brew install devtrace`

## 4. About pipx and pixi

- `pipx`: installs Python CLI apps in isolated virtual environments and exposes commands globally.
- `pixi`: a cross-language environment and task manager from Prefix.dev; useful for reproducible dev environments, not required for end users to install `devtrace`.
