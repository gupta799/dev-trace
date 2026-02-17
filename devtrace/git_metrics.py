from __future__ import annotations

import subprocess
from pathlib import Path

from devtrace.types import CommandMetrics


def _parse_numstat(output: str) -> dict[str, tuple[int, int]]:
    metrics_by_file: dict[str, tuple[int, int]] = {}

    for line in output.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        add_str, del_str, path = parts[0], parts[1], parts[2]

        added = 0
        deleted = 0
        if add_str != "-":
            added += int(add_str)
        if del_str != "-":
            deleted += int(del_str)

        current_add, current_del = metrics_by_file.get(path, (0, 0))
        metrics_by_file[path] = (current_add + added, current_del + deleted)

    return metrics_by_file


def collect_git_diff_metrics(repo_path: Path) -> tuple[int, int, int]:
    """Collect touched/add/delete metrics from git working tree and index."""
    try:
        result_working = subprocess.run(
            ["git", "-C", str(repo_path), "diff", "--numstat"],
            check=False,
            capture_output=True,
            text=True,
        )
        result_staged = subprocess.run(
            ["git", "-C", str(repo_path), "diff", "--cached", "--numstat"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return 0, 0, 0

    if result_working.returncode != 0 or result_staged.returncode != 0:
        return 0, 0, 0

    combined = _parse_numstat(result_working.stdout)
    for path, (added, deleted) in _parse_numstat(result_staged.stdout).items():
        current_add, current_del = combined.get(path, (0, 0))
        combined[path] = (current_add + added, current_del + deleted)

    touched = len(combined)
    lines_added = sum(change[0] for change in combined.values())
    lines_deleted = sum(change[1] for change in combined.values())
    return touched, lines_added, lines_deleted


def to_metrics(
    command_hash: str,
    duration_ms: int,
    exit_code: int,
    timed_out: bool,
    repo_path: Path,
) -> CommandMetrics:
    """Construct a command metrics record from execution + git state."""
    touched, added, deleted = collect_git_diff_metrics(repo_path)
    return CommandMetrics(
        command_hash=command_hash,
        duration_ms=duration_ms,
        exit_code=exit_code,
        timed_out=timed_out,
        files_touched_count=touched,
        lines_added=added,
        lines_deleted=deleted,
    )
