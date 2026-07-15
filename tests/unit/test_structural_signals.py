from __future__ import annotations

from datetime import UTC, datetime, timedelta

from git_contribution_analyzer.domain.models.contribution import ContributionCommit
from git_contribution_analyzer.domain.services.structural_signals import (
    STRUCTURAL_SIGNAL_RULE_VERSION,
    build_structural_signals,
)


def _commit(
    index: int,
    *paths: str,
    merge: bool = False,
    binary_files: int = 0,
    patch_id: str | None = None,
) -> ContributionCommit:
    return ContributionCommit(
        hash=f"{index:040d}",
        subject=f"feat: change {index}",
        authored_at=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=index),
        commit_type="FEATURE",
        delivery_status="LANDED",
        paths=paths,
        modules=tuple(sorted({path.split("/", maxsplit=1)[0] for path in paths})),
        insertions=0 if binary_files else 10,
        deletions=0 if binary_files else 2,
        files_changed=len(paths),
        merge=merge,
        binary_files=binary_files,
        generated_files=0,
        patch_id=patch_id,
    )


def test_should_find_repeated_co_changes_and_rank_structural_hotspots() -> None:
    commits = (
        _commit(1, "api/controller.py", "service/user.py", "tests/test_user.py"),
        _commit(2, "api/controller.py", "service/user.py"),
        _commit(3, "api/controller.py", "service/user.py"),
        _commit(4, "api/controller.py", "config/settings.py"),
    )

    result = build_structural_signals(commits)

    assert result["ruleVersion"] == STRUCTURAL_SIGNAL_RULE_VERSION
    assert result["summary"] == {
        "analyzedCommits": 4,
        "analyzedFiles": 4,
        "coupledPairs": 1,
        "hotspots": 2,
    }
    assert result["couplings"] == [
        {
            "leftPath": "api/controller.py",
            "rightPath": "service/user.py",
            "coChangeCommits": 3,
            "confidence": "HIGH",
            "commitHashes": [f"{value:040d}" for value in (1, 2, 3)],
        }
    ]
    assert result["hotspots"] == [
        {
            "path": "api/controller.py",
            "changeCommits": 4,
            "coupledFiles": 1,
            "coChangeCommits": 3,
            "score": 7,
            "commitHashes": [f"{value:040d}" for value in (1, 2, 3, 4)],
        },
        {
            "path": "service/user.py",
            "changeCommits": 3,
            "coupledFiles": 1,
            "coChangeCommits": 3,
            "score": 6,
            "commitHashes": [f"{value:040d}" for value in (1, 2, 3)],
        },
    ]
    assert result["limitations"]


def test_should_exclude_noise_and_duplicate_patches() -> None:
    commits = (
        _commit(1, "src/app.py", "src/config.py", patch_id="patch-1"),
        _commit(2, "src/app.py", "src/config.py", patch_id="patch-1"),
        _commit(3, "src/app.py", "generated/client.py"),
        _commit(4, "src/app.py", "src/config.py", merge=True),
        _commit(5, "assets/logo.png", binary_files=1),
    )

    result = build_structural_signals(commits)

    assert result["summary"] == {
        "analyzedCommits": 2,
        "analyzedFiles": 2,
        "coupledPairs": 0,
        "hotspots": 1,
    }
    assert result["couplings"] == []
    assert result["hotspots"] == [
        {
            "path": "src/app.py",
            "changeCommits": 2,
            "coupledFiles": 0,
            "coChangeCommits": 0,
            "score": 2,
            "commitHashes": [f"{value:040d}" for value in (1, 3)],
        }
    ]


def test_should_return_empty_signals_for_isolated_one_off_changes() -> None:
    result = build_structural_signals(
        (
            _commit(1, "api/one.py"),
            _commit(2, "service/two.py"),
        )
    )

    assert result["summary"] == {
        "analyzedCommits": 2,
        "analyzedFiles": 2,
        "coupledPairs": 0,
        "hotspots": 0,
    }
    assert result["couplings"] == []
    assert result["hotspots"] == []
