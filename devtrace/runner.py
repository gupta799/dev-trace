from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from devtrace.git_metrics import to_metrics
from devtrace.types import CommandMetrics
from devtrace.utils import hash_command, monotonic_ms


def run_command(command: list[str], repo_path: Path, timeout_s: float | None = None) -> CommandMetrics:
    """Execute command and collect the minimal command metrics."""
    start_ms = monotonic_ms()

    timed_out = False
    exit_code = 0
    stdout_text = ""
    stderr_text = ""

    try:
        completed = subprocess.run(
            command,
            cwd=repo_path,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        exit_code = completed.returncode
        stdout_text = completed.stdout
        stderr_text = completed.stderr
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        exit_code = 124
        stdout_text = exc.stdout or ""
        stderr_text = exc.stderr or ""

    if stdout_text:
        sys.stdout.write(stdout_text)
    if stderr_text:
        sys.stderr.write(stderr_text)

    duration_ms = max(0, monotonic_ms() - start_ms)
    command_hash = hash_command(command)

    return to_metrics(
        command_hash=command_hash,
        duration_ms=duration_ms,
        exit_code=exit_code,
        timed_out=timed_out,
        repo_path=repo_path,
    )
