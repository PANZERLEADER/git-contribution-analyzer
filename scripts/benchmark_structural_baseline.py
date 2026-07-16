from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import tempfile
import tracemalloc
from datetime import UTC, datetime, timedelta
from pathlib import Path
from statistics import median
from time import perf_counter

from git_contribution_analyzer.adapters.workspace.layout import WorkspaceLayout
from git_contribution_analyzer.application.use_cases.assess_work import assess_work
from git_contribution_analyzer.application.use_cases.index_repository import index_repository
from git_contribution_analyzer.application.use_cases.init_project import init_project
from git_contribution_analyzer.application.use_cases.manage_structural_baselines import (
    rebuild_structural_baseline,
)
from git_contribution_analyzer.application.use_cases.map_identity import map_identity
from git_contribution_analyzer.domain.models.contribution import ContributionCommit
from git_contribution_analyzer.domain.models.structural_baseline import StructuralRuleConfig
from git_contribution_analyzer.domain.services.structural_baseline import (
    build_structural_baseline,
)


def _commit(index: int, started_at: datetime) -> ContributionCommit:
    paths = tuple(
        sorted(
            {
                f"src/module_{(index + offset) % 40}/file_{(index * 7 + offset) % 500}.py"
                for offset in range(4)
            }
        )
    )
    return ContributionCommit(
        hash=f"{index:040x}",
        subject=f"feat: synthetic {index}",
        authored_at=started_at + timedelta(minutes=index),
        commit_type="FEATURE",
        delivery_status="LANDED",
        paths=paths,
        modules=tuple(sorted({path.split("/", maxsplit=1)[0] for path in paths})),
        insertions=20,
        deletions=5,
        files_changed=len(paths),
        merge=False,
        binary_files=0,
        generated_files=0,
        patch_id=f"patch-{index}",
    )


def _domain_benchmark(commits_count: int) -> dict[str, object]:
    if commits_count < 1:
        raise SystemExit("--commits must be positive")
    started_at = datetime(2020, 1, 1, tzinfo=UTC)
    commits = tuple(_commit(index, started_at) for index in range(commits_count))
    cutoff = started_at + timedelta(minutes=commits_count + 1)
    tracemalloc.start()
    started = perf_counter()
    baseline = build_structural_baseline(
        commits,
        cutoff=cutoff,
        config=StructuralRuleConfig(minimum_baseline_commits=2),
        identity_context={"benchmark": str(commits_count)},
    )
    elapsed = perf_counter() - started
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {
        "commits": commits_count,
        "eligibleFiles": baseline.summary.eligible_files,
        "rawEdges": baseline.summary.raw_edges,
        "hotspots": len(baseline.materialization.file_metrics),
        "couplings": len(baseline.materialization.edge_metrics),
        "elapsedSeconds": round(elapsed, 4),
        "peakMemoryBytes": peak,
        "factRuleVersion": "structural-facts-v1",
    }


def _run_git(repository: Path, *arguments: str, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )
    return result.stdout.strip()


def _write_git_commit(repository: Path, index: int, started_at: datetime) -> None:
    module = repository / "src" / f"module_{index % 5}"
    module.mkdir(parents=True, exist_ok=True)
    (module / f"file_{index % 20}.py").write_text(
        f"VALUE = {index}\n",
        encoding="utf-8",
    )
    config = repository / "config" / "settings.yml"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(f"revision: {index}\n", encoding="utf-8")
    _run_git(repository, "add", "src", "config")
    occurred_at = started_at + timedelta(minutes=index)
    environment = os.environ.copy()
    environment.update(
        {
            "GIT_AUTHOR_DATE": occurred_at.isoformat(),
            "GIT_COMMITTER_DATE": occurred_at.isoformat(),
        }
    )
    _run_git(repository, "commit", "-m", f"feat: benchmark {index}", env=environment)


def _measure_assessment(repository: Path) -> float:
    assess_work(repository, person_selectors=("benchmark@example.com",))
    timings: list[float] = []
    for _ in range(7):
        started = perf_counter()
        assess_work(repository, person_selectors=("benchmark@example.com",))
        timings.append(perf_counter() - started)
    return median(timings)


def _copy_sqlite(source: Path, target: Path) -> None:
    for suffix in ("-wal", "-shm"):
        Path(f"{target}{suffix}").unlink(missing_ok=True)
    with sqlite3.connect(source) as source_connection, sqlite3.connect(
        target
    ) as target_connection:
        source_connection.backup(target_connection)


def _incremental_benchmark(
    initial_commits: int,
    increments: tuple[int, ...],
    *,
    measure_assessment: bool,
) -> dict[str, object]:
    if initial_commits < 1:
        raise SystemExit("--initial-commits must be positive")
    if not increments or any(value < 1 for value in increments):
        raise SystemExit("--increments must contain positive integers")
    started_at = datetime(2020, 1, 1, tzinfo=UTC)
    cutoff = datetime(2030, 1, 1, tzinfo=UTC)
    with tempfile.TemporaryDirectory(prefix="gca-structural-incremental-") as temporary:
        repository = Path(temporary) / "repository"
        repository.mkdir()
        _run_git(repository, "init", "-b", "main")
        _run_git(repository, "config", "user.name", "Structural Benchmark")
        _run_git(repository, "config", "user.email", "benchmark@example.com")
        next_index = 0
        for _ in range(initial_commits):
            _write_git_commit(repository, next_index, started_at)
            next_index += 1

        started = perf_counter()
        init_project(repository)
        initial_index_seconds = perf_counter() - started
        assessment_before: float | None = None
        database = WorkspaceLayout.for_repository(repository).database
        assessment_snapshot = Path(temporary) / "assessment-before.sqlite"
        if measure_assessment:
            map_identity(
                repository,
                name="Structural Benchmark",
                email="benchmark@example.com",
                person_name="Structural Benchmark",
                person_email="benchmark@example.com",
            )
            _copy_sqlite(database, assessment_snapshot)
            assessment_before = _measure_assessment(repository)
            _copy_sqlite(assessment_snapshot, database)
        started = perf_counter()
        initial_baseline = rebuild_structural_baseline(repository, cutoff=cutoff)
        initial_baseline_seconds = perf_counter() - started
        assessment_after = (
            _measure_assessment(repository) if measure_assessment else None
        )
        batches: list[dict[str, object]] = []
        for increment in increments:
            for _ in range(increment):
                _write_git_commit(repository, next_index, started_at)
                next_index += 1
            started = perf_counter()
            sync = index_repository(repository, full_rebuild=False)
            sync_seconds = perf_counter() - started
            started = perf_counter()
            cold = rebuild_structural_baseline(repository, cutoff=cutoff)
            cold_seconds = perf_counter() - started
            started = perf_counter()
            warm = rebuild_structural_baseline(repository, cutoff=cutoff)
            warm_seconds = perf_counter() - started
            batches.append(
                {
                    "addedCommits": increment,
                    "indexedCommits": sync["indexedCommits"],
                    "newCommits": sync["newCommits"],
                    "syncSeconds": round(sync_seconds, 4),
                    "coldSeconds": round(cold_seconds, 4),
                    "warmSeconds": round(warm_seconds, 4),
                    "sqliteBytes": database.stat().st_size,
                    "baselineStable": cold["baselineId"] == warm["baselineId"],
                    "rawEdges": cold["summary"]["rawEdges"],
                }
            )
        result: dict[str, object] = {
            "mode": "incremental",
            "initialCommits": initial_commits,
            "initialIndexSeconds": round(initial_index_seconds, 4),
            "initialBaselineSeconds": round(initial_baseline_seconds, 4),
            "initialBaselineId": initial_baseline["baselineId"],
            "batches": batches,
        }
        if assessment_before is not None and assessment_after is not None:
            overhead = (
                (assessment_after - assessment_before) / assessment_before
                if assessment_before > 0
                else 0.0
            )
            result["assessment"] = {
                "beforeBaselineMedianSeconds": round(assessment_before, 4),
                "afterBaselineMedianSeconds": round(assessment_after, 4),
                "overheadRatio": round(overhead, 4),
            }
        return result


def _parse_increments(value: str) -> tuple[int, ...]:
    try:
        return tuple(int(item.strip()) for item in value.split(",") if item.strip())
    except ValueError as exc:
        raise SystemExit("--increments must be a comma-separated integer list") from exc


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("domain", "incremental"), default="domain")
    parser.add_argument("--commits", type=int, default=10_000)
    parser.add_argument("--initial-commits", type=int, default=10)
    parser.add_argument("--increments", default="1,10,100")
    parser.add_argument("--measure-assessment", action="store_true")
    arguments = parser.parse_args()
    result = (
        _domain_benchmark(arguments.commits)
        if arguments.mode == "domain"
        else _incremental_benchmark(
            arguments.initial_commits,
            _parse_increments(arguments.increments),
            measure_assessment=arguments.measure_assessment,
        )
    )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
