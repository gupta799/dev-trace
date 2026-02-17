from __future__ import annotations

import csv
import random
from pathlib import Path

from devtrace.ml.constants import RAW_DATASET_COLUMNS
from devtrace.ml.schemas import TelemetryRow


def _sample_profile(rng: random.Random) -> dict[str, int]:
    draw = rng.random()

    if draw < 0.50:
        return {
            "duration_ms": rng.randint(120, 3500),
            "exit_code": 0,
            "timed_out": 0,
            "files_touched_count": rng.randint(1, 8),
            "lines_added": rng.randint(2, 120),
            "lines_deleted": rng.randint(0, 60),
        }

    if draw < 0.72:
        return {
            "duration_ms": rng.randint(2500, 26000),
            "exit_code": 0,
            "timed_out": 0,
            "files_touched_count": rng.randint(6, 45),
            "lines_added": rng.randint(80, 900),
            "lines_deleted": rng.randint(30, 650),
        }

    if draw < 0.90:
        return {
            "duration_ms": rng.randint(200, 10000),
            "exit_code": 1,
            "timed_out": 0,
            "files_touched_count": rng.randint(1, 14),
            "lines_added": rng.randint(1, 200),
            "lines_deleted": rng.randint(0, 220),
        }

    return {
        "duration_ms": rng.randint(10000, 120000),
        "exit_code": rng.choice([124, 137]),
        "timed_out": 1,
        "files_touched_count": rng.randint(0, 6),
        "lines_added": rng.randint(0, 40),
        "lines_deleted": rng.randint(0, 50),
    }


def _synthetic_label(row: TelemetryRow, rng: random.Random) -> float:
    score = 65.0
    score += 20.0 if row.exit_code == 0 else -20.0
    score -= 28.0 if row.timed_out else 0.0
    score += min(row.files_touched_count, 20.0) * 0.75
    score += min((row.lines_added + row.lines_deleted) / 120.0, 17.0)
    score -= min(row.duration_ms / 24000.0, 18.0)
    if row.exit_code != 0 and (row.lines_added + row.lines_deleted) > 240:
        score -= 8.0
    score += rng.uniform(-6.0, 6.0)
    return max(0.0, min(score, 100.0))


def generate_synthetic_dataset(output_path: Path, rows: int, seed: int = 42) -> int:
    """Generate synthetic dataset for bootstrapping model training."""
    if rows <= 0:
        raise ValueError("rows must be > 0")

    rng = random.Random(seed)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[*RAW_DATASET_COLUMNS, "productivity_label"])
        writer.writeheader()

        for _ in range(rows):
            profile = _sample_profile(rng)
            row = TelemetryRow(
                command_hash=f"{rng.getrandbits(64):016x}",
                duration_ms=profile["duration_ms"],
                exit_code=profile["exit_code"],
                timed_out=bool(profile["timed_out"]),
                files_touched_count=profile["files_touched_count"],
                lines_added=profile["lines_added"],
                lines_deleted=profile["lines_deleted"],
            )
            label = _synthetic_label(row, rng)
            writer.writerow(
                {
                    "command_hash": row.command_hash,
                    "duration_ms": int(row.duration_ms),
                    "exit_code": row.exit_code,
                    "timed_out": int(row.timed_out),
                    "files_touched_count": int(row.files_touched_count),
                    "lines_added": int(row.lines_added),
                    "lines_deleted": int(row.lines_deleted),
                    "productivity_label": f"{label:.4f}",
                }
            )

    return rows
