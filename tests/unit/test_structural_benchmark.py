from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_incremental_benchmark_should_report_sync_and_warm_cache() -> None:
    root = Path(__file__).parents[2]
    result = subprocess.run(
        [
            sys.executable,
            str(root / "scripts" / "benchmark_structural_baseline.py"),
            "--mode",
            "incremental",
            "--initial-commits",
            "2",
            "--increments",
            "1",
            "--measure-assessment",
        ],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["mode"] == "incremental"
    assert payload["initialCommits"] == 2
    assert payload["batches"][0]["addedCommits"] == 1
    assert payload["batches"][0]["baselineStable"] is True
    assert payload["batches"][0]["syncSeconds"] >= 0
    assert payload["batches"][0]["warmSeconds"] >= 0
    assert payload["assessment"]["beforeBaselineMedianSeconds"] >= 0
    assert payload["assessment"]["afterBaselineMedianSeconds"] >= 0
    assert isinstance(payload["assessment"]["overheadRatio"], float)
