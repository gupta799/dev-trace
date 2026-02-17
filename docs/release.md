# DevTrace Release and Distribution

## 1. Publish to PyPI

Prereqs:
- GitHub repo configured with a PyPI Trusted Publisher
- `publish-pypi.yml` workflow present

Steps:
1. Bump `version` in `pyproject.toml`.
2. Create git tag and GitHub release.
3. Release trigger runs `.github/workflows/publish-pypi.yml`.
4. Verify package appears at `https://pypi.org/project/devtrace/`.

## 2. Recommended install commands

- `pipx install devtrace` (best for end-user CLI installs)
- `pip install devtrace` (inside venv)

## 3. Homebrew setup

Homebrew formulas are Ruby files (`.rb`).

To support `brew install devtrace`:
1. Create a tap repo, e.g. `jaiydevgupta/homebrew-tap`.
2. Add `Formula/devtrace.rb` from `packaging/homebrew/devtrace.rb`.
3. Update formula `url` and `sha256` to match the PyPI sdist of the released version.
4. Users install with:
   - `brew tap jaiydevgupta/tap`
   - `brew install devtrace`

## 4. About pipx and pixi

- `pipx`: installs Python CLI apps in isolated virtual environments and exposes commands globally.
- `pixi`: a cross-language environment and task manager from Prefix.dev; useful for reproducible dev environments, not required for end users to install `devtrace`.
