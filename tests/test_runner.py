from __future__ import annotations

from pathlib import Path

from devtrace.runner import run_command


def test_run_command_collects_execution_metrics(tmp_path: Path) -> None:
    metrics = run_command(["sh", "-lc", "echo hello"], repo_path=Path(tmp_path))
    assert metrics.duration_ms >= 0
    assert metrics.exit_code == 0
    assert metrics.timed_out is False
    assert len(metrics.command_hash) == 64
