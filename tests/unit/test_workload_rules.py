from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from git_contribution_analyzer.domain.models.contribution import (
    ContributionCommit,
    ContributionItem,
)
from git_contribution_analyzer.domain.models.work_assessment import (
    CompletionBucket,
    SizeBand,
    WorkloadBaseline,
)
from git_contribution_analyzer.domain.services.workload_rules import (
    assess_item_size,
    build_workload_baseline,
    classify_completion,
)


def _commit(
    *,
    hash_: str = "a",
    status: str = "LANDED",
    path: str = "src/app.py",
    insertions: int = 20,
    deletions: int = 5,
    merge: bool = False,
    commit_type: str = "FEATURE",
    patch_id: str | None = None,
) -> ContributionCommit:
    return ContributionCommit(
        hash=hash_,
        subject="feat: change",
        authored_at=datetime(2026, 1, 1, tzinfo=UTC),
        commit_type=commit_type,
        delivery_status=status,
        paths=(path,),
        modules=(path.split("/", 1)[0],),
        insertions=insertions,
        deletions=deletions,
        files_changed=1,
        merge=merge,
        binary_files=0,
        generated_files=0,
        patch_id=patch_id,
    )


def _item(*commits: ContributionCommit) -> ContributionItem:
    return ContributionItem(
        id="CI-001",
        group_key="test",
        title="Test item",
        confidence="HIGH",
        commits=commits,
        evidence_ids=("EV-001",),
    )


def test_should_classify_completed_pending_rework_and_integration() -> None:
    assert classify_completion(_item(_commit(status="LANDED"))) is CompletionBucket.COMPLETED
    assert (
        classify_completion(_item(_commit(status="AUTHORED_ONLY")))
        is CompletionBucket.PENDING
    )
    assert (
        classify_completion(_item(_commit(status="REVERTED")))
        is CompletionBucket.REWORK
    )
    assert (
        classify_completion(_item(_commit(status="LANDED", merge=True)))
        is CompletionBucket.INTEGRATION
    )


def test_should_count_duplicate_patch_only_once() -> None:
    item = _item(
        _commit(hash_="a", patch_id="same", insertions=50, deletions=10),
        _commit(hash_="b", patch_id="same", insertions=50, deletions=10),
    )

    result = assess_item_size(item)

    assert result.effective_churn == 60
    assert result.effective_files == 1


def test_should_ignore_generated_lockfile_and_binary_only_changes() -> None:
    item = _item(
        _commit(hash_="a", path="dist/bundle.js", insertions=2000),
        _commit(hash_="b", path="uv.lock", insertions=2000),
        replace(
            _commit(hash_="c", path="assets/logo.png", insertions=2000),
            binary_files=1,
        ),
    )

    result = assess_item_size(item)

    assert result.effective_churn == 0
    assert result.effective_files == 0
    assert result.band is SizeBand.SMALL


def test_should_apply_static_size_thresholds() -> None:
    small = assess_item_size(_item(_commit(insertions=40, deletions=10)))
    medium = assess_item_size(_item(_commit(insertions=100, deletions=10)))
    large = assess_item_size(_item(_commit(insertions=350, deletions=10)))
    xlarge = assess_item_size(_item(_commit(insertions=1100, deletions=10)))

    assert [small.band, medium.band, large.band, xlarge.band] == [
        SizeBand.SMALL,
        SizeBand.MEDIUM,
        SizeBand.LARGE,
        SizeBand.XLARGE,
    ]
    assert small.baseline_mode == "STATIC_FALLBACK"
    assert "INSUFFICIENT_REPOSITORY_BASELINE" in small.gaps


def test_should_use_repository_baseline_when_sample_is_sufficient() -> None:
    items = tuple(
        _item(_commit(hash_=str(index), insertions=10 + index * 10))
        for index in range(20)
    )
    baseline = build_workload_baseline(items)

    result = assess_item_size(items[10], baseline=baseline)

    assert result.baseline_mode == "REPOSITORY"
    assert result.baseline_sample_size == 20
    assert result.confidence == "HIGH"
    assert result.gaps == ()


def test_should_exclude_merge_from_effective_size_and_handle_empty_baseline() -> None:
    merge = _item(_commit(merge=True, insertions=500))

    result = assess_item_size(merge)
    empty = build_workload_baseline(())

    assert result.effective_churn == 0
    assert result.excluded_changes == ("MERGE:a",)
    assert empty.sample_size == 0
    assert empty.churn_percentiles == (0, 0, 0)


def test_should_apply_all_repository_percentile_bands_with_absolute_guards() -> None:
    baselines = (
        WorkloadBaseline(20, (100, 200, 300), (1, 2, 3), (1, 2, 3)),
        WorkloadBaseline(20, (50, 100, 300), (1, 2, 3), (1, 2, 3)),
        WorkloadBaseline(20, (100, 200, 400), (1, 2, 3), (1, 2, 3)),
        WorkloadBaseline(20, (100, 500, 1000), (1, 2, 3), (1, 2, 3)),
    )
    items = (
        _item(_commit(insertions=40, deletions=10)),
        _item(_commit(insertions=90, deletions=0)),
        _item(_commit(insertions=350, deletions=0)),
        _item(_commit(insertions=1100, deletions=0)),
    )

    bands = [
        assess_item_size(item, baseline=baseline).band
        for item, baseline in zip(items, baselines, strict=True)
    ]

    assert bands == [SizeBand.SMALL, SizeBand.MEDIUM, SizeBand.LARGE, SizeBand.XLARGE]
