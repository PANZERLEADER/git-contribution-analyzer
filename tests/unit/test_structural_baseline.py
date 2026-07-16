from __future__ import annotations

from datetime import UTC, datetime

from git_contribution_analyzer.domain.models.contribution import ContributionCommit
from git_contribution_analyzer.domain.models.structural_baseline import (
    StructuralRuleConfig,
    StructuralTimeStrategy,
)
from git_contribution_analyzer.domain.services.structural_baseline import (
    build_structural_baseline,
)


def _commit(
    commit_hash: str,
    day: int,
    paths: tuple[str, ...],
    *,
    patch_id: str | None = None,
    merge: bool = False,
    binary_only: bool = False,
) -> ContributionCommit:
    return ContributionCommit(
        hash=commit_hash,
        subject=f"feat: {commit_hash}",
        authored_at=datetime(2026, 1, day, tzinfo=UTC),
        commit_type="FEATURE",
        delivery_status="LANDED",
        paths=paths,
        modules=tuple(sorted({path.split("/", maxsplit=1)[0] for path in paths})),
        insertions=0 if binary_only else 10,
        deletions=0,
        files_changed=len(paths),
        merge=merge,
        binary_files=len(paths) if binary_only else 0,
        generated_files=0,
        patch_id=patch_id,
    )


def _config(**overrides: object) -> StructuralRuleConfig:
    values: dict[str, object] = {
        "time_strategy": StructuralTimeStrategy.LIFETIME,
        "minimum_baseline_commits": 2,
        "hotspot_percentile": 0.75,
        "minimum_co_change_count": 2,
        "minimum_subset_ratio": 0.75,
        "minimum_jaccard": 0.2,
        "minimum_hub_penalty": 0.0,
        "maximum_context_paths": 200,
        "rolling_window_days": 365,
    }
    values.update(overrides)
    return StructuralRuleConfig(**values)


def test_should_build_cutoff_baseline_and_keep_subthreshold_edges() -> None:
    commits = (
        _commit("a", 1, ("src/a.py", "src/b.py"), patch_id="p-a"),
        _commit("duplicate", 2, ("src/a.py", "src/b.py"), patch_id="p-a"),
        _commit("merge", 3, ("src/a.py", "src/b.py"), merge=True),
        _commit("generated", 4, ("dist/bundle.js",)),
        _commit("binary", 5, ("assets/logo.png",), binary_only=True),
        _commit("b", 6, ("src/a.py", "src/b.py")),
        _commit("future", 7, ("src/a.py", "src/c.py")),
    )

    baseline = build_structural_baseline(
        commits,
        cutoff=datetime(2026, 1, 7, tzinfo=UTC),
        config=_config(),
    )

    assert baseline.summary.eligible_commits == 2
    assert [(entry.path, entry.change_count) for entry in baseline.file_counts] == [
        ("src/a.py", 2),
        ("src/b.py", 2),
    ]
    assert [
        (entry.left_path, entry.right_path, entry.co_change_count)
        for entry in baseline.edge_counts
    ] == [("src/a.py", "src/b.py", 2)]
    assert all("future" not in hashes for hashes in baseline.supporting_commits.values())


def test_should_retain_nonzero_edge_below_candidate_threshold() -> None:
    baseline = build_structural_baseline(
        (
            _commit("a", 1, ("src/a.py", "src/b.py")),
            _commit("b", 2, ("src/a.py", "src/c.py")),
        ),
        cutoff=datetime(2026, 1, 3, tzinfo=UTC),
        config=_config(minimum_co_change_count=2),
    )

    assert len(baseline.edge_counts) == 2
    assert baseline.materialization.edge_metrics == ()


def test_should_control_ubiquitous_hub_with_jaccard() -> None:
    commits = (
        *(
            _commit(f"hub-{day}", day, ("config.yml", f"src/f{day}.py"))
            for day in range(1, 7)
        ),
        _commit("pair-1", 7, ("src/a.py", "src/b.py")),
        _commit("pair-2", 8, ("src/a.py", "src/b.py")),
    )

    baseline = build_structural_baseline(
        commits,
        cutoff=datetime(2026, 1, 9, tzinfo=UTC),
        config=_config(minimum_jaccard=0.5),
    )

    candidates = {
        (entry.left_path, entry.right_path) for entry in baseline.materialization.edge_metrics
    }
    assert ("src/a.py", "src/b.py") in candidates
    assert all("config.yml" not in edge for edge in candidates)


def test_should_filter_ubiquitous_hub_with_explicit_penalty_threshold() -> None:
    commits = (
        *(
            _commit(f"hub-a-{day}", day, ("config.yml", "src/a.py"))
            for day in range(1, 4)
        ),
        *(
            _commit(f"hub-other-{day}", day, ("config.yml", f"src/f{day}.py"))
            for day in range(4, 8)
        ),
        *(
            _commit(f"pair-{day}", day, ("src/x.py", "src/y.py"))
            for day in range(8, 11)
        ),
    )

    baseline = build_structural_baseline(
        commits,
        cutoff=datetime(2026, 1, 11, tzinfo=UTC),
        config=_config(
            minimum_co_change_count=3,
            minimum_jaccard=0.3,
            minimum_hub_penalty=0.5,
        ),
    )

    candidates = {
        (entry.left_path, entry.right_path) for entry in baseline.materialization.edge_metrics
    }
    assert ("src/x.py", "src/y.py") in candidates
    assert ("config.yml", "src/a.py") not in candidates


def test_should_cap_edges_for_large_context_and_report_gap() -> None:
    baseline = build_structural_baseline(
        (
            _commit("large", 1, tuple(f"src/f{i}.py" for i in range(5))),
            _commit("normal", 2, ("src/a.py",)),
        ),
        cutoff=datetime(2026, 1, 3, tzinfo=UTC),
        config=_config(maximum_context_paths=3),
    )

    assert baseline.summary.capped_commits == 1
    assert baseline.edge_counts == ()
    assert "STRUCTURAL_CONTEXT_CAPPED" in baseline.materialization.gaps


def test_should_use_rolling_window_for_recent_counts() -> None:
    baseline = build_structural_baseline(
        (
            _commit("old", 1, ("src/a.py",)),
            _commit("recent", 8, ("src/b.py",)),
        ),
        cutoff=datetime(2026, 1, 10, tzinfo=UTC),
        config=_config(
            time_strategy=StructuralTimeStrategy.DUAL_WINDOW,
            rolling_window_days=3,
        ),
    )

    counts = {entry.path: entry for entry in baseline.file_counts}
    assert counts["src/a.py"].recent_change_count == 0
    assert counts["src/b.py"].recent_change_count == 1
